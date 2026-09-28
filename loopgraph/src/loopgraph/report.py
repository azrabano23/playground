"""Markdown tables from ledger entries, so reports are generated, not typed."""

from __future__ import annotations

from typing import Iterable, Sequence

from .ledger import Entry


def fmt(v, digits: int = 3) -> str:
    if isinstance(v, float):
        return f"{v:.{digits}g}" if abs(v) < 1e4 else f"{v:.0f}"
    return "" if v is None else str(v)


def table(entries: Iterable[Entry], params: Sequence[str], metrics: Sequence[str],
          headers: Sequence[str] | None = None, digits: int = 3) -> str:
    cols = list(params) + list(metrics)
    head = list(headers) if headers else cols
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(cols)]
    for e in entries:
        row = [fmt(e.params.get(p), digits) for p in params]
        row += [fmt(e.metrics.get(m), digits) for m in metrics]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)
