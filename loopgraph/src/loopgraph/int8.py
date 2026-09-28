"""Int8 dense networks, an exact integer reference, and a C99 emitter.

The contract is the one that matters on a microcontroller: the emitted C and
the numpy reference below perform the *same integer operations* in the same
order, so their outputs are bit-identical, and the float model is only ever an
approximation both are compared against.

Scheme (TFLite-style, symmetric):
  * activations int8, zero point 0, one scale per tensor
  * weights int8, one scale per output channel
  * bias int32 at scale s_in * s_w[o]
  * accumulate in int32; requantize with an integer multiplier and shift:
        y = clamp((acc * m[o] + 2^(n-1)) >> n)          (int64 intermediate)
  * ReLU is the clamp's lower bound (0 instead of -128)

No malloc, no floats in the forward pass, no libc beyond <stdint.h>.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np



@dataclass
class QLayer:
    w: np.ndarray        # int8 [out, in]
    b: np.ndarray        # int32 [out]
    m: np.ndarray        # int32 [out] requant multiplier
    n: int               # right shift
    relu: bool
    s_out: float         # output scale (dequantize: y_float = y_int8 * s_out)


@dataclass
class QMLP:
    s_in: float
    layers: list[QLayer] = field(default_factory=list)

    @property
    def dims(self) -> list[int]:
        return [self.layers[0].w.shape[1]] + [l.w.shape[0] for l in self.layers]

    @property
    def s_out(self) -> float:
        return self.layers[-1].s_out

    @property
    def param_bytes(self) -> int:
        """Bytes of const data the C emits: int8 weights + int32 bias + int32 multipliers."""
        return sum(l.w.size + 4 * l.b.size + 4 * l.m.size for l in self.layers)

    @property
    def scratch_bytes(self) -> int:
        """RAM for the two ping-pong activation buffers."""
        return 2 * max(self.dims)

    @property
    def macs(self) -> int:
        return sum(l.w.size for l in self.layers)

    def quantize_input(self, x: np.ndarray) -> np.ndarray:
        return np.clip(np.round(np.asarray(x, np.float64) / self.s_in), -128, 127).astype(np.int8)

    def dequantize_output(self, y: np.ndarray) -> np.ndarray:
        return y.astype(np.float64) * self.s_out

    def forward_int(self, xq: np.ndarray) -> np.ndarray:
        """Exact integer reference. xq: int8 [..., in] -> int8 [..., out]."""
        a = np.asarray(xq, np.int64)
        for l in self.layers:
            acc = a @ l.w.astype(np.int64).T + l.b.astype(np.int64)
            acc = np.clip(acc, -(2**31), 2**31 - 1)  # int32 accumulator semantics
            y = (acc * l.m.astype(np.int64) + (1 << (l.n - 1))) >> l.n
            a = np.clip(y, 0 if l.relu else -128, 127)
        return a.astype(np.int8)

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Float in, float out, through the integer path."""
        return self.dequantize_output(self.forward_int(self.quantize_input(x)))


def float_forward(weights: list[tuple[np.ndarray, np.ndarray]], x: np.ndarray,
                  capture: bool = False):
    """Reference float MLP: ReLU between layers, linear output."""
    a = np.asarray(x, np.float64)
    acts = [a]
    for i, (W, b) in enumerate(weights):
        a = a @ W.T + b
        if i < len(weights) - 1:
            a = np.maximum(a, 0)
        acts.append(a)
    return (a, acts) if capture else a


def _requant(M: np.ndarray) -> tuple[np.ndarray, int]:
    """Integer multipliers m and shared shift n with m / 2^n ~= M, m < 2^31."""
    mmax = float(np.max(M)) if M.size else 1.0
    n = 1
    while n < 62 and mmax * 2 ** (n + 1) < 2**31 - 1:
        n += 1
    m = np.round(M * 2**n).astype(np.int64)
    return np.clip(m, 0, 2**31 - 1).astype(np.int32), n


