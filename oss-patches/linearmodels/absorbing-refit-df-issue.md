**Title:** AbsorbingLS: calling fit() more than once inflates df_model and changes p-values

Every call to `AbsorbingLS.fit()` adds the number of regressors to the model's internal parameter count again. The first fit is correct. Each later fit on the same model object reports a larger `df_model` and a smaller `df_resid`. Anything that depends on them changes too: t-based p-values when `debiased=True`, the F-statistic's denominator df, and `rsquared_adj`. The coefficients and covariance are not affected.

Refitting the same model with a different `cov_type` is a common thing to do, so this is easy to hit without noticing.

```python
import numpy as np, pandas as pd
from linearmodels.iv import AbsorbingLS

rs = np.random.RandomState(0)
n = 200
x = pd.DataFrame({"const": 1.0, "x1": rs.standard_normal(n), "x2": rs.standard_normal(n)})
y = x.x1 + rs.standard_normal(n)
absorb = pd.DataFrame({"cat": pd.Categorical(rs.randint(0, 20, n))})

mod = AbsorbingLS(y, x, absorb=absorb)
for cov_type in ("unadjusted", "robust", "unadjusted"):
    res = mod.fit(cov_type=cov_type, debiased=True)
    print(cov_type, res.df_model, res.df_resid, round(res.rsquared_adj, 4), round(res.pvalues["x2"], 6))
```

```
unadjusted 22 178 0.5076 0.01654
robust 25 175 0.4991 0.011157
unadjusted 28 172 0.4904 0.016576    <- same spec as the first fit, different df / adj. R2 / p-value
```

The cause is `self._num_params += exog_resid.shape[1]` in `AbsorbingLS.fit`. It mutates model state on every call, but the absorbed-parameter count is only computed once, in `_first_time_fit`.
