"""A language-model planner.

It reads the same ledger the other agents read — every run, its metrics, which
gates it failed, who proposed it and why — and proposes the next experiments
with a stated hypothesis for each. Its output is constrained to a JSON schema
built from the search space, then validated again locally; anything off-grid
is discarded and the slot is handed to a fallback agent. A planner that cannot
reach the API degrades to the fallback rather than stopping the campaign.
"""

from __future__ import annotations

import json
import os
from typing import Any, Sequence

from .agents import Decider, Objective, ParetoDecider, Proposal, Space, _key, _tried, validate
from .ledger import Entry

MODEL = "claude-opus-5"

SYSTEM = """You are the planning agent in an automated research harness.
You choose the next experiments to run. Each experiment is one point in a
discrete search space. You see the full history of runs: parameters, metrics,
gate verdicts (a failed gate means the run is inadmissible), which agent
proposed the run and its stated rationale.

Goal: move the Pareto frontier of the stated objectives using as few runs as
possible. Prefer runs that test a specific hypothesis about the history (for
example, that a failed gate is caused by one knob). Never propose a point that
has already been run. Every value must be one of the listed choices."""


def _history_table(space: Space, history: Sequence[Entry], objectives: Sequence[Objective],
                   limit: int = 200) -> str:
    rows = []
    for e in history[-limit:]:
        rows.append({
            "params": {k: e.params.get(k) for k in space},
            "metrics": {o.metric: e.metrics.get(o.metric) for o in objectives}
                       | {k: v for k, v in e.metrics.items() if isinstance(v, (int, float))},
            "failed_gates": [g for g, ok in e.gates.items() if not ok],
            "by": e.decided_by,
        })
    return json.dumps(rows, default=str)


def _schema(space: Space, k: int) -> dict[str, Any]:
    props = {}
    for name, choices in space.items():
        # enums must be homogeneous JSON; strings are the safe common type
        props[name] = {"type": "string", "enum": [str(c) for c in choices]}
    return {
        "type": "object",
        "properties": {
            "proposals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "params": {"type": "object", "properties": props,
                                   "required": list(space), "additionalProperties": False},
                        "hypothesis": {"type": "string"},
                    },
                    "required": ["params", "hypothesis"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["proposals"],
        "additionalProperties": False,
    }


class LLMDecider:
    """Planner backed by the Anthropic API; falls back to a Pareto walker."""

    name = "llm"

    def __init__(self, objectives: Sequence[Objective], goal: str = "",
                 model: str = MODEL, fallback: Decider | None = None, client: Any = None,
                 effort: str = "medium"):
        self.objectives = list(objectives)
        self.goal = goal
        self.model = model
        self.effort = effort
        self.fallback = fallback or ParetoDecider(objectives)
        self._client = client
        self.last_error: str | None = None

    @staticmethod
    def available() -> bool:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

    def _client_or_none(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError:
            self.last_error = "anthropic SDK not installed"
            return None
        self._client = anthropic.Anthropic()
        return self._client

    def _ask(self, space: Space, history: Sequence[Entry], k: int) -> list[dict[str, Any]]:
        client = self._client_or_none()
        if client is None:
            return []
        objectives = ", ".join(f"{'maximize' if o.maximize else 'minimize'} {o.metric}"
                               for o in self.objectives)
        prompt = (
            f"Objectives: {objectives}.\n"
            + (f"Context: {self.goal}\n" if self.goal else "")
            + f"Search space (knob -> allowed values, ordered): {json.dumps(space, default=str)}\n"
            f"History ({len(history)} runs, oldest first): "
            f"{_history_table(space, history, self.objectives)}\n\n"
            f"Propose exactly {k} new experiments."
        )
        resp = client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            thinking={"type": "adaptive"},
            system=SYSTEM,
            output_config={"effort": self.effort,
                           "format": {"type": "json_schema", "schema": _schema(space, k)}},
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason == "refusal":
            self.last_error = "refusal"
            return []
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return json.loads(text).get("proposals", []) if text else []

    def propose(self, space, history, k):
        raw: list[dict[str, Any]] = []
        try:
            raw = self._ask(space, history, k)
        except Exception as exc:  # network, auth, rate limit: degrade, don't stop
            self.last_error = f"{type(exc).__name__}: {exc}"
        tried = _tried(space, history)
        out: list[Proposal] = []
        for r in raw:
            p = validate(r.get("params", {}), space)
            if p is None or _key(p, space) in tried:
                continue
            tried.add(_key(p, space))
            out.append(Proposal(p, r.get("hypothesis", ""), self.name))
            if len(out) == k:
                break
        if len(out) < k:
            pending = list(history) + [Entry("_pending", q.params, {}) for q in out]
            for p in self.fallback.propose(space, pending, k - len(out)):
                p.decided_by = f"{self.name}->{p.decided_by or self.fallback.name}"
                out.append(p)
        return out
