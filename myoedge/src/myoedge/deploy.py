"""The on-device decoder: int8 EMG samples in, servo angles out.

Per sample (200 Hz): rotate by the calibrated shift, push into a ring buffer.
Every `step` samples: Hudgins features over the last `window` samples, Q16
prep to int8, int8 classifier, majority vote over the last `vote` decisions,
then drive a HACKberry-style hand (three servos: thumb, index, and the
coupled middle-ring-little) toward the posture for that class at a speed
proportional to muscle activity. Rest and the two wrist classes hold the
current posture, since the hand has no wrist actuator.

`Decoder` is the exact integer reference; `emit` writes the same program as
C99 for an 8-bit AVR (ATmega32U4, the Arduino Micro on the HACKberry board).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from loopgraph.int8 import QMLP, emit_c, quantize_mlp

from .adapt import STEPS_PER_CHANNEL
from .data import CHANNELS, FS
from .features import ilog2_q4, td

FRAC = 16
# HACKberry Mk2 firmware servo ranges, degrees (open, closed): thumb, index, others
SERVO_OPEN = np.array([10, 0, 20])
SERVO_CLOSED = np.array([95, 100, 75])
POSTURE = {0: SERVO_CLOSED, 1: SERVO_OPEN}   # Hand_Close, Hand_Open; others hold
SPEED_SHIFT = 6   # degrees per decision = clamp(total MAV-sum >> 6, 1, VMAX)
VMAX = 12


@dataclass
class Model:
    q: QMLP
    c: np.ndarray     # int32 Q16 offsets
    g: np.ndarray     # int32 Q16 gains
    window: int
    step: int
    vote: int
    zc_thr: int
    ssc_thr: int
    shift: int = 0    # calibrated rotation, in 1/STEPS_PER_CHANNEL channel steps

    @classmethod
    def build(cls, layers, mu, sd, X_calib, window, step, vote, zc_thr=1, ssc_thr=1,
              pct=99.9) -> "Model":
        Z = (X_calib - mu) / sd
        r = np.maximum(np.percentile(np.abs(Z), pct, axis=0), 1e-3)
        L = [(W.copy(), b.copy()) for W, b in layers]
        L[0] = (L[0][0] * r[None, :], L[0][1])
        q = quantize_mlp(L, Z / r, pct=pct)
        g = np.round(1.0 / (sd * r * q.s_in) * 2**FRAC).astype(np.int64)
        c = np.round(mu * g).astype(np.int64)
        if max(np.abs(g).max(), np.abs(c).max()) >= 2**31:
            raise OverflowError("prep constants exceed int32")
        return cls(q, c.astype(np.int32), g.astype(np.int32), window, step, vote,
                   zc_thr, ssc_thr)

    # -- exact integer reference ----------------------------------------------
    def prep(self, F: np.ndarray) -> np.ndarray:
        v = (F.astype(np.int64) * self.g - self.c + (1 << (FRAC - 1))) >> FRAC
        return np.clip(v, -128, 127).astype(np.int8)

    def classify(self, F: np.ndarray) -> np.ndarray:
        """int32 features [N, 32] -> class per window (first max wins, as in C)."""
        return np.argmax(self.q.forward_int(self.prep(np.atleast_2d(F))), axis=1)

    @property
    def latency_ms(self) -> float:
        """Derived decision delay: half a window plus half the vote span."""
        return 1000.0 * (self.window / 2 + (self.vote - 1) * self.step / 2) / FS

    @property
    def flash_bytes(self) -> int:
        return self.q.param_bytes + 8 * self.g.size

    @property
    def ram_bytes(self) -> int:
        return self.window * CHANNELS + self.vote + 4 * self.g.size + self.q.scratch_bytes + 16


@dataclass
class Decoder:
    """Streaming state, one sample at a time, exactly as the C does it."""

    m: Model
    buf: np.ndarray = None
    head: int = 0
    filled: int = 0
    since: int = 0
    votes: list = field(default_factory=list)
    servo: np.ndarray = None

    def __post_init__(self):
        self.buf = np.zeros((self.m.window, CHANNELS), np.int8)
        self.servo = SERVO_OPEN.copy()

    def push(self, sample: np.ndarray):
        """Returns (class, servo angles) on decision ticks, else None."""
        from .adapt import rotate

        s = rotate(np.asarray(sample, np.int8)[None, :], -self.m.shift)[0]
        self.buf[self.head] = s
        self.head = (self.head + 1) % self.m.window
        self.filled = min(self.filled + 1, self.m.window)
        self.since += 1
        if self.filled < self.m.window or self.since < self.m.step:
            return None
        self.since = 0
        w = np.roll(self.buf, -self.head, axis=0)  # oldest first
        f = td(w, self.m.zc_thr, self.m.ssc_thr, log=True)
        k = int(self.m.classify(f)[0])
        self.votes = (self.votes + [k])[-self.m.vote:]
        counts = np.bincount(self.votes, minlength=5)
        cls = int(np.argmax(counts))
        if cls in POSTURE:
            speed = int(np.clip(int(np.abs(w.astype(np.int32)).sum()) >> SPEED_SHIFT, 1, VMAX))
            self.servo = self.servo + np.clip(POSTURE[cls] - self.servo, -speed, speed)
        return cls, self.servo.copy()


def run_stream(m: Model, emg: np.ndarray):
    d = Decoder(m)
    out = []
    for s in emg:
        r = d.push(s)
        if r is not None:
            out.append((r[0], *r[1]))
    return np.array(out, np.int64).reshape(-1, 4)


# -- C ----------------------------------------------------------------------

def emit(m: Model, name: str = "myo") -> dict[str, str]:
    net = emit_c(m.q, f"{name}_net")
    up = name.upper()
    nf = m.g.size
    arr = lambda t, n, v: (f"static const {t} {n}[{len(v)}] = "
                           f"{{{', '.join(str(int(x)) for x in v)}}};\n")
    h = f"""/* Generated by myoedge. Do not edit. */
