"""Content-addressed experiment graphs.

A pipeline is a DAG of pure functions. Each node declares its inputs by
parameter name; an input is satisfied either by another node's output of the
same name or by a run parameter. A node's cache key is the hash of its own
code version and the keys of everything it reads, so changing one knob
re-runs exactly the nodes downstream of that knob and nothing else.

This is the same idea as a build system (Bazel, Make) applied to research:
the graph is the unit of reproducibility, not the notebook.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import pickle
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable


def stable_hash(obj: Any) -> str:
    """Hash plain data deterministically. Arrays hash by dtype, shape and bytes."""
    h = hashlib.sha256()
    _feed(h, obj)
    return h.hexdigest()[:16]


def _feed(h, obj: Any) -> None:
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        np = None
    if np is not None and isinstance(obj, np.ndarray):
        h.update(b"nd")
        h.update(str(obj.dtype).encode())
        h.update(str(obj.shape).encode())
        h.update(np.ascontiguousarray(obj).tobytes())
    elif isinstance(obj, dict):
        h.update(b"{")
        for k in sorted(obj, key=str):
            _feed(h, str(k))
            _feed(h, obj[k])
        h.update(b"}")
    elif isinstance(obj, (list, tuple)):
        h.update(b"[")
        for x in obj:
            _feed(h, x)
        h.update(b"]")
    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        h.update(json.dumps(obj).encode())
    else:
        h.update(repr(obj).encode())


@dataclass(frozen=True)
class Node:
    name: str
    fn: Callable[..., Any]
    inputs: tuple[str, ...]
    version: str
    cache: bool = True

    @property
    def code_hash(self) -> str:
        try:
            src = inspect.getsource(self.fn)
        except (OSError, TypeError):
            src = self.fn.__qualname__
        return stable_hash([self.version, src])


def node(name: str | None = None, *, version: str = "1", cache: bool = True):
    """Declare a pipeline stage. Inputs are the function's parameter names."""

    def wrap(fn: Callable[..., Any]) -> Node:
        params = tuple(inspect.signature(fn).parameters)
        return Node(name or fn.__name__, fn, params, version, cache)

    return wrap


@dataclass
class NodeRun:
    name: str
    key: str
    seconds: float
    cached: bool


@dataclass
class RunResult:
    values: dict[str, Any]
    params: dict[str, Any]
    trace: list[NodeRun] = field(default_factory=list)

    def __getitem__(self, k: str) -> Any:
        return self.values[k]

    @property
    def keys(self) -> dict[str, str]:
        return {t.name: t.key for t in self.trace}


class GraphError(RuntimeError):
    pass


class Graph:
    """A DAG of nodes resolved by name."""

    def __init__(self, nodes: Iterable[Node], cache_dir: str | Path | None = None):
        self.nodes: dict[str, Node] = {}
        for n in nodes:
            if n.name in self.nodes:
                raise GraphError(f"duplicate node {n.name!r}")
            self.nodes[n.name] = n
        self.cache_dir = Path(cache_dir) if cache_dir else None

    # -- structure -------------------------------------------------------
    def deps(self, name: str) -> list[str]:
        return [i for i in self.nodes[name].inputs if i in self.nodes]

    def free_params(self) -> set[str]:
        """Inputs no node produces: these must come from run parameters."""
        return {i for n in self.nodes.values() for i in n.inputs if i not in self.nodes}

    def order(self, targets: Iterable[str]) -> list[str]:
        seen: dict[str, int] = {}  # 1 = visiting, 2 = done
        out: list[str] = []

        def visit(n: str, stack: tuple[str, ...]) -> None:
            if n not in self.nodes:
                raise GraphError(f"unknown node {n!r}")
            state = seen.get(n)
            if state == 2:
                return
            if state == 1:
                raise GraphError("cycle: " + " -> ".join(stack + (n,)))
            seen[n] = 1
            for d in self.deps(n):
                visit(d, stack + (n,))
            seen[n] = 2
            out.append(n)

        for t in targets:
            visit(t, ())
        return out

    def levels(self, targets: Iterable[str]) -> list[list[str]]:
        """Topological order grouped into waves that can run concurrently."""
        order = self.order(targets)
        depth: dict[str, int] = {}
        for n in order:
            depth[n] = 1 + max((depth[d] for d in self.deps(n)), default=-1)
        waves: dict[int, list[str]] = {}
        for n in order:
            waves.setdefault(depth[n], []).append(n)
        return [waves[k] for k in sorted(waves)]

    def to_mermaid(self) -> str:
        lines = ["graph LR"]
        for n in self.nodes:
            for d in self.deps(n):
                lines.append(f"  {d} --> {n}")
            for p in self.nodes[n].inputs:
                if p not in self.nodes:
                    lines.append(f"  {p}([{p}]) -.-> {n}")
        return "\n".join(lines)

    # -- execution -------------------------------------------------------
    def run(self, targets: Iterable[str], params: dict[str, Any] | None = None,
            workers: int = 1) -> RunResult:
        params = dict(params or {})
        targets = list(targets)
        missing = {
            i for n in self.order(targets) for i in self.nodes[n].inputs
            if i not in self.nodes and i not in params
        }
        if missing:
            raise GraphError(f"missing run parameters: {sorted(missing)}")

        values: dict[str, Any] = {}
        keys: dict[str, str] = {}
        trace: list[NodeRun] = []

        def key_of(n: Node) -> str:
            parts = [n.code_hash]
            for i in n.inputs:
                parts.append(keys[i] if i in self.nodes else stable_hash(params[i]))
            return stable_hash(parts)

        def exec_one(name: str) -> tuple[str, Any, NodeRun]:
            n = self.nodes[name]
            k = key_of(n)
            path = self.cache_dir / f"{name}-{k}.pkl" if (self.cache_dir and n.cache) else None
            t0 = time.perf_counter()
            if path is not None and path.exists():
                with open(path, "rb") as f:
                    v = pickle.load(f)
                return name, v, NodeRun(name, k, time.perf_counter() - t0, True)
            args = {i: (values[i] if i in self.nodes else params[i]) for i in n.inputs}
            v = n.fn(**args)
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                with open(tmp, "wb") as f:
                    pickle.dump(v, f)
                tmp.replace(path)
            return name, v, NodeRun(name, k, time.perf_counter() - t0, False)

        for wave in self.levels(targets):
            for name in wave:  # keys depend only on earlier waves
                keys[name] = key_of(self.nodes[name])
            if workers > 1 and len(wave) > 1:
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    results = list(ex.map(exec_one, wave))
            else:
                results = [exec_one(n) for n in wave]
            for name, v, tr in results:
                values[name] = v
                trace.append(tr)
        return RunResult(values, params, trace)
