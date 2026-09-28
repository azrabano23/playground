"""wormstage as a loopgraph graph.

    stage ─► brain(glu_sign) ─► command (forward / reverse, per stimulus)
                                   │
    circuit(stage, command, knobs) ┴─► robot run ─► gait metrics
                     └─► C emission ─► bit-exact gate
"""

from __future__ import annotations

import numpy as np

from loopgraph import Graph, node
from loopgraph.cgate import CGateError, cc

from .body import Snake
from .brain import stage_report
from .circuit import Circuit, compile_circuit
from .data import load
from .emit import check
from .gait import measure, run

DT = 0.02


@node(version="1")
def brain(stage, glu_sign):
    return stage_report(stage, glu_sign=glu_sign, n_null=1000)


@node(version="1")
def command(brain, stimulus):
    """Reverse if the stimulus biases the backward command neurons."""
    if stimulus == "none":
        return {"backward": False, "rev": 0.0}
    r = brain[f"{stimulus}_rev"]
    return {"backward": bool(np.isfinite(r) and r > 0), "rev": r}


@node(version="1")
def circuit(stage, command, ventral_tonic, w_sr, field):
    label = load(stage).label
    return Circuit.for_stage(label, backward=command["backward"], ventral_tonic=ventral_tonic,
                             w_sr=w_sr, field=field)


@node(version="1")
def gait(circuit, n_links, K, k_joint, T):
    snake = Snake(n_links=n_links, K=K, k_joint=k_joint)
    tr = run(circuit, snake, T=T, dt=DT)
    m = measure(tr)
    m["servos"] = n_links - 1
    # the recorded trajectory is what the C gate replays
    m["_phi_mrad"] = np.round(tr.phi[: int(8 / DT)] * 1000).astype(np.int16)
    return m


@node(version="1")
def exact(circuit, gait, n_links):
    if cc() is None:
        return None
    k = compile_circuit(circuit, n_links - 1, DT, 1.0)
    try:
        return int(check(k, gait["_phi_mrad"].astype(int))[0])
    except CGateError:
        return 0


@node(version="1")
def metrics(brain, command, gait, exact, stimulus):
    m = {k: v for k, v in gait.items() if not k.startswith("_")}
    m["reversal_index"] = command["rev"]
    m["reverses"] = int(command["backward"])
    if stimulus != "none":
        m["brain_z"] = brain[f"{stimulus}_z"]
        m["brain_p"] = brain[f"{stimulus}_p"]
    if exact is not None:
        m["bit_exact"] = exact
    return m


DEFAULTS = {"glu_sign": 1.0, "stimulus": "none", "ventral_tonic": 1.0, "w_sr": 1.0,
            "field": 0.5, "n_links": 12, "K": 40.0, "k_joint": 0.1, "T": 30.0}


def graph(cache_dir=".loopgraph/cache") -> Graph:
    return Graph([brain, command, circuit, gait, exact, metrics], cache_dir=cache_dir)


def execute(params: dict, cache_dir=".loopgraph/cache"):
    r = graph(cache_dir).run(["metrics"], {**DEFAULTS, **params})
    return r["metrics"], r.keys
