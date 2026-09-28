"""Append-only experiment ledger, verification gates, and claim checking.

Every run the harness makes lands in a JSONL ledger with its parameters,
metrics, gate verdicts, node keys and the git revision. Nothing is edited in
place. A number that appears in a README is a *claim*; `verify_claims` checks
each claim against the ledger so documentation cannot drift away from what
was actually measured.
"""

from __future__ import annotations

import json
import math
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable


def git_rev(cwd: str | Path = ".") -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=cwd,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


# -- gates ----------------------------------------------------------------

@dataclass(frozen=True)
class Gate:
    """A named pass/fail check on a run's metrics.

    Gates are how the harness says "this result is admissible". A run that
    fails a gate still goes in the ledger, marked rejected, so failures are
    part of the record instead of silently discarded.
    """

    name: str
    check: Callable[[dict[str, Any]], bool]
    why: str = ""

    def __call__(self, metrics: dict[str, Any]) -> bool:
        try:
            return bool(self.check(metrics))
        except (KeyError, TypeError, ValueError):
            return False


def at_least(metric: str, value: float, why: str = "") -> Gate:
    return Gate(f"{metric}>={value}", lambda m: m[metric] >= value, why)


def at_most(metric: str, value: float, why: str = "") -> Gate:
    return Gate(f"{metric}<={value}", lambda m: m[metric] <= value, why)


def equals(metric: str, value: Any, why: str = "") -> Gate:
    return Gate(f"{metric}=={value}", lambda m: m[metric] == value, why)


# -- ledger ---------------------------------------------------------------

@dataclass
class Entry:
    experiment: str
    params: dict[str, Any]
    metrics: dict[str, Any]
    gates: dict[str, bool] = field(default_factory=dict)
    keys: dict[str, str] = field(default_factory=dict)
    decided_by: str = "human"
    rationale: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    t: float = field(default_factory=time.time)
    rev: str | None = None

    @property
    def admitted(self) -> bool:
        return all(self.gates.values())


def _jsonable(x: Any) -> Any:
    try:
        import numpy as np
        if isinstance(x, np.generic):
            return x.item()
        if isinstance(x, np.ndarray):
            return x.tolist()
    except ImportError:  # pragma: no cover
        pass
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, float) and not math.isfinite(x):
        return str(x)
    return x


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, e: Entry) -> Entry:
        if e.rev is None:
            e.rev = git_rev(self.path.parent if self.path.parent.exists() else ".")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(_jsonable(asdict(e)), sort_keys=True) + "\n")
        return e

    def entries(self, experiment: str | None = None) -> list[Entry]:
        if not self.path.exists():
            return []
        out = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                e = Entry(**d)
                if experiment is None or e.experiment == experiment:
                    out.append(e)
        return out

    def best(self, experiment: str, metric: str, maximize: bool = True,
             admitted_only: bool = True) -> Entry | None:
        es = [e for e in self.entries(experiment)
              if metric in e.metrics and (e.admitted or not admitted_only)]
        if not es:
            return None
        return (max if maximize else min)(es, key=lambda e: e.metrics[metric])

    def latest(self, experiment: str) -> Entry | None:
        es = self.entries(experiment)
        return es[-1] if es else None


def record(ledger: Ledger, experiment: str, params: dict[str, Any],
           metrics: dict[str, Any], gates: Iterable[Gate] = (),
           keys: dict[str, str] | None = None, decided_by: str = "human",
           rationale: str = "") -> Entry:
    verdicts = {g.name: g(metrics) for g in gates}
    return ledger.append(Entry(experiment, params, metrics, verdicts, keys or {},
                               decided_by, rationale))


# -- claims ---------------------------------------------------------------

@dataclass
class Claim:
    """A number stated in documentation, bound to where it came from.

    `select` picks the ledger entry: "latest" or "best:<metric>[:min]".
    """

    id: str
    experiment: str
    metric: str
    value: float
    tol: float = 0.0
    select: str = "latest"
    text: str = ""


def _pick(ledger: Ledger, c: Claim) -> Entry | None:
    if c.select == "latest":
        return ledger.latest(c.experiment)
    if c.select.startswith("best:"):
        parts = c.select.split(":")
        return ledger.best(c.experiment, parts[1], maximize=not (len(parts) > 2 and parts[2] == "min"))
    raise ValueError(f"bad claim selector {c.select!r}")


def verify_claims(ledger: Ledger, claims: Iterable[Claim]) -> list[tuple[Claim, bool, Any]]:
    out = []
    for c in claims:
        e = _pick(ledger, c)
        got = None if e is None else e.metrics.get(c.metric)
        ok = got is not None and abs(float(got) - c.value) <= c.tol
        out.append((c, ok, got))
    return out


def load_claims(path: str | Path) -> list[Claim]:
    with open(path) as f:
        return [Claim(**d) for d in json.load(f)]
