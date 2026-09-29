# OSS contribution drafts

Nothing in this folder has been posted anywhere. For each item:
1. Fork the upstream repo.
2. Apply the `.patch` with `git am` (add `--keep-cr` for pandas_market_calendars and FinancePy).
3. Rerun the tests yourself.
4. Post the issue or comment first where one is included, then open the PR.

Read each project's AI-assistance policy before you post: llama.cpp, Pinocchio and ArduPilot require disclosure, and nautilus_trader forbids naming AI tools anywhere in the PR.

## Hard contributions (each has a TALKING-POINTS.md)

| Folder | What it is | Do first |
|---|---|---|
| QuantLib-lbr/ | Jäckel "Let's Be Rational" Black implied-vol solver: ~1e-15 error, ~3x faster | Post issue.md; check against Jäckel's current LetsBeRational.7z; run tools/check_filelists.sh |
| nautilus_trader-4925/ | Allocation-free L2 book ladder: 0 allocs per delta, 12–29% fewer instructions | Post proposal-comment.md and wait for maintainer OK; sign CLA; run make pre-commit; no AI mentions |
| ompl-1362/ | OwenStateSpace root-finding: high-altitude failures go to 0, exact lengths | Post issue-comment.md; coordinate with #1470 (rebased diff included) |
| mujoco-3628/ | Newton line search at cone zone boundaries: false fixed points 590 → 0 | Sign Google CLA; post issue-comment.md; 3 stacked patches |
| pytrec_eval-mteb-3030/ | trec_eval uninitialised read + stale cache + use-after-free behind NDCG > 1 | Open the trec_eval PR, then pytrec_eval, then mteb; post issue-comment.md |
| llama.cpp-28963/ | Embedding-batch M-RoPE position over-read causing nondeterminism | Write your own PR text from NOTES (AI-written posts are banned); disclose AI; run full ctest |

## Bug-fix patches (each has -PR.md, and -issue.md if the bug was self-found)
- bt/rebalance-over-time-cash
- pandas_market_calendars/486 (CME) and ice-carter-2025
- FinancePy/uk-moved-bank-holidays and us-new-year-jan3
- exchange_calendars/300
- ffn/yearly-plot-freq
- skfolio/bodnar-okhrin-beta
- vectorbt/cvar-nan
- linearmodels/631, weighted-f-statistic and absorbing-refit-df
- arch/801: docs patch plus a proposal

## Issue comments only
- FinancePy 264/273
- bt 461 and 567
- skfolio 331
- vectorbt 809 and 810
- yfinance 2855
- arch 801
