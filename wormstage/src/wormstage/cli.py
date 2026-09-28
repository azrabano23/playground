"""wormstage command line.

    wormstage develop     every stage: gait at rest, and the response to ASH
    wormstage ablate      L1 extrasynaptic ventral drive, 0 to 1
    wormstage medium      drag anisotropy sweep, L1 vs adult
    wormstage design      agents search for the fewest servos that keep the gait
    wormstage emit        write the C controller for one stage
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loopgraph import (Campaign, Committee, Ledger, Objective, ParetoDecider, RandomDecider,
                       at_least, equals, record)

from .data import load, stage_keys
from .pipeline import DEFAULTS, execute

KEEP = ("freq_hz", "wavelength_bl", "forward_bl_s", "symmetry", "undulating",
        "reversal_index", "brain_p", "bit_exact")


def _log(e):
    m = e.metrics
    print(f"[{e.decided_by:>8}] {e.params} ->",
          " ".join(f"{k}={m[k]:.3g}" if isinstance(m.get(k), float) else f"{k}={m.get(k)}"
                   for k in KEEP if k in m), flush=True)


def _sweep(L: Ledger, name: str, grid: list[dict]) -> None:
    done = {tuple(sorted(e.params.items())) for e in L.entries(name)}
    for p in grid:
        if tuple(sorted(p.items())) in done:
            continue
        m, k = execute(p)
        _log(record(L, name, p, m, keys=k, decided_by="design"))


def cmd_develop(a):
    grid = [{"stage": s, "stimulus": stim} for s in stage_keys() for stim in ("none", "ASH")]
    _sweep(Ledger(a.ledger), "develop", grid)
    return 0


def cmd_ablate(a):
    grid = [{"stage": "witvliet1", "ventral_tonic": v, "K": K}
            for v in (0.0, 0.25, 0.5, 0.75, 1.0) for K in (10.0, 40.0)]
    _sweep(Ledger(a.ledger), "ablate_tonic", grid)
    return 0


def cmd_medium(a):
    grid = [{"stage": s, "K": K} for s in ("witvliet1", "witvliet8")
            for K in (1.5, 3.0, 10.0, 20.0, 40.0)]
    _sweep(Ledger(a.ledger), "medium", grid)
    return 0


SPACE = {"n_links": [4, 5, 6, 8, 10, 12, 16], "field": [0.25, 0.5, 0.75],
         "w_sr": [0.65, 1.0, 1.5], "k_joint": [0.05, 0.1, 0.2]}
GATES = [equals("undulating", 1, "a coherent travelling wave"),
         at_least("symmetry", 0.7, "no one-sided curling"),
         equals("bit_exact", 1, "C controller matches the reference")]


def cmd_design(a):
    L = Ledger(a.ledger)
    objs = [Objective("forward_bl_s"), Objective("servos", maximize=False)]
    stage = a.stage

    def ex(p):
        return execute({**p, "stage": stage})

    Campaign(f"design_{stage}", SPACE, ex, L,
             Committee([ParetoDecider(objs, seed=a.seed), RandomDecider(a.seed)]),
             GATES, budget=a.budget, batch=4, on_entry=_log).run()
    return 0


def cmd_emit(a):
    from .circuit import Circuit, compile_circuit
    from .emit import emit
    c = Circuit.for_stage(load(a.stage).label, backward=a.backward)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for fn, text in emit(compile_circuit(c, a.n_links - 1, 0.02, 1.0), a.name).items():
        (out / fn).write_text(text)
    print(f"wrote {out}/{a.name}.[ch] for {a.stage} ({c.stage}, "
          f"{'backward' if a.backward else 'forward'})")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="wormstage")
    p.add_argument("--ledger", default="results/ledger.jsonl")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("develop", cmd_develop), ("ablate", cmd_ablate), ("medium", cmd_medium)):
        sub.add_parser(name).set_defaults(fn=fn)
    s = sub.add_parser("design")
    s.add_argument("--stage", default="witvliet8")
    s.add_argument("--budget", type=int, default=24)
    s.add_argument("--seed", type=int, default=0)
    s.set_defaults(fn=cmd_design)
    s = sub.add_parser("emit")
    s.add_argument("--stage", default="witvliet8")
    s.add_argument("--backward", action="store_true")
    s.add_argument("--n-links", type=int, default=DEFAULTS["n_links"])
    s.add_argument("--name", default="worm")
    s.add_argument("-o", "--out", default="out")
    s.set_defaults(fn=cmd_emit)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
