"""Agents that decide what to run next, and the loop that lets them.

The research loop is: an agent reads the ledger and proposes experiments; the
executor runs each proposal through the graph; gates judge the result; the
ledger records everything, including who proposed it and why. The agent sees
its own and other agents' failures on the next round.

Agents here are deliberately interchangeable. A grid, a Pareto-frontier
explorer and a language model all implement `propose`, so an LLM planner can
be swapped in or out without touching the pipeline, and its decisions are
judged by the same gates as everyone else's.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Protocol, Sequence

from .ledger import Entry, Gate, Ledger, record

Space = dict[str, list[Any]]
"""A search space: knob name -> ordered list of allowed values."""


@dataclass
class Proposal:
    params: dict[str, Any]
    rationale: str = ""
    decided_by: str = ""


@dataclass(frozen=True)
class Objective:
    metric: str
    maximize: bool = True

    def better(self, a: float, b: float) -> bool:
        return a > b if self.maximize else a < b


class Decider(Protocol):
    name: str

    def propose(self, space: Space, history: Sequence[Entry], k: int) -> list[Proposal]:
        ...


def _key(params: dict[str, Any], space: Space) -> tuple:
    return tuple(params.get(n) for n in space)


def _tried(space: Space, history: Sequence[Entry]) -> set[tuple]:
    return {_key(e.params, space) for e in history}


def validate(params: dict[str, Any], space: Space) -> dict[str, Any] | None:
    """Coerce a proposal onto the space; None if any knob is off-grid."""
    out = {}
    for n, choices in space.items():
        if n not in params:
            return None
        v = params[n]
        if v in choices:
            out[n] = v
            continue
        # tolerate "8" vs 8 and 0.1 vs 0.10000001 from text-producing agents
        match = [c for c in choices if str(c) == str(v)]
        if not match:
            try:
                match = [c for c in choices
                         if isinstance(c, (int, float)) and abs(float(c) - float(v)) < 1e-9]
            except (TypeError, ValueError):
                match = []
        if not match:
            return None
        out[n] = match[0]
    return out


def pareto_front(entries: Iterable[Entry], objectives: Sequence[Objective]) -> list[Entry]:
    es = [e for e in entries if e.admitted and all(o.metric in e.metrics for o in objectives)]

    def dominates(a: Entry, b: Entry) -> bool:
        ge = all(not o.better(b.metrics[o.metric], a.metrics[o.metric]) for o in objectives)
        gt = any(o.better(a.metrics[o.metric], b.metrics[o.metric]) for o in objectives)
        return ge and gt

    return [e for e in es if not any(dominates(o, e) for o in es if o is not e)]


class GridDecider:
    """Exhaustive, in space order. The honest baseline every agent must beat."""

    name = "grid"

    def propose(self, space, history, k):
        tried = _tried(space, history)
        out = []
        for combo in itertools.product(*space.values()):
            if combo in tried:
                continue
            out.append(Proposal(dict(zip(space, combo)), "next untried grid point", self.name))
            if len(out) == k:
                break
        return out


class RandomDecider:
    name = "random"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def propose(self, space, history, k):
        tried = _tried(space, history)
        total = 1
        for v in space.values():
            total *= len(v)
        out: list[Proposal] = []
        seen = set(tried)
        for _ in range(50 * k):
            if len(out) == k or len(seen) >= total:
                break
            p = {n: self.rng.choice(v) for n, v in space.items()}
            if _key(p, space) in seen:
                continue
            seen.add(_key(p, space))
            out.append(Proposal(p, "random draw", self.name))
        return out


class ParetoDecider:
    """Walk outward from the current Pareto frontier one knob-step at a time.

    Multi-objective problems like accuracy-vs-flash have no single best run,
    only a frontier. This agent spends its budget on the neighbours of
    frontier points, which is where the frontier can move.
    """

    name = "pareto"

    def __init__(self, objectives: Sequence[Objective], seed: int = 0):
        self.objectives = list(objectives)
        self.rng = random.Random(seed)
        self.fallback = RandomDecider(seed)

    def propose(self, space, history, k):
        front = pareto_front(history, self.objectives)
        tried = _tried(space, history)
        cands: list[Proposal] = []
        seen = set(tried)
        for e in sorted(front, key=lambda e: e.t):
            for n, choices in space.items():
                if e.params.get(n) not in choices:
                    continue
                i = choices.index(e.params[n])
                for j in (i - 1, i + 1):
                    if 0 <= j < len(choices):
                        p = dict(e.params)
                        p[n] = choices[j]
                        p = {m: p[m] for m in space}
                        if _key(p, space) not in seen:
                            seen.add(_key(p, space))
                            desc = ", ".join(f"{o.metric}={e.metrics[o.metric]:.4g}"
                                             for o in self.objectives)
                            cands.append(Proposal(
                                p, f"neighbour of frontier run {e.id} ({desc}): {n} "
                                   f"{e.params[n]} -> {choices[j]}", self.name))
        self.rng.shuffle(cands)
        out = cands[:k]
        if len(out) < k:
            for p in self.fallback.propose(space, list(history) + [Entry("_", q.params, {}) for q in out],
                                           k - len(out)):
                p.decided_by = self.name
                p.rationale = "frontier exhausted or empty; exploring at random"
                out.append(p)
        return out


class Committee:
    """Several agents share one budget; each round, each gets a turn.

    The ledger records which agent proposed each run, so after a campaign you
    can ask which planner actually moved the frontier.
    """

    name = "committee"

    def __init__(self, members: Sequence[Decider]):
        self.members = list(members)

    def propose(self, space, history, k):
        out: list[Proposal] = []
        pending = list(history)
        i = 0
        while len(out) < k and i < 4 * k * max(1, len(self.members)):
            m = self.members[i % len(self.members)]
            i += 1
            got = m.propose(space, pending, 1)
            if not got:
                continue
            p = got[0]
            p.decided_by = p.decided_by or m.name
            if _key(p.params, space) in _tried(space, pending):
                continue
            out.append(p)
            pending.append(Entry("_pending", p.params, {}))
        return out


@dataclass
class Campaign:
    """A budgeted research loop: propose -> execute -> gate -> record -> repeat."""

    experiment: str
    space: Space
    execute: Callable[[dict[str, Any]], dict[str, Any] | tuple[dict[str, Any], dict[str, str]]]
    ledger: Ledger
    decider: Decider
    gates: list[Gate] = field(default_factory=list)
    budget: int = 20
    batch: int = 4
    on_entry: Callable[[Entry], None] | None = None

    def run(self) -> list[Entry]:
        made: list[Entry] = []
        while len(made) < self.budget:
            history = self.ledger.entries(self.experiment)
            want = min(self.batch, self.budget - len(made))
            props = []
            for p in self.decider.propose(self.space, history, want):
                v = validate(p.params, self.space)
                if v is not None and _key(v, self.space) not in _tried(self.space, history):
                    p.params = v
                    props.append(p)
            if not props:
                break  # the agent has nothing left to try
            for p in props:
                out = self.execute(p.params)
                metrics, keys = out if isinstance(out, tuple) else (out, {})
                e = record(self.ledger, self.experiment, p.params, metrics, self.gates,
                           keys=keys, decided_by=p.decided_by or self.decider.name,
                           rationale=p.rationale)
                made.append(e)
                if self.on_entry:
                    self.on_entry(e)
                history = history + [e]
        return made