#ifndef {up}_DECODER_H
#define {up}_DECODER_H
#include <stdint.h>

#define {up}_CH 8
#define {up}_WINDOW {m.window}
#define {up}_STEP {m.step}
#define {up}_VOTE {m.vote}

typedef struct {{
    int8_t buf[{up}_WINDOW][{up}_CH];
    uint8_t head, filled, since, nvotes;
    uint8_t votes[{up}_VOTE];
    int16_t servo[3];
    int8_t shift;   /* calibrated rotation, 1/{STEPS_PER_CHANNEL} channel steps */
}} {name}_t;

void {name}_init({name}_t *d, int8_t shift);
/* Push one sample; returns the decided class (0..4) on decision ticks, else -1.
   d->servo then holds thumb, index, others in degrees. */
int8_t {name}_push({name}_t *d, const int8_t sample[{up}_CH]);

#endif
"""
    c = [f"/* Generated by myoedge. Do not edit. */\n#include \"{name}.h\"\n#include \"{name}_net.h\"\n\n",
         arr("int32_t", "P_GAIN", m.g), arr("int32_t", "P_OFF", m.c),
         arr("int16_t", "S_OPEN", SERVO_OPEN), arr("int16_t", "S_CLOSED", SERVO_CLOSED)]
    c.append(f"""
static int32_t ilog2_q4(int32_t v)
{{
    if (v < 1) return 0;
    int32_t msb = 0;
    while ((v >> (msb + 1)) != 0) ++msb;
    int32_t frac = msb >= 4 ? (v >> (msb - 4)) & 15 : (v << (4 - msb)) & 15;
    return msb * 16 + frac;
}}

static void rotate(const int8_t *in, int8_t *out, int8_t steps)
{{
    int s = -steps;
    int k = s >= 0 ? s / {STEPS_PER_CHANNEL} : -((-s + {STEPS_PER_CHANNEL} - 1) / {STEPS_PER_CHANNEL});
    int rem = s - k * {STEPS_PER_CHANNEL};
    int32_t f = rem * 256 / {STEPS_PER_CHANNEL};
    for (int ch = 0; ch < {up}_CH; ++ch) {{
        int32_t a = in[((ch + k) % {up}_CH + {up}_CH) % {up}_CH];
        int32_t b = in[((ch + k + 1) % {up}_CH + {up}_CH) % {up}_CH];
        int32_t v = ((256 - f) * a + f * b + 128) >> 8;
        out[ch] = (int8_t)(v > 127 ? 127 : (v < -128 ? -128 : v));
    }}
}}

void {name}_init({name}_t *d, int8_t shift)
{{
    for (int i = 0; i < {up}_WINDOW; ++i)
        for (int ch = 0; ch < {up}_CH; ++ch) d->buf[i][ch] = 0;
    d->head = d->filled = d->since = d->nvotes = 0;
    for (int i = 0; i < 3; ++i) d->servo[i] = S_OPEN[i];
    d->shift = shift;
}}

#define AT(i) d->buf[(d->head + (i)) % {up}_WINDOW]

