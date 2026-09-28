"""The forward motor circuit, per developmental stage, as integer code.

Model (after Boyle, Berri & Cohen 2012): there is no central pattern
generator. Each B-type motor neuron is bistable and excited by stretch of the
body *posterior* to it; the wave is produced by the loop through the body.
Here the body is the robot, so the robot's own joint encoders close the loop.

  dorsal B:   I_D = I_on + w_sr * stretch_D
  ventral B:  I_V = I_bias - S_D(nearest) + I_on + w_sr * stretch_V   (adult)
  switch on when I > 0.75, off when I < 0.25 (hysteresis H = 0.5)
  muscles:    first-order low-pass (tau) of neural drive
  joint:      target = gain * nmj(x) * (ventral - dorsal)

What changes with development (Mulcahy et al. 2022; Lu et al. 2022):
  * L1 has only the embryonic motor neurons: DB (7) excite dorsal muscle and
    DD (6) inhibit *ventral* muscle. There are no ventral B neurons at all.
    Ventral bends come from extrasynaptic cholinergic drive that excites
    ventral muscle tonically (`ventral_tonic`); DD inhibition carves it.
  * From L2, VB (11) and VD (13) exist and DD has rewired to dorsal muscle,
    so the circuit is two-sided.

Everything here is integer so that the numpy reference and the emitted C are
bit-identical: currents are Q12 (4096 = 1.0), muscles Q15, joints in mrad.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

Q12 = 4096
Q15 = 32767
ON, OFF = int(0.75 * Q12), int(0.25 * Q12)


@dataclass(frozen=True)
class Circuit:
    stage: str                 # "L1" or "post-L1"
    n_dorsal: int              # DB count
    n_ventral: int             # VB count (0 at L1)
    i_on: float = 0.675        # AVB drive onto B neurons
    i_bias: float = 0.5
    w_sr: float = 1.0          # stretch receptor gain
    field: float = 0.5         # posterior receptive field, fraction of body
    sr_ref: float = 0.15       # rad of bend that counts as full stretch
    ventral_tonic: float = 1.0  # L1 extrasynaptic ventral excitation (Lu et al. 2022)
    muscle_tau: float = 0.2    # s
    gain: float = 0.8          # rad at full activation difference
    nmj_taper: float = 0.6     # neuromuscular weight 0.7 * (1 - taper * x)

    @classmethod
    def for_stage(cls, label: str, **kw) -> "Circuit":
        if label == "L1":
            return cls("L1", n_dorsal=7, n_ventral=0, **kw)
        return cls("post-L1", n_dorsal=7, n_ventral=11, **kw)


@dataclass
class Compiled:
    """Integer constants for one circuit on one robot."""

    n_joints: int
    phi_max_mrad: int            # bend (mrad) that reads as unit stretch
    dorsal_pos: np.ndarray       # neuron positions along the body in [0,1)
    ventral_pos: np.ndarray
    d_field: list[np.ndarray]    # joint indices each neuron senses
    v_field: list[np.ndarray]
    d_gain: np.ndarray           # Q16 multipliers: sum(mrad) -> Q12 stretch
    v_gain: np.ndarray
    j_dorsal: np.ndarray         # nearest dorsal neuron per joint
    j_ventral: np.ndarray        # nearest ventral neuron per joint (-1 if none)
    v_cross: np.ndarray          # nearest dorsal neuron per ventral neuron
    nmj: np.ndarray              # per-joint output gain, mrad per Q15
    i_on: int
    i_bias: int
    w_sr: int
    tonic: int                   # Q15
    alpha: int                   # Q15 muscle filter coefficient
    stage: str


def _field(pos: float, n_joints: int, frac: float) -> np.ndarray:
    x = (np.arange(n_joints) + 1) / (n_joints + 1)
    idx = np.nonzero((x >= pos) & (x <= pos + frac))[0]
    return idx if idx.size else np.array([n_joints - 1])


def compile_circuit(c: Circuit, n_joints: int, dt: float, joint_max: float) -> Compiled:
    phi_max = int(round(c.sr_ref * 1000))  # stretch saturates the neuron at this bend
    dpos = (np.arange(c.n_dorsal) + 0.5) / c.n_dorsal
    vpos = (np.arange(c.n_ventral) + 0.5) / max(c.n_ventral, 1) if c.n_ventral else np.zeros(0)
    dfield = [_field(p, n_joints, c.field) for p in dpos]
    vfield = [_field(p, n_joints, c.field) for p in vpos]
    gain = lambda f: int(round(Q12 * 65536 / (len(f) * phi_max)))
    xj = (np.arange(n_joints) + 1) / (n_joints + 1)
    near = lambda pos, x: int(np.argmin(np.abs(pos - x)))
    nmj = 0.7 * (1 - c.nmj_taper * xj) / 0.7  # normalised so the head has weight 1
    return Compiled(
        n_joints, phi_max, dpos, vpos, dfield, vfield,
        np.array([gain(f) for f in dfield], np.int64),
        np.array([gain(f) for f in vfield], np.int64),
        np.array([near(dpos, x) for x in xj]),
        np.array([near(vpos, x) for x in xj]) if c.n_ventral else np.full(n_joints, -1),
        np.array([near(dpos, p) for p in vpos], dtype=int),
        np.round(nmj * c.gain * 1000).astype(np.int64),
        int(round(c.i_on * Q12)), int(round(c.i_bias * Q12)), int(round(c.w_sr * Q12)),
        int(round(np.clip(c.ventral_tonic, 0, 1) * Q15)),
        int(round(min(1.0, dt / c.muscle_tau) * Q15)),
        c.stage,
    )


@dataclass
class State:
    s_d: np.ndarray    # int8 0/1
    s_v: np.ndarray
    m_d: np.ndarray    # Q15 dorsal muscle activation per joint
    m_v: np.ndarray


def reset(k: Compiled) -> State:
    # break the symmetry the way a worm does at rest: the head starts bent
    s_d = np.zeros(len(k.dorsal_pos), np.int64)
    s_d[0] = 1
    return State(s_d, np.zeros(len(k.ventral_pos), np.int64),
                 np.zeros(k.n_joints, np.int64), np.zeros(k.n_joints, np.int64))


def _switch(s: np.ndarray, i: np.ndarray) -> np.ndarray:
    return np.where(i > ON, 1, np.where(i < OFF, 0, s))


def _stretch(phi_mrad: np.ndarray, fields, gains, sign: int) -> np.ndarray:
    out = np.empty(len(fields), np.int64)
    for n, (f, g) in enumerate(zip(fields, gains)):
        out[n] = (sign * int(phi_mrad[f].sum()) * int(g)) >> 16
    return out


def tick(k: Compiled, st: State, phi_mrad: np.ndarray) -> tuple[State, np.ndarray]:
    """One control tick. phi_mrad: int joint readings -> int joint targets (mrad).

    Positive joint angle is a ventral bend, which stretches the dorsal side.
    """
    phi = np.asarray(phi_mrad, np.int64)
    sd = _stretch(phi, k.d_field, k.d_gain, +1)
    i_d = k.i_on + ((k.w_sr * sd) >> 12)
    s_d = _switch(st.s_d, i_d)
    if len(k.ventral_pos):
        sv = _stretch(phi, k.v_field, k.v_gain, -1)
        i_v = k.i_bias - Q12 * s_d[k.v_cross] + k.i_on + ((k.w_sr * sv) >> 12)
        s_v = _switch(st.s_v, i_v)
        drive_v = Q15 * s_v[k.j_ventral]
    else:
        s_v = st.s_v
        # L1: tonic extrasynaptic excitation of ventral muscle, inhibited by DD,
        # which DB drives (DD innervates ventral muscle before rewiring)
        drive_v = np.maximum(0, k.tonic - Q15 * s_d[k.j_dorsal])
    drive_d = Q15 * s_d[k.j_dorsal]
    m_d = st.m_d + (((drive_d - st.m_d) * k.alpha) >> 15)
    m_v = st.m_v + (((drive_v - st.m_v) * k.alpha) >> 15)
    target = ((m_v - m_d) * k.nmj) >> 15
    return State(s_d, s_v, m_d, m_v), np.clip(target, -32768, 32767)
