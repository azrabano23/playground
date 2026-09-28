**Title:** BUG: Fix model F-statistic in weighted panel models with a constant

**Body:**

`f_statistic` (the homoskedastic "Model F-statistic" in the summary) is wrong for weighted `PooledOLS`, `PanelOLS` and `BetweenOLS` fits that include a constant. Unweighted fits are not affected.

**Example**

```python
import numpy as np, pandas as pd, statsmodels.api as sm
from linearmodels import PooledOLS

rs = np.random.RandomState(0)
idx = pd.MultiIndex.from_product([range(30), range(8)])
x = pd.DataFrame({"const": 1.0, "x1": rs.standard_normal(240), "x2": rs.standard_normal(240)}, index=idx)
y = 1 + x.x1 - 0.5 * x.x2 + rs.standard_normal(240)
w = pd.Series(rs.uniform(0.5, 2, 240), index=idx)

PooledOLS(y, x, weights=w).fit().f_statistic.stat   # 94.2300 on main
sm.WLS(y, x, weights=w).fit().fvalue                # 92.1232
```

With the data from the new test (30 entities x 8 periods, 20% of rows dropped, uniform weights), comparing against an F-test built from `statsmodels.WLS`:

| model (weighted, with const) | main | this PR | WLS F-test |
|---|---|---|---|
| PooledOLS | 94.2300 | 92.1232 | 92.1232 |
| PanelOLS, entity effects | 74.4188 | 72.5450 | 72.5450 |
| BetweenOLS | 11.3737 | 11.3838 | 11.3838 |

On main you can also see the problem without any outside reference. With entity effects the constant is redundant, but dropping it changes the F-statistic, 74.42 with `const` and 72.55 without. The coefficients, standard errors and R² are the same in both fits.

**Cause**

In `_PanelModelBase._f_statistic`, the restricted (constant-only) model's residuals are built by subtracting a scalar from the weighted dependent variable:

```python
y - float(np.squeeze((root_w.T @ y) / (root_w.T @ root_w)))
```

In the weighted regression the constant column is `root_w`, not a column of ones. So the restricted residual has to be `y - root_w * c`. When all weights are 1 the two versions are the same, which is why unweighted results were right.

**Fix**

Multiply the projection coefficient by `root_w`. It is a one-line change.

**Tests**

- Added `test_f_statistic_weighted_with_constant` in `linearmodels/tests/panel/test_panel_ols.py`, parametrized over pooled and entity effects. It compares `f_statistic` with an F-test computed directly from weighted least squares, and checks that dropping the redundant constant under entity effects gives the same value. Both cases fail on main (62.26 vs 60.96 and 105.07 vs 99.51) and pass with the fix.
- `pytest linearmodels/tests/panel/test_pooled_ols.py test_between_ols.py test_random_effects.py test_results.py test_simulated_against_stata.py`: 656 passed, 57 skipped, 47 xfailed
- `pytest linearmodels/tests/panel/test_panel_ols.py test_firstdifference_ols.py test_fama_macbeth.py`: see below
- black, isort, ruff and flake8 are clean on the changed files

A related problem I noticed but left alone here: `RandomEffects` on an unbalanced panel also subtracts a scalar, but its transformed constant is `1 - theta_i`, not `root_w`. Its F-statistic is therefore slightly off too. For example, 72.02 vs 71.46 from OLS on the quasi-demeaned data. Fixing that needs the transformed constant column rather than `root_w`, so I kept it out of this change. I'm happy to follow up if that's wanted.
