"""Evaluation over all 21 subjects, as a loopgraph graph.

Protocol (per subject): train on the five pre-shift repetitions; test on the
four post-shift sessions. In each session the first Hand_Close recording is
the calibration fist; it is excluded from testing for *every* method,
calibrated or not, so all methods are scored on identical data. Scores use
the integer decoder's classifier and the same majority vote as the device.
"""

from __future__ import annotations

import numpy as np

from loopgraph import Graph, node
from loopgraph.cgate import CGateError, cc

from .adapt import augment, estimate_shift, pattern, rotate
from .data import Recording, electrode_shift, subjects
from .deploy import Model, check_c
from .features import featurize, td, windows
from .model import fit_lda, fit_mlp, standardise

TRIALS = ["trial_1", "trial_2", "trial_3", "trial_4"]
STEP = 8  # 40 ms decision period


def voted(pred: np.ndarray, n: int) -> np.ndarray:
    out = np.empty_like(pred)
    for i in range(len(pred)):
        out[i] = np.argmax(np.bincount(pred[max(0, i - n + 1):i + 1], minlength=5))
    return out


def train(recs, classifier: str, window: int, seed: int):
    X, y = featurize(recs, window, STEP)
    mu, sd = standardise(X)
    Z = (X - mu) / sd
    if classifier == "lda":
        L = fit_lda(Z, y)
    else:
        L = fit_mlp(Z, y, hidden=int(classifier[3:]), seed=seed)
    return L, mu, sd, X


def evaluate_subject(s: int, window: int, vote: int, classifier: str, aug: float,
                     recal: int, seed: int = 0) -> dict:
    d = electrode_shift(s)
    L, mu, sd, X = train(augment(d["training"], aug), classifier, window, seed)
    m = Model.build(L, mu, sd, X, window, STEP, vote)
    ref = sum(pattern(r.emg) for r in d["training"] if r.label == 0)
    accs = []
    for t in TRIALS:
        recs = d[t]
        cal = next(r for r in recs if r.label == 0 and r.rep == 0)
        shift = estimate_shift(ref, cal.emg) if recal else 0
        hit = tot = 0
        for r in recs:
            if r is cal:
                continue
            emg = rotate(r.emg, -shift) if shift else r.emg
            F = np.array([td(w) for w in windows(emg, window, STEP)])
            if not len(F):
                continue
            p = voted(m.classify(F), vote)
            hit += int(np.sum(p == r.label))
            tot += len(p)
        accs.append(hit / max(tot, 1))
    return {"acc": float(np.mean(accs)), "flash": m.flash_bytes, "ram": m.ram_bytes,
            "latency_ms": m.latency_ms}


@node(version="2")  # shift estimate now rotates the pattern, not the samples
def per_subject(window, vote, classifier, aug, recal, seed):
    return {s: evaluate_subject(s, window, vote, classifier, aug, recal, seed)
            for s in subjects()}


@node(version="1")
def exact(window, vote, classifier, aug, seed):
    """Stream subject 0's first post-shift session through C and the reference."""
    if cc() is None:
        return None
    d = electrode_shift(0)
    L, mu, sd, X = train(augment(d["training"], aug), classifier, window, seed)
    m = Model.build(L, mu, sd, X, window, STEP, vote)
    m.shift = 3
    emg = np.concatenate([r.emg for r in d["trial_1"]])
    try:
        return int(check_c(m, emg)[0])
    except CGateError:
        return 0


@node(version="1")
def metrics(per_subject, exact):
    acc = np.array([v["acc"] for v in per_subject.values()])
    any_v = next(iter(per_subject.values()))
    m = {"acc_shift": float(acc.mean()), "acc_p10": float(np.percentile(acc, 10)),
         "acc_min": float(acc.min()), "subjects": len(acc),
         "latency_ms": any_v["latency_ms"], "flash_b": max(v["flash"] for v in per_subject.values()),
         "ram_b": any_v["ram"]}
    if exact is not None:
        m["bit_exact"] = exact
    m["per_subject"] = {str(k): round(v["acc"], 4) for k, v in per_subject.items()}
    return m


DEFAULTS = {"window": 40, "vote": 3, "classifier": "lda", "aug": 0.0, "recal": 0, "seed": 0}


def graph(cache_dir=".loopgraph/cache") -> Graph:
    return Graph([per_subject, exact, metrics], cache_dir=cache_dir)


def execute(params: dict, cache_dir=".loopgraph/cache"):
    r = graph(cache_dir).run(["metrics"], {**DEFAULTS, **params})
    return r["metrics"], r.keys
