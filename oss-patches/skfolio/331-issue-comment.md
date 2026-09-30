Thanks for the very thorough write-up, the simulation results on overlapping windows are convincing.

@guptahardik are you still planning to open the PR with your reference implementation? I'd be glad to help review or test it (e.g. checking that `lags=0` reproduces the current statistic, and the `holding_period_summary()` path with `evaluation_step=1`).

If you've moved on to other things and the maintainers are happy with the approach, I'm also happy to pick it up. In that case it would help to know which of your three options is preferred: a corrected `t_stat` by default, an extra `n_effective` column, or a docs-only note, and whether Hansen-Hodrick with a Newey-West fallback is acceptable when the HH variance comes out non-positive.
