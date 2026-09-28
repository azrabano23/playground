"""myoedge command line.

    myoedge fetch       clone the datasets at pinned commits
    myoedge compare     baseline vs augmentation vs one-fist recalibration
    myoedge campaign    agents search window/vote/classifier/augmentation
    myoedge emit        write the C decoder for one subject
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loopgraph import (Campaign, Committee, Ledger, Objective, ParetoDecider, RandomDecider,
                       at_most, equals, record)

from .pipeline import DEFAULTS, execute

GATES = [at_most("latency_ms", 300, "Englehart & Hudgins 2003: acceptable controller delay"),
         at_most("flash_b", 28 * 1024, "ATmega32U4 flash, less a 4 KB bootloader"),
         at_most("ram_b", 2048, "ATmega32U4 has 2.5 KB SRAM"),
         equals("bit_exact", 1, "C decoder matches the reference")]


def _log(e):
    m = e.metrics
    print(f"[{e.decided_by:>8}] {e.params} -> shift acc {m['acc_shift']:.3f} "
          f"(p10 {m['acc_p10']:.3f}, min {m['acc_min']:.3f}) {m['latency_ms']:.0f} ms "
          f"{m['flash_b']} B {'ok' if e.admitted else 'REJECTED'}", flush=True)


def cmd_fetch(a):
    from .data import fetch
    fetch()
    print("ok")
    return 0


def cmd_compare(a):
    L = Ledger(a.ledger)
    done = {tuple(sorted(e.params.items())) for e in L.entries("compare")}
    for clf in ("lda", "mlp16"):
        for aug, recal in ((0.0, 0), (1.0, 0), (0.0, 1), (1.0, 1)):
            p = {"classifier": clf, "aug": aug, "recal": recal}
            if tuple(sorted(p.items())) in done:
                continue
            m, k = execute(p)
            _log(record(L, "compare", p, m, GATES, keys=k, decided_by="design"))
    return 0


SPACE = {"window": [30, 40, 50, 60], "vote": [1, 3, 5, 7], "classifier": ["lda", "mlp16", "mlp32"],
         "aug": [0.0, 0.5, 1.0, 1.5], "recal": [0, 1]}


def cmd_campaign(a):
    L = Ledger(a.ledger)
    objs = [Objective(a.objective), Objective("latency_ms", maximize=False)]
    Campaign("design", SPACE, lambda p: execute(p), L,
             Committee([ParetoDecider(objs, seed=a.seed), RandomDecider(a.seed)]), GATES,
             budget=a.budget, batch=4, on_entry=_log).run()
    return 0


def cmd_emit(a):
    from .adapt import augment, estimate_shift, pattern
    from .data import electrode_shift
    from .deploy import Model, emit
    from .pipeline import STEP, train

    d = electrode_shift(a.subject)
    L, mu, sd, X = train(augment(d["training"], a.aug), a.classifier, a.window, 0)
    m = Model.build(L, mu, sd, X, a.window, STEP, a.vote)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for fn, text in emit(m).items():
        (out / fn).write_text(text)
    ref = sum(pattern(r.emg) for r in d["training"] if r.label == 0)
    (out / "calibration_ref.h").write_text(
        "/* per-channel sum |x| of the training fists; the device compares a new fist */\n"
        f"static const int32_t CAL_REF[8] = {{{', '.join(str(int(v)) for v in ref)}}};\n")
    print(f"wrote {out}/ ({m.flash_bytes} B weights, {m.ram_bytes} B RAM, "
          f"{m.latency_ms:.0f} ms decision delay)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="myoedge")
    p.add_argument("--ledger", default="results/ledger.jsonl")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch").set_defaults(fn=cmd_fetch)
    sub.add_parser("compare").set_defaults(fn=cmd_compare)
    s = sub.add_parser("campaign")
    s.add_argument("--budget", type=int, default=24)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--objective", default="acc_p10", choices=["acc_p10", "acc_shift"])
    s.set_defaults(fn=cmd_campaign)
    s = sub.add_parser("emit")
    s.add_argument("--subject", type=int, default=0)
    for k, v in DEFAULTS.items():
        if k not in ("seed", "recal"):
            s.add_argument(f"--{k}", type=type(v), default=v)
    s.add_argument("-o", "--out", default="out")
    s.set_defaults(fn=cmd_emit)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
