# loopgraph

A small Python harness for running research experiments: you describe the
pipeline, planners choose which experiments to run next, and every number
you publish is checked against what was actually measured.

It runs [pocketpolicy](https://github.com/azrabano23/pocketpolicy),
[wormstage](https://github.com/azrabano23/wormstage) and
[myoedge](https://github.com/azrabano23/myoedge).

## Why

Two things go wrong in fast-moving research code: results that can't be
reproduced, and numbers in a README that no longer match the code. loopgraph
guards against both.

- **Cached pipeline.** Each step is a function. Change one setting and only
  the steps after it re-run.
- **Ledger.** Every run is saved to one file, including the ones that failed.
- **Planners.** A grid, a random search, a frontier-walker, or an optional
  LLM choose the next experiment. The ledger records which one proposed
  each run, so you can check whether the smart planner actually helped.
- **Gates.** Rules every result must pass, like "the C code matches the
  Python output byte for byte." Planners can't override them.
- **Claims.** `loopgraph claims` fails CI if a published number drifts from
  the ledger.

## Try it

```python
from loopgraph import Graph, node, Ledger, Campaign, ParetoDecider, Objective, at_least

@node()
def model(width, data): ...

@node()
def score(model, data): ...

g = Graph([data, model, score], cache_dir=".loopgraph/cache")

def execute(p):
    r = g.run(["score"], p)
    return r["score"], r.keys

Campaign("exp", {"width": [8, 16, 32, 64]}, execute, Ledger("ledger.jsonl"),
         ParetoDecider([Objective("acc"), Objective("kb", maximize=False)]),
         gates=[at_least("acc", 0.9)], budget=12).run()
```

```bash
pip install -e ".[test]" && pytest
loopgraph claims ledger.jsonl claims.json
```

The LLM planner is optional: `pip install -e ".[llm]"`, then set
`ANTHROPIC_API_KEY` and `LOOPGRAPH_LLM_MODEL`.
