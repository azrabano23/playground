"""Verification gates that compile and run C.

A gate is only as good as what it executes. These compile emitted sources with
warnings as errors, run them, and compare every output byte against the
numpy reference. `bit_exact_mlp` is the gate the int8 projects rely on.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .int8 import QMLP, emit_c

CFLAGS = ["-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic"]


class CGateError(RuntimeError):
    pass


def cc() -> str | None:
    for c in ("cc", "gcc", "clang"):
        if shutil.which(c):
            return c
    return None


def compile_and_run(sources: dict[str, str], main_c: str, stdin: str = "",
                    extra_flags: list[str] | None = None, timeout: float = 60) -> str:
    compiler = cc()
    if compiler is None:
        raise CGateError("no C compiler on PATH")
    with tempfile.TemporaryDirectory() as d:
        dp = Path(d)
        for fn, text in sources.items():
            (dp / fn).write_text(text)
        (dp / "main.c").write_text(main_c)
        cfiles = [str(dp / f) for f in list(sources) + ["main.c"] if f.endswith(".c")]
        exe = dp / "prog"
        r = subprocess.run([compiler, *CFLAGS, *(extra_flags or []), "-I", d, *cfiles,
                            "-o", str(exe)], capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            raise CGateError(f"compile failed:\n{r.stderr}")
        r = subprocess.run([str(exe)], input=stdin, capture_output=True, text=True,
                           timeout=timeout)
        if r.returncode != 0:
            raise CGateError(f"run failed ({r.returncode}):\n{r.stderr}")
        return r.stdout


def object_size(sources: dict[str, str], unit: str) -> dict[str, int]:
    """Section sizes of one translation unit compiled for the host (-Os).

    This is a host-toolchain number, useful for relative comparison only. The
    exact on-target figure needs the target compiler.
    """
    compiler = cc()
    if compiler is None or not shutil.which("size"):
        raise CGateError("need a C compiler and binutils `size`")
    with tempfile.TemporaryDirectory() as d:
        for fn, text in sources.items():
            Path(d, fn).write_text(text)
        obj = Path(d, "u.o")
        r = subprocess.run([compiler, *CFLAGS[:-3], "-Os", "-c", str(Path(d, unit)), "-I", d,
                            "-o", str(obj)], capture_output=True, text=True)
        if r.returncode != 0:
            raise CGateError(r.stderr)
        out = subprocess.run(["size", "-A", str(obj)], capture_output=True, text=True).stdout
    sizes: dict[str, int] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith(".") and parts[1].isdigit():
            sizes[parts[0]] = int(parts[1])
    return sizes


@dataclass
class ExactReport:
    n: int
    mismatched_rows: int
    c_digest: str
    ref_digest: str

    @property
    def ok(self) -> bool:
        return self.mismatched_rows == 0 and self.c_digest == self.ref_digest


def bit_exact_mlp(q: QMLP, xq: np.ndarray, name: str = "net") -> ExactReport:
    """Run the emitted C on int8 inputs and compare byte-for-byte to forward_int."""
    xq = np.asarray(xq, np.int8)
    ref = q.forward_int(xq)
    srcs = emit_c(q, name)
    up = name.upper()
    main = f"""#include <stdio.h>
#include "{name}.h"
int main(void) {{
    int8_t in[{up}_IN], out[{up}_OUT];
    int v;
    for (;;) {{
        for (int i = 0; i < {up}_IN; ++i) {{
            if (scanf("%d", &v) != 1) return 0;
            in[i] = (int8_t)v;
        }}
        {name}_forward(in, out);
        for (int o = 0; o < {up}_OUT; ++o) printf("%d ", out[o]);
        printf("\\n");
    }}
}}
"""
    stdin = "\n".join(" ".join(str(int(v)) for v in row) for row in xq) + "\n"
    out = compile_and_run(srcs, main, stdin)
    got = np.array([[int(t) for t in line.split()] for line in out.strip().splitlines()],
                   dtype=np.int8).reshape(ref.shape)
    bad = int(np.sum(np.any(got != ref, axis=-1)))
    return ExactReport(len(xq), bad, hashlib.sha256(got.tobytes()).hexdigest()[:16],
                       hashlib.sha256(ref.tobytes()).hexdigest()[:16])
