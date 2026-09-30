## Summary

`RebalanceOverTime` ignores `temp["cash"]` after its first step. `Rebalance` documents `cash` as the share of value to hold back. But `RebalanceOverTime` only sees it on the day new weights arrive, because `temp` is cleared every period. From the second step onwards it rebalances towards the full-value targets, so the strategy ends up fully invested.

## Behavior

With `WeighSpecified(a=1.0)`, `temp["cash"] = 0.75` and `run_always(RebalanceOverTime(n=2))`, the cash share over the first few days is:

| | day 1 | day 2 | later |
|---|---|---|---|
| `Rebalance` | 0.75 | 0.75 | 0.75 |
| `RebalanceOverTime(n=2)`, master | 0.875 | **0.0** | **0.0** |
| `RebalanceOverTime(n=2)`, this PR | 0.875 | 0.75 | 0.75 |

Root cause: `RebalanceOverTime` saves `weights` for the whole plan but not `cash`. Also, `children[c].weight` is a share of total value while the targets are shares of the investable part. So even when a user sets `cash` every day, the first step interpolates between two different scales.

Fix: keep `cash` together with the weights when a new plan starts, and scale the targets by `1 - cash` before interpolating, as `Rebalance` does. `cash` is then removed from `temp` for the inner `Rebalance` call so the reserve isn't applied twice, and put back afterwards. Fixed-income strategies still ignore `cash`, as before. The docstring now lists `cash` as optional.

This is separate from #567, which is about plain `Rebalance` and is already fixed on master by f76ca25.

## Regression Evidence

New test `tests/test_algos.py::test_rebalance_over_time_keeps_cash_reserve` (1,000 capital, price 100, cash 0.75, n=2):

- master: fails on the second step, `assert np.float64(10.0) == 2.5` (all 1,000 invested)
- this branch: passes. Positions go 1.25 → 2.5 → 2.5 and cash ends at 750.

## Verification

- `python -m pytest tests` → 496 passed
- `python -m ruff check bt` and `python -m ruff format --check bt` → clean

## Scope

Changed files are limited to `bt/algos.py` and `tests/test_algos.py`.
