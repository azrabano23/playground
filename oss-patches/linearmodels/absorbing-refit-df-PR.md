**Title:** BUG: Stop AbsorbingLS.fit from accumulating df_model across calls

**Body:**

`AbsorbingLS.fit` did `self._num_params += exog_resid.shape[1]` on every call. The absorbed-parameter count is set only once, in `_first_time_fit`, and later fits reuse the cached residualized data. So the second and later fits on the same model count the regressors again.

As a result, `df_model` grows by k (the number of regressors) on each refit and `df_resid` shrinks by k. That changes the t-based p-values when `debiased=True`, the F-statistic's `df_denom` and `rsquared_adj`. Params and the covariance are unaffected.

**Reproducer** (20 absorbed categories, 3 regressors, n = 200):

```python
mod = AbsorbingLS(y, x, absorb=absorb)
for cov_type in ("unadjusted", "robust", "unadjusted"):
    res = mod.fit(cov_type=cov_type, debiased=True)
    print(cov_type, res.df_model, res.df_resid, round(res.rsquared_adj, 4), round(res.pvalues["x2"], 6))
```

main:
```
unadjusted 22 178 0.5076 0.01654
robust 25 175 0.4991 0.011157
unadjusted 28 172 0.4904 0.016576
```

this PR:
```
unadjusted 22 178 0.5076 0.01654
robust 22 178 0.5076 0.011143
unadjusted 22 178 0.5076 0.01654
```

22 is the correct count: 3 regressors plus 20 categories, minus 1 because the constant is shared.

**Change**

`_num_params` now holds only the absorbed parameters. `fit` and `_f_statistic` add `params.shape[0]` locally instead of mutating the model.

**Tests**

- New `test_refit_does_not_change_df` in `linearmodels/tests/iv/test_absorbing.py`. It fails on main (`assert res.df_model == first.df_model`) and passes here.
- `pytest linearmodels/tests/iv/test_absorbing.py linearmodels/tests/iv/test_formulas.py`: 675 passed
- black, isort, ruff and flake8 are clean on the changed files

Separately, while looking at this I noticed that the debiased covariance in `AbsorbingLS` scales by n/(n-k) with k the number of non-absorbed regressors. `df_resid`, which is used for the t p-values, subtracts the absorbed parameters too. That may be part of #432, but it's a design question (Stata's `areg` counts the absorbed effects, `reghdfe` drops nested ones), so I haven't touched it here.
