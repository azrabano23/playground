# loopgraph

A harness for research that runs itself, and cannot quietly lie about what it found.

The three projects in this repository are built on it: `pocketpolicy` (shrinking robot
foundation policies onto microcontrollers), `wormstage` (compiling a nematode connectome at
every developmental stage into a snake-robot controller) and `myoedge` (on-device EMG decoding
for low-cost prosthetic hands). Each is a graph of pipeline stages; agents propose which
experiments to run; gates decide which results count; a ledger records all of it.

```
        ┌──────────────────────────── ledger.jsonl ◄───────────────────────────┐
        │  every run: params, metrics, gate verdicts, node keys, git rev,     │
        │  which agent proposed it and its stated hypothesis                   │
        ▼                                                                      │
   ┌─────────┐   proposals   ┌────────────┐   metrics   ┌────────┐   verdicts  │
   │ agents  │ ────────────► │   graph    │ ──────────► │ gates  │ ────────────┘
   │ grid    │               │ data→fit→  │             │ exact  │
   │ pareto  │               │ quant→emit │             │ budget │
   │ llm     │               │ →eval      │             │ floor  │
   └─────────┘               └────────────┘             └────────┘
                                   │ content-addressed cache: a changed knob
                                   │ re-runs only what is downstream of it
```

## Pieces

| module | what it is |
|---|---|
| `graph` | A DAG of pure functions resolved by parameter name. The cache key is the hash of the node's source code plus the keys of its inputs, so results are reproducible and incremental, like a build system. Independent nodes run in concurrent waves. |
| `ledger` | Append-only JSONL. Runs that fail a gate are kept and marked rejected, never dropped. A **claim** binds a number in a README to a ledger entry; `loopgraph claims` fails when the two disagree. |
| `agents` | Planners share one interface, `propose(space, history, k)`: `GridDecider` (the baseline to beat), `RandomDecider`, `ParetoDecider` (walks outward from the current multi-objective frontier one knob at a time) and `Committee` (several agents share a budget, and each run is attributed to its proposer). `Campaign` is the budgeted loop. |
| `llm` | A language-model planner behind the same interface. It sees the whole ledger, including failed gates and other agents' rationales, and answers in a JSON schema generated from the search space. Its answer is validated again locally. Off-grid points, repeats, refusals and network errors hand the slot to a Pareto fallback, so a campaign never stalls on the planner. |
| `int8` | Post-training int8 quantization of dense networks (per-channel weights, int32 accumulation, integer requantization), an exact integer reference in numpy, and a C99 emitter: no malloc, no floats in the forward pass. |
| `cgate` | Gates that execute. `bit_exact_mlp` compiles the emitted C with `-Wall -Wextra -Werror -pedantic`, runs it, and compares every output byte against the reference. |

## Why agents, and why gates

An agent that picks experiments is only useful if its picks are judged by something it cannot
argue with. Here that is the gate set, which is identical for every planner. The ledger records
who proposed what, so "did the LLM planner actually beat the grid?" is a query, not a feeling:

```
loopgraph show ledger.jsonl -e distill
loopgraph front ledger.jsonl -e distill -o success,flash_kb:min
loopgraph claims ledger.jsonl claims.json      # exit 1 if any README number is stale
```

The LLM planner is optional. Install with `pip install -e ".[llm]"` and set `ANTHROPIC_API_KEY`.
Without them, every campaign runs on the deterministic planners.

## Use

```python
from loopgraph import Graph, node, Ledger, Campaign, ParetoDecider, Objective, at_least

@node()
def model(width, data): ...

@node()
def score(model, data): ...

g = Graph([data, model, score], cache_dir=".loopgraph/cache")
L = Ledger("ledger.jsonl")

def execute(p):
    r = g.run(["score"], p)
    return r["score"], r.keys          # metrics, node keys for provenance

Campaign("exp", {"width": [8, 16, 32, 64]}, execute, L,
         ParetoDecider([Objective("acc"), Objective("kb", maximize=False)]),
         gates=[at_least("acc", 0.9)], budget=12).run()
```

`pip install -e ".[test]" && pytest` runs 25 tests. The C gates need a host C compiler.
