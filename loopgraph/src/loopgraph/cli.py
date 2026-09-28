"""loopgraph command line: inspect ledgers and verify documented claims."""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from .agents import Objective, pareto_front
from .ledger import Ledger, load_claims, verify_claims


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def cmd_show(a) -> int:
    L = Ledger(a.ledger)
    es = L.entries(a.experiment)
    if not es:
        print("no entries")
        return 1
    metrics = a.metrics.split(",") if a.metrics else sorted({k for e in es for k in e.metrics})[:6]
    params = sorted({k for e in es for k in e.params})
    head = ["id", "by", *params, *metrics, "ok"]
    print("\t".join(head))
    for e in es[-a.tail:]:
        row = [e.id[:8], e.decided_by, *(_fmt(e.params.get(p)) for p in params),
               *(_fmt(e.metrics.get(m)) for m in metrics), "Y" if e.admitted else "n"]
        print("\t".join(row))
    by = Counter(e.decided_by for e in es)
    print(f"\n{len(es)} runs, {sum(e.admitted for e in es)} admitted; proposed by: "
          + ", ".join(f"{k}={v}" for k, v in by.most_common()))
    return 0


def cmd_front(a) -> int:
    L = Ledger(a.ledger)
    objs = []
    for spec in a.objectives.split(","):
        name, _, sense = spec.partition(":")
        objs.append(Objective(name, sense != "min"))
    front = sorted(pareto_front(L.entries(a.experiment), objs),
                   key=lambda e: e.metrics[objs[0].metric])
    for e in front:
        print(e.id[:8], e.decided_by, e.params,
              {o.metric: _fmt(e.metrics[o.metric]) for o in objs})
    return 0


def cmd_claims(a) -> int:
    L = Ledger(a.ledger)
    bad = 0
    for c, ok, got in verify_claims(L, load_claims(a.claims)):
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {c.id}: claimed {c.value} ± {c.tol}, ledger {got}"
              + (f"  ({c.text})" if c.text else ""))
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="loopgraph")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("show", help="tabulate ledger entries")
    s.add_argument("ledger")
    s.add_argument("-e", "--experiment")
    s.add_argument("-m", "--metrics", help="comma-separated metric names")
    s.add_argument("-n", "--tail", type=int, default=40)
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("front", help="print the Pareto frontier")
    s.add_argument("ledger")
    s.add_argument("-e", "--experiment", required=True)
    s.add_argument("-o", "--objectives", required=True, help="e.g. success,kb:min")
    s.set_defaults(fn=cmd_front)

    s = sub.add_parser("claims", help="verify documented numbers against the ledger")
    s.add_argument("ledger")
    s.add_argument("claims")
    s.set_defaults(fn=cmd_claims)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
