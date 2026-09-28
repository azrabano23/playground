"""Hudgins time-domain features, in integer arithmetic.

Hudgins, Parker & Scott 1993 (IEEE TBME 40:82) define, per channel over a
window: mean absolute value, waveform length, zero crossings and slope sign
changes. Computed here exactly as an 8-bit microcontroller would: int8
samples in, int32 sums and counts out, no division. An optional integer
log2 (4 fractional bits) compresses the amplitude features, which vary over
two orders of magnitude between rest and a strong grip.
"""

from __future__ import annotations

import numpy as np

from .data import CHANNELS


def ilog2_q4(v: np.ndarray) -> np.ndarray:
    """floor(16 * log2(v)) approximately, for v >= 1; 0 for v < 1. Integer only.

    MSB position gives the integer part; the next four bits below it give a
    linear approximation of the fraction. Mirrored exactly in the C.
    """
    v = np.asarray(v, np.int64)
    out = np.zeros_like(v)
    pos = v >= 1
    vv = v[pos]
    msb = np.floor(np.log2(vv)).astype(np.int64)
    # guard floating log2 at exact powers: fix msb so that 2^msb <= v < 2^(msb+1)
    msb = np.where((1 << msb) > vv, msb - 1, msb)
    msb = np.where((1 << (msb + 1)) <= vv, msb + 1, msb)
    frac = np.where(msb >= 4, (vv >> np.maximum(msb - 4, 0)) & 15, (vv << (4 - msb)) & 15)
    out[pos] = msb * 16 + frac
    return out


def td(window: np.ndarray, zc_thr: int = 1, ssc_thr: int = 1, log: bool = True) -> np.ndarray:
    """int8 [W, C] -> int32 [4*C]: MAV-sum, WL, ZC, SSC per channel."""
    x = window.astype(np.int32)
    mav = np.abs(x).sum(0)
    d = np.diff(x, axis=0)
    wl = np.abs(d).sum(0)
    zc = ((x[:-1] * x[1:] < 0) & (np.abs(d) >= zc_thr)).sum(0)
    ssc = (((x[1:-1] - x[:-2]) * (x[1:-1] - x[2:])) >= ssc_thr).sum(0)
    if log:
        mav, wl = ilog2_q4(mav), ilog2_q4(wl)
    return np.concatenate([mav, wl, zc, ssc]).astype(np.int32)


def windows(emg: np.ndarray, length: int, step: int) -> np.ndarray:
    n = (len(emg) - length) // step + 1
    if n <= 0:
        return np.zeros((0, length, emg.shape[1]), emg.dtype)
    idx = np.arange(length)[None, :] + step * np.arange(n)[:, None]
    return emg[idx]


def featurize(recs, length: int, step: int, **kw) -> tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    for r in recs:
        for w in windows(r.emg, length, step):
            X.append(td(w, **kw))
            y.append(r.label)
    return np.array(X, np.int32).reshape(-1, 4 * CHANNELS), np.array(y)