int8_t {name}_push({name}_t *d, const int8_t sample[{up}_CH])
{{
    rotate(sample, d->buf[d->head], d->shift);
    d->head = (uint8_t)((d->head + 1) % {up}_WINDOW);
    if (d->filled < {up}_WINDOW) ++d->filled;
    ++d->since;
    if (d->filled < {up}_WINDOW || d->since < {up}_STEP) return -1;
    d->since = 0;

    int32_t feat[{nf}];
    int32_t total = 0;
    for (int ch = 0; ch < {up}_CH; ++ch) {{
        int32_t mav = 0, wl = 0, zc = 0, ssc = 0;
        for (int i = 0; i < {up}_WINDOW; ++i) {{
            int32_t x = AT(i)[ch];
            mav += x < 0 ? -x : x;
            if (i + 1 < {up}_WINDOW) {{
                int32_t y = AT(i + 1)[ch], dd = y - x;
                wl += dd < 0 ? -dd : dd;
                if (x * y < 0 && (dd < 0 ? -dd : dd) >= {m.zc_thr}) ++zc;
            }}
            if (i > 0 && i + 1 < {up}_WINDOW) {{
                int32_t p = AT(i - 1)[ch], n = AT(i + 1)[ch];
                if ((x - p) * (x - n) >= {m.ssc_thr}) ++ssc;
            }}
        }}
        total += mav;
        feat[ch] = ilog2_q4(mav);
        feat[{CHANNELS} + ch] = ilog2_q4(wl);
        feat[{2 * CHANNELS} + ch] = zc;
        feat[{3 * CHANNELS} + ch] = ssc;
    }}
    int8_t x8[{nf}], y8[5];
    for (int i = 0; i < {nf}; ++i) {{
        int64_t v = ((int64_t)feat[i] * P_GAIN[i] - P_OFF[i] + (1 << {FRAC - 1})) >> {FRAC};
        x8[i] = (int8_t)(v > 127 ? 127 : (v < -128 ? -128 : v));
    }}
    {name}_net_forward(x8, y8);
    uint8_t k = 0;
    for (uint8_t j = 1; j < 5; ++j) if (y8[j] > y8[k]) k = j;

    if (d->nvotes < {up}_VOTE) d->votes[d->nvotes++] = k;
    else {{
        for (int i = 1; i < {up}_VOTE; ++i) d->votes[i - 1] = d->votes[i];
        d->votes[{up}_VOTE - 1] = k;
    }}
    uint8_t cnt[5] = {{0, 0, 0, 0, 0}}, cls = 0;
    for (int i = 0; i < d->nvotes; ++i) ++cnt[d->votes[i]];
    for (uint8_t j = 1; j < 5; ++j) if (cnt[j] > cnt[cls]) cls = j;

    if (cls <= 1) {{
        int32_t sp = total >> {SPEED_SHIFT};
        if (sp < 1) sp = 1;
        if (sp > {VMAX}) sp = {VMAX};
        for (int i = 0; i < 3; ++i) {{
            int32_t tgt = cls == 0 ? S_CLOSED[i] : S_OPEN[i];
            int32_t dlt = tgt - d->servo[i];
            if (dlt > sp) dlt = sp;
            if (dlt < -sp) dlt = -sp;
            d->servo[i] = (int16_t)(d->servo[i] + dlt);
        }}
    }}
    return (int8_t)cls;
}}
""")
    return {**net, f"{name}.h": h, f"{name}.c": "".join(c)}


def check_c(m: Model, emg: np.ndarray, name: str = "myo") -> tuple[bool, int, int]:
    """Stream the same samples through C and the reference; compare every decision."""
    from loopgraph.cgate import compile_and_run

    ref = run_stream(m, emg)
    up = name.upper()
    main = f"""#include <stdio.h>
#include "{name}.h"
int main(void) {{
    static {name}_t d;
    int8_t s[{up}_CH];
    int v;
    {name}_init(&d, {m.shift});
    for (;;) {{
        for (int ch = 0; ch < {up}_CH; ++ch) {{
            if (scanf("%d", &v) != 1) return 0;
            s[ch] = (int8_t)v;
        }}
        int8_t c = {name}_push(&d, s);
        if (c >= 0) printf("%d %d %d %d\\n", c, d.servo[0], d.servo[1], d.servo[2]);
    }}
}}
"""
    stdin = "\n".join(" ".join(map(str, s)) for s in emg) + "\n"
    out = compile_and_run(emit(m, name), main, stdin)
    got = np.array([[int(t) for t in l.split()] for l in out.strip().splitlines()],
                   np.int64).reshape(-1, 4)
    if got.shape != ref.shape:
        return False, len(ref), len(ref)
    bad = int(np.sum(np.any(got != ref, axis=1)))
    return bad == 0, bad, len(ref)
