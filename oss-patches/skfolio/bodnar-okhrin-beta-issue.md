**Title:** [BUG] ShrunkMu BODNAR_OKHRIN uses the wrong denominator for beta_

### Describe the bug

`ShrunkMu(method=ShrunkMuMethods.BODNAR_OKHRIN)` computes the target intensity as

```python
self.beta_ = (1 - self.alpha_) * v / u
```

where `u = ybar' S^-1 ybar`, `v = ybar' S^-1 mu0` and `w = mu0' S^-1 mu0`
(`src/skfolio/moments/expected_returns/_shrunk_mu.py`).

Eq. (7) of Bodnar, Okhrin and Parolya (2019), "Optimal shrinkage estimator for high-dimensional mean vector" (JMVA, arXiv:1610.09292), divides by the target's quadratic form, not the sample mean's:

```
beta_hat = (1 - alpha_hat) * (ybar' S^-1 mu0) / (mu0' S^-1 mu0)      # = (1 - alpha) * v / w
```

This also follows from the paper's first-order condition in beta: for a given alpha, the loss-minimizing beta is `(mu0' S^-1 mu - alpha * mu0' S^-1 ybar) / (mu0' S^-1 mu0)`. `alpha_` already matches eq. (6). Only `beta_` is affected. (Riskfolio-Lib's `mean_vector(method="BOP")` has the same `/ (mu.T @ Sigma_inv @ mu)` line, which is probably where it came from.)

### Impact

With a grand-mean target, `u` is usually larger than `w`, so `alpha_ + beta_` comes out below one and `mu_` is pulled toward zero instead of toward the target. Monte Carlo check (p=20, n=60, 500 draws, Gaussian returns, loss `(mu_hat - mu)' Sigma^-1 (mu_hat - mu)` as in the paper):

| true mean | sample mean | current | eq. (7) |
|---|---|---|---|
| all assets equal (target is exact) | 0.337 | 0.144 | **0.095** |
| equal plus small noise | 0.337 | 0.211 | **0.174** |

In the first case the average `alpha_ + beta_` is 0.907 with the current code and 1.002 with eq. (7).

### To reproduce

```python
import numpy as np
from skfolio.datasets import load_sp500_dataset
from skfolio.preprocessing import prices_to_returns
from skfolio.moments import ShrunkMu, ShrunkMuMethods

X = prices_to_returns(load_sp500_dataset())
m = ShrunkMu(method=ShrunkMuMethods.BODNAR_OKHRIN).fit(X)
y = np.asarray(X).mean(axis=0)
b = m.mu_target_
Si = np.linalg.inv(m.covariance_estimator_.covariance_)
print(m.beta_, (1 - m.alpha_) * (y @ Si @ b) / (b @ Si @ b))
```

The two numbers differ. With the test fixture (S&P 500 data from 2014), `beta_` is 0.4486 but eq. (7) gives 0.8055.

### Expected behavior

`beta_ = (1 - alpha_) * v / w`. It's a one-line change, and I have a PR ready with a test against eq. (6) and (7).

### Versions

skfolio main @ 808b75a (v1.4.8), Python 3.11, NumPy 2.x.
