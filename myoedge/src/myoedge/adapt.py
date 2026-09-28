"""Electrode shift: simulate it for training, undo it with one gesture.

The Myo is a ring of eight electrodes, so the dominant donning error is a
rotation of the ring around the forearm: channel c now sees roughly what
channel c+s saw during training, for a fractional s. Two remedies:

  augment      train on copies of the data rotated by small fractional
               amounts, so the classifier tolerates the error unaided
  recalibrate  after donning, the user makes a fist for about three seconds;
               the rotation whose per-channel activity pattern best matches
               the fist recorded at training time is undone on every
               incoming sample

Both are integer-only. Rotation weights are Q8, and the shift search
compares normalised correlations by cross-multiplication, so no square
root or division runs on the device.
"""

from __future__ import annotations

import numpy as np

STEPS_PER_CHANNEL = 4          # search / rotation resolution: quarter channels
SEARCH = np.arange(-4 * STEPS_PER_CHANNEL, 4 * STEPS_PER_CHANNEL + 1)  # +-4 channels


def rotate(emg: np.ndarray, steps: int) -> np.ndarray:
    """Circular rotation by steps/STEPS_PER_CHANNEL channels, int8 -> int8.

    out[:, c] = ((256 - f) * x[:, c + k] + f * x[:, c + k + 1] + 128) >> 8
    """
    x = emg.astype(np.int32)
    k, rem = divmod(int(steps), STEPS_PER_CHANNEL)
    f = rem * 256 // STEPS_PER_CHANNEL
    a = np.roll(x, -k, axis=1)
    b = np.roll(x, -k - 1, axis=1)
    return np.clip(((256 - f) * a + f * b + 128) >> 8, -128, 127).astype(np.int8)


def pattern(emg: np.ndarray) -> np.ndarray:
    """Per-channel activity: sum of |x|, int64."""
    return np.abs(emg.astype(np.int64)).sum(0)


def estimate_shift(ref: np.ndarray, cal_emg: np.ndarray) -> int:
    """Rotation (in steps) that maps the calibration fist back onto the reference.

    maximise  <ref, p_s> / |p_s|  over s, compared without roots:
    a/|p| > b/|q|  <=>  a^2 |q|^2 > b^2 |p|^2  for a, b > 0.
    """
    best, best_num, best_den = 0, -1, 1
    for s in SEARCH:
        p = pattern(rotate(cal_emg, -int(s)))
        dot = int(np.dot(ref, p))
        num, den = dot * dot if dot > 0 else 0, int(np.dot(p, p)) or 1
        if num * best_den > best_num * den:
            best, best_num, best_den = int(s), num, den
    return best


def augment(recs, max_channels: float):
    """Training copies rotated by up to +-max_channels in half-channel steps."""
    from .data import Recording

    if max_channels <= 0:
        return list(recs)
    half = STEPS_PER_CHANNEL // 2
    lim = int(round(max_channels * STEPS_PER_CHANNEL))
    steps = range(-lim, lim + 1, half)
    return [Recording(rotate(r.emg, s), r.label, r.rep, r.session) for r in recs for s in steps]
