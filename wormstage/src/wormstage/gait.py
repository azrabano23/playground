"""Closed-loop runs of a compiled circuit on the snake, and gait measurements.

The measurements are the ones used for the worm itself (Fang-Yen et al. 2010;
Berri et al. 2009): undulation frequency, wavelength in body lengths, speed,
the direction the wave travels, and dorsoventral symmetry.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .body import Snake
from .circuit import Circuit, compile_circuit, reset, tick


@dataclass
class Trace:
    t: np.ndarray
    phi: np.ndarray      # [T, J] rad
    pose: np.ndarray     # [T, 3]
    snake: Snake
    s_d: np.ndarray      # [T, nD]


def run(circuit: Circuit, snake: Snake, T: float = 30.0, dt: float = 0.02) -> Trace:
    k = compile_circuit(circuit, snake.n_links - 1, dt, snake.joint_max)
    st = reset(k, circuit.backward)
    pose = np.zeros(3)
    phi = np.zeros(snake.n_links - 1)
    n = int(T / dt)
    P = np.empty((n, len(phi)))
    X = np.empty((n, 3))
    SD = np.empty((n, len(k.dorsal_pos)), np.int8)
    for i in range(n):
        # the controller sees quantised encoder readings, like the real servo bus
        st, target = tick(k, st, np.round(phi * 1000).astype(np.int64))
        pose, phi = snake.step(pose, phi, target / 1000.0, dt)
        P[i], X[i], SD[i] = phi, pose, st.s_d
    return Trace(np.arange(n) * dt, P, X, snake, SD)


def _freq(x: np.ndarray, dt: float) -> float:
    x = x - x.mean()
    if np.std(x) < 1e-3:
        return 0.0
    ups = np.nonzero((x[:-1] < 0) & (x[1:] >= 0))[0]
    if len(ups) < 3:
        return 0.0
    return 1.0 / (np.mean(np.diff(ups)) * dt)


def measure(tr: Trace, settle: float = 10.0) -> dict:
    dt = tr.t[1] - tr.t[0]
    keep = tr.t >= settle
    phi = tr.phi[keep]
    pose = tr.pose[keep]
    J = phi.shape[1]
    L = tr.snake.length
    amp = phi.std(0)
    f = _freq(phi[:, J // 4], dt)
    out = {"freq_hz": f, "amp_rad": float(amp.mean()),
           "speed_bl_s": 0.0, "wavelength_bl": 0.0, "wave_dir": 0.0,
           "symmetry": 0.0, "undulating": 0}
    dur = tr.t[keep][-1] - tr.t[keep][0]
    out["speed_bl_s"] = float(np.linalg.norm(pose[-1, :2] - pose[0, :2]) / dur / L)
    # forward = displacement along the initial heading of the head
    d = pose[-1, :2] - pose[0, :2]
    h = np.array([np.cos(pose[0, 2]), np.sin(pose[0, 2])])
    out["forward_bl_s"] = float(d @ h / dur / L)
    if f > 0 and amp.min() > 0.02:
        # phase lag between neighbouring joints from the analytic signal
        spec = np.fft.rfft(phi - phi.mean(0), axis=0)
        freqs = np.fft.rfftfreq(len(phi), dt)
        b = np.argmin(np.abs(freqs - f))
        ph = np.unwrap(np.angle(spec[b]))
        slope = np.polyfit(np.arange(J), ph, 1)[0]  # rad per joint
        if abs(slope) > 1e-6:
            out["wavelength_bl"] = float(2 * np.pi / abs(slope) / (J + 1))
        out["wave_dir"] = float(-np.sign(slope))  # +1: head -> tail
        out["undulating"] = int(out["wave_dir"] != 0 and f > 0.05)
    if amp.mean() > 0.02:  # symmetry of a body that does not bend is undefined
        mean = phi.mean(0)
        out["symmetry"] = float(1 - np.clip(np.abs(mean).mean() / amp.mean(), 0, 1))
    return out