def quantize_mlp(weights: list[tuple[np.ndarray, np.ndarray]], calib: np.ndarray,
                 pct: float = 99.99) -> QMLP:
    """Post-training quantization from float weights and calibration inputs.

    Activation ranges come from a high percentile of the calibration set rather
    than the max, so one outlier sample does not waste most of the int8 range.
    """
    _, acts = float_forward(weights, calib, capture=True)

    def scale(a: np.ndarray) -> float:
        r = float(np.percentile(np.abs(a), pct)) if a.size else 0.0
        return max(r, 1e-8) / 127.0

    s_in = scale(acts[0])
    q = QMLP(s_in)
    s_prev = s_in
    for i, (W, b) in enumerate(weights):
        W = np.asarray(W, np.float64)
        b = np.asarray(b, np.float64)
        s_w = np.maximum(np.max(np.abs(W), axis=1), 1e-12) / 127.0
        wq = np.clip(np.round(W / s_w[:, None]), -127, 127).astype(np.int8)
        bq = np.clip(np.round(b / (s_prev * s_w)), -(2**31), 2**31 - 1).astype(np.int32)
        s_out = scale(acts[i + 1])
        m, n = _requant(s_prev * s_w / s_out)
        q.layers.append(QLayer(wq, bq, m, n, relu=i < len(weights) - 1, s_out=s_out))
        s_prev = s_out
    return q


# -- C emission ------------------------------------------------------------

def _ident(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"not a C identifier: {name!r}")
    return name


def _arr(ctype: str, name: str, a: np.ndarray, per_line: int = 16) -> str:
    flat = [str(int(v)) for v in np.asarray(a).ravel()]
    rows = [", ".join(flat[i:i + per_line]) for i in range(0, len(flat), per_line)]
    body = ",\n    ".join(rows) if rows else "0"
    return f"static const {ctype} {name}[{max(1, len(flat))}] = {{\n    {body}\n}};\n"


def emit_c(q: QMLP, name: str) -> dict[str, str]:
    """Return {filename: source} for `<name>.h` and `<name>.c`."""
    name = _ident(name)
    up = name.upper()
    dims = q.dims
    h = f"""/* Generated by loopgraph.int8. Do not edit. */
#ifndef {up}_H
#define {up}_H
#include <stdint.h>

#define {up}_IN {dims[0]}
#define {up}_OUT {dims[-1]}
#define {up}_PARAM_BYTES {q.param_bytes}

/* Quantization: in_int8 = round(x / {up}_S_IN), y = out_int8 * {up}_S_OUT.
   Scales are for the host side; the forward pass itself uses no floats. */
#define {up}_S_IN {q.s_in!r}f
#define {up}_S_OUT {q.s_out!r}f

void {name}_forward(const int8_t in[{up}_IN], int8_t out[{up}_OUT]);

#endif
"""
    parts = [f"/* Generated by loopgraph.int8. Do not edit. */\n#include \"{name}.h\"\n\n"]
    for i, l in enumerate(q.layers):
        parts.append(_arr("int8_t", f"W{i}", l.w))
        parts.append(_arr("int32_t", f"B{i}", l.b))
        parts.append(_arr("int32_t", f"M{i}", l.m))
    # hidden activations ping-pong between two buffers; declare only the ones
    # used, since an unused static is a -Werror failure for shallow networks
    width = max(dims)
    nbuf = min(2, len(q.layers) - 1)
    for i in range(nbuf):
        parts.append(f"\nstatic int8_t buf_{'ab'[i]}[{width}];")
    parts.append("\n\n")
    parts.append(
        "static void dense(const int8_t *x, int nin, int nout, const int8_t *w,\n"
        "                  const int32_t *b, const int32_t *m, int n, int8_t lo, int8_t *y)\n"
        "{\n"
        "    for (int o = 0; o < nout; ++o) {\n"
        "        int64_t acc = b[o];\n"
        "        const int8_t *row = w + (int32_t)o * nin;\n"
        "        for (int i = 0; i < nin; ++i)\n"
        "            acc += (int32_t)row[i] * (int32_t)x[i];\n"
        "        if (acc > INT32_MAX) acc = INT32_MAX;\n"
        "        if (acc < INT32_MIN) acc = INT32_MIN;\n"
        "        int64_t v = (acc * (int64_t)m[o] + ((int64_t)1 << (n - 1))) >> n;\n"
        "        if (v > 127) v = 127;\n"
        "        if (v < lo) v = lo;\n"
        "        y[o] = (int8_t)v;\n"
        "    }\n"
        "}\n\n"
    )
    body = [f"void {name}_forward(const int8_t in[{up}_IN], int8_t out[{up}_OUT])\n{{\n"]
    src = "in"
    for i, l in enumerate(q.layers):
        last = i == len(q.layers) - 1
        dst = "out" if last else ("buf_a" if i % 2 == 0 else "buf_b")
        lo = "0" if l.relu else "-128"
        body.append(f"    dense({src}, {l.w.shape[1]}, {l.w.shape[0]}, W{i}, B{i}, M{i}, "
                    f"{l.n}, {lo}, {dst});\n")
        src = dst
    body.append("}\n")
    return {f"{name}.h": h, f"{name}.c": "".join(parts) + "".join(body)}
