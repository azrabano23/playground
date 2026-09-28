"""The nerve ring as a signed graded network, one per developmental stage.

C. elegans neurons are mostly graded, not spiking, so a linear rate model is
the standard first approximation (e.g. Kunert et al. 2014). Structure and
sign come from data; nothing is fitted:

  sign(pre)  +1 acetylcholine, -1 GABA, `glu_sign` for glutamate (which is
             excitatory through GLR-1 on AVA and inhibitory through GluCl
             elsewhere, so it is a stated assumption, not a fact),
             0 for neurons with no known classical transmitter.
  chemical   each neuron's inputs normalised to unit total weight
  electrical gap-junction Laplacian, normalised the same way
  dynamics   x = A x + u  (steady state), with ||A||_inf <= gain < 1, which
             bounds the spectral radius without an eigendecomposition

Readout: the reversal index of a stimulus is the mean response of the
backward command interneurons (AVA, AVD, AVE) minus the forward ones (AVB,
PVC). Each stage is compared against degree-preserving shuffles of its own
chemical wiring, so a result is attributed to the wiring rather than to the
number of synapses.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .data import Stage, load, transmitter

BACKWARD = ("AVAL", "AVAR", "AVDL", "AVDR", "AVEL", "AVER")
FORWARD = ("AVBL", "AVBR", "PVCL", "PVCR")
STIMULI = {
    "ASH": ("ASHL", "ASHR"),     # nociception: avoidance, i.e. reversal
    "FLP": ("FLPL", "FLPR"),     # harsh nose touch: reversal
    "ALM": ("ALML", "ALMR"),     # anterior gentle touch: reversal
    "AWC": ("AWCL", "AWCR"),     # odour sensing
    "AFD": ("AFDL", "AFDR"),     # thermosensation
}


def signs(stage: Stage, glu_sign: float = 1.0) -> np.ndarray:
    out = np.zeros(len(stage.nodes))
    for i, n in enumerate(stage.nodes):
        t = transmitter(n)
        if "Acetylcholine" in t:
            out[i] = 1.0
        elif "GABA" in t:
            out[i] = -1.0
        elif "Glutamate" in t:
            out[i] = glu_sign
    return out


def _norm_rows(M: np.ndarray) -> np.ndarray:
    s = np.abs(M).sum(1, keepdims=True)
    return np.divide(M, s, out=np.zeros_like(M), where=s > 0)


@dataclass
class Brain:
    stage: Stage
    A: np.ndarray

    @classmethod
    def build(cls, stage: Stage, glu_sign: float = 1.0, gain: float = 0.9,
              gj_weight: float = 0.5, chemical: np.ndarray | None = None) -> "Brain":
        C = stage.chemical if chemical is None else chemical
        Wc = _norm_rows(C * signs(stage, glu_sign)[None, :])
        G = stage.electrical
        Lg = _norm_rows(G) - np.diag((_norm_rows(G)).sum(1))  # diffusive coupling
        A = (1 - gj_weight) * Wc + gj_weight * Lg
        norm = max(np.abs(A).sum(1).max(), 1e-9)
        return cls(stage, A * (gain / norm))

    def respond(self, drive: dict[str, float]) -> np.ndarray:
        u = np.zeros(len(self.stage.nodes))
        for n, v in drive.items():
            if n in self.stage.index:
                u[self.stage.index[n]] = v
        return np.linalg.solve(np.eye(len(u)) - self.A, u)

    def reversal_index(self, stimulus: str) -> float:
        return self.reversal_indices([stimulus])[stimulus]

    def reversal_indices(self, stimuli=tuple(STIMULI)) -> dict[str, float]:
        """All stimuli in one solve (columns of U are the stimuli)."""
        ix = self.stage.index
        U = np.zeros((len(self.stage.nodes), len(stimuli)))
        for j, s in enumerate(stimuli):
            for c in STIMULI[s]:
                if c in ix:
                    U[ix[c], j] = 1.0
        X = np.linalg.solve(np.eye(len(U)) - self.A, U)
        b = X[self.stage.ids(BACKWARD)].mean(0)
        f = X[self.stage.ids(FORWARD)].mean(0)
        return {s: (float(b[j] - f[j]) if U[:, j].any() else float("nan"))
                for j, s in enumerate(stimuli)}


def shuffle_chemical(C: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Degree-preserving null: permute the targets of all chemical edges.

    Every presynaptic neuron keeps its outputs (so its sign and total output),
    every postsynaptic neuron keeps its number of inputs; who connects to whom
    is randomised. Edges that would become self-loops are re-drawn.
    """
    post, pre = np.nonzero(C)
    w = C[post, pre]
    new = rng.permutation(post)
    for _ in range(100):
        bad = np.nonzero(new == pre)[0]
        if not len(bad):
            break
        other = rng.integers(0, len(new), len(bad))
        new[bad], new[other] = new[other], new[bad].copy()
    out = np.zeros_like(C)
    np.add.at(out, (new, pre), w)
    return out


def stage_report(key: str, glu_sign: float = 1.0, n_null: int = 100, seed: int = 0) -> dict:
    stage = load(key)
    brain = Brain.build(stage, glu_sign)
    rng = np.random.default_rng(seed)
    nulls = [Brain.build(stage, glu_sign, chemical=shuffle_chemical(stage.chemical, rng))
             for _ in range(n_null)]
    out = {"stage": key, "label": stage.label, "hours": stage.hours,
           "synapses": int(stage.chemical.sum()), "neurons": len(stage.nodes)}
    real = brain.reversal_indices()
    null_all = [b.reversal_indices() for b in nulls]
    for s in STIMULI:
        r = real[s]
        null = np.array([n[s] for n in null_all])
        out[f"{s}_rev"] = r
        if np.isfinite(r) and null.std() > 0:
            out[f"{s}_z"] = float((r - null.mean()) / null.std())
            out[f"{s}_p"] = float((np.sum(null >= r) + 1) / (len(null) + 1))
        else:
            out[f"{s}_z"] = float("nan")
            out[f"{s}_p"] = float("nan")
    return out
