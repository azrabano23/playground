**Title:** fix(moments): divide the Bodnar-Okhrin-Parolya beta by the target's norm

Fixes #<issue number once opened>

### Problem

`ShrunkMu(method=ShrunkMuMethods.BODNAR_OKHRIN)` computes

```python
self.beta_ = (1 - self.alpha_) * v / u      # u = ybar' S^-1 ybar
```

but eq. (7) of Bodnar, Okhrin and Parolya (2019) is

```
beta_hat = (1 - alpha_hat) * (ybar' S^-1 mu0) / (mu0' S^-1 mu0)       # v / w
```

It is also what the paper's first-order condition in beta gives: for a fixed alpha, the optimal beta projects onto the target in the S^-1 metric, so the denominator is the target's quadratic form. `alpha_` already matches eq. (6).

With a grand-mean target, `u > w` in practice, so `alpha_ + beta_ < 1` and `mu_` is pulled toward zero instead of toward the target. In a small Monte Carlo (p=20, n=60, 500 draws, the paper's loss `(mu_hat - mu)' Sigma^-1 (mu_hat - mu)`), the current code averages a loss of 0.144 and eq. (7) averages 0.095 when the target is exact. The sample mean alone gives 0.337.

With `vol_weighted_target=True`, `v == w` by construction, so eq. (7) gives `alpha_ + beta_ == 1`. On the S&P 500 test fixture, the current code gives `alpha_ + beta_ = -0.228 + 0.294 = 0.067`, which shrinks `mu_` almost to zero.

### Fix

One line: use `w` instead of `u`.

### Tests

- New `TestShrunkMu::test_bodnar_okhrin_matches_reference`, parametrized over `vol_weighted_target`, recomputes `alpha_`, `beta_` and `mu_` directly from eq. (6) and (7). For the vol-weighted target it also checks `alpha_ + beta_ == 1`.
- Updated the `BODNAR_OKHRIN` regression values in `test_shrinkage_mu`. The other methods are unchanged.

Before the fix (on `main` @ 808b75a):

```
test_bodnar_okhrin_matches_reference[False]  FAILED  beta_: ACTUAL 0.448611, DESIRED 0.805532
test_bodnar_okhrin_matches_reference[True]   FAILED  beta_: ACTUAL 0.294349, DESIRED 1.227693
test_shrinkage_mu                            FAILED  mu_[0]: 5.96e-05 vs 2.96e-04 ...
```

After (pip-installed editable env, Python 3.11, NumPy 2.4.6):

```
python -m pytest tests/test_moment/test_expected_returns/test_expected_returns.py -k "bodnar or shrinkage_mu"
3 passed
python -m pytest tests/test_moment src/skfolio/moments
551 passed, 28 errors   # all 28 errors are HTTP 403 while downloading the implied-vol / options datasets in my sandbox, and don't depend on this change
ruff check && ruff format --check   # clean
```

Reference: T. Bodnar, O. Okhrin, N. Parolya, "Optimal shrinkage estimator for high-dimensional mean vector", Journal of Multivariate Analysis 170 (2019), Theorem 3, eq. (6)-(7). arXiv:1610.09292.
