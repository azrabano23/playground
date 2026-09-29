**Title:** Model F-statistic is wrong for weighted PooledOLS/PanelOLS/BetweenOLS with a constant

When weights are used and the model has a constant, `res.f_statistic`, the homoskedastic "F-statistic" in the summary, does not match the usual WLS F-test. The p-value is off by the same amount. Unweighted fits are fine.

```python
import numpy as np, pandas as pd, statsmodels.api as sm
from linearmodels import PooledOLS, PanelOLS

rs = np.random.RandomState(0)
idx = pd.MultiIndex.from_product([range(30), range(8)])
x = pd.DataFrame({"const": 1.0, "x1": rs.standard_normal(240),
                  "x2": rs.standard_normal(240)}, index=idx)
y = 1 + x.x1 - 0.5 * x.x2 + np.repeat(rs.standard_normal(30), 8) + rs.standard_normal(240)
w = pd.Series(rs.uniform(0.5, 2, 240), index=idx)

print(PooledOLS(y, x, weights=w).fit().f_statistic.stat)  # 62.2621
print(sm.WLS(y, x, weights=w).fit().fvalue)               # 60.9588

# with entity effects the constant is redundant, yet it changes the F-stat
print(PanelOLS(y, x, entity_effects=True, weights=w).fit().f_statistic.stat)                 # 105.0662
print(PanelOLS(y, x[["x1", "x2"]], entity_effects=True, weights=w).fit().f_statistic.stat)   # 99.5064 (matches WLS)
```

The cause is in `_PanelModelBase._f_statistic`. It builds the restricted residual as `y - scalar`. In the weighted regression the constant column is `sqrt(w)`, so the residual should be `y - sqrt(w) * scalar`.
