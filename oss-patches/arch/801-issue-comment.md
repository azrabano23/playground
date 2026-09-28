I looked into both points against current `main` (88ffcf8) and can confirm them in the code. Neither has a single obviously right fix, so here's a concrete proposal before anyone writes a large patch.

**1. BCa acceleration uses the IID jackknife for every bootstrap class**

`IIDBootstrap._bca_acceleration` calls `_loo_jackknife(func, nobs, ...)`, and `CircularBlockBootstrap`, `MovingBlockBootstrap` and `StationaryBootstrap` inherit it without overriding it. So `a` is identical whichever bootstrap you use. On a skewed AR(1) (n=500, phi=0.8, statistic = mean):

```
IIDBootstrap             _loo_jackknife(nobs=500)  a = 0.00615
CircularBlockBootstrap   _loo_jackknife(nobs=500)  a = 0.00615
StationaryBootstrap      _loo_jackknife(nobs=500)  a = 0.00615
MovingBlockBootstrap     _loo_jackknife(nobs=500)  a = 0.00615
delete-l (moving-block) jackknife, l=5             a = 0.00440
delete-l (moving-block) jackknife, l=20            a = 0.00211
```

(The last two rows come from a hand-rolled delete-a-block jackknife. They're only there to show the estimate depends on the choice, and I'm not proposing that exact formula.)

The acceleration is a skewness term built from the jackknife influence values (Efron 1987, JASA 82:171-185; Davison & Hinkley 1997, sec. 5.3). With dependent data the leave-one-out influence values don't capture the skewness of the sampling distribution. The natural replacement is Künsch's (1989, Ann. Statist. 17:1217-1241) delete-a-block jackknife. As mentioned above, though, second-order correctness of BCa-type intervals under the block bootstrap is only established for smooth functions of means (Götze & Künsch 1996, Ann. Statist. 24:1914-1933; see also Lahiri 2003, *Resampling Methods for Dependent Data*). Also, as noted in the issue, R's `boot.ci` has the same limitation. So it's a real modelling choice, not a straightforward bug fix.

Proposal (opt-in, no change to existing results):

- Add a private `_jackknife(func, extra_kwargs)` hook on `IIDBootstrap` (current LOO behaviour). Override it in `CircularBlockBootstrap` with a delete-`l` moving-block jackknife: `n - l + 1` overlapping blocks, with pseudo-values scaled as in Künsch (1989). Default `l` would be `block_size`, and for `StationaryBootstrap` the rounded expected block length.
- Expose it via `conf_int(..., method="bca", bca_jackknife="iid" | "block")`. The default stays `"iid"` for now. If you'd like to move the time-series classes to `"block"` later, that could go through a `FutureWarning`.
- Until then, document the current behaviour (small doc patch below).

**2. Studentized intervals reuse the outer block size in the inner bootstrap**

In `_construct_bootstrap_estimates`, the nested bootstrap is `self.clone(*pos_data, **kw_data, seed=...)`, and `CircularBlockBootstrap.clone` passes `self._parameters[0]` (the outer `block_size`). With `CircularBlockBootstrap(20, x)` and `method="studentized"`, every inner bootstrap uses block size 20. As the issue says (citing Lahiri 2003), the inner block length should grow more slowly than the outer one. I don't think there's a single automatic rule that's clearly correct here, so I'd make it user-controllable first:

- `conf_int(..., studentize_block_size: int | float | None = None)`. `None` keeps today's behaviour, and the argument is ignored for `IIDBootstrap` and when `std_err_func` is given. For `StationaryBootstrap` it is the expected block length of the inner bootstrap.
- `clone()` on the time-series classes gets an optional `block_size=` override so the nested bootstrap can be built with it. `optimal_block_length` could be suggested in the docs for picking a value.
- An automatic default (for example, rescaling the outer length by a power of n) could come later once there's agreement on the rate.

If this direction works for you, I'm happy to open a PR for (2) first, since it's small and purely additive, and then (1). In the meantime, I have a docs-only patch that states both caveats in `conf_int`'s docstring and in `doc/source/bootstrap/confidence-intervals.rst`.
