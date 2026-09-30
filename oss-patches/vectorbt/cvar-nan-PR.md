**Title:** fix(returns): exclude NaNs from the tail size in cond_value_at_risk

### Problem

`cond_value_at_risk_1d_nb` takes the cutoff index from `len(returns)`, NaNs included, and `np.partition` puts the NaNs last. The Rust kernel deliberately does the same thing so the two engines match. The result is that each NaN makes the tail one observation larger:

```python
sr = pd.Series(np.linspace(-0.1, 0.09, 20))
sr_nan = pd.concat((pd.Series([np.nan]), sr), ignore_index=True)   # leading NaN, as after pct_change()

sr.vbt.returns(freq="d").cond_value_at_risk(cutoff=0.05)      # -0.1
sr_nan.vbt.returns(freq="d").cond_value_at_risk(cutoff=0.05)  # -0.095 before, -0.1 after

pd.Series([np.nan] * 30 + [-0.1]).vbt.returns(freq="d").cond_value_at_risk(cutoff=0.05)  # nan before, -0.1 after
```

`value_at_risk_1d_nb` and `tail_ratio_1d_nb` already drop NaNs before computing quantiles. CVaR didn't.

### Fix

- `vectorbt/returns/nb.py`: filter out NaNs first, then run the existing empty check, cutoff index and partition.
- `rust/src/returns.rs`: same filter as `value_at_risk_1d`. With NaNs gone, the NaN-aware comparator isn't needed, so it becomes a plain `partial_cmp` and the unused `Ordering` import is dropped.

NaN-free inputs give the same results as before. None of the existing expected values change.

### Tests

- `tests/test_returns.py::TestAccessors::test_cond_value_at_risk_ignores_nan`: covers the leading-NaN case, equality with the NaN-free series, and the mostly-NaN case. I used `np.testing.assert_allclose` because `tests.utils.isclose` returns `True` for any two non-NaN numbers (see note below).
- `tests/test_engine.py::TestReturnsRustParity::test_dispatch_drawdown_edges`: checks the Numba result on a NaN-containing 2D array, plus Rust/Numba parity on it.

Before (master @ ceffc50, both engines unpatched):

```
FAILED tests/test_returns.py::TestAccessors::test_cond_value_at_risk_ignores_nan    ACTUAL -0.095, DESIRED -0.1
FAILED tests/test_engine.py::TestReturnsRustParity::test_dispatch_drawdown_edges    ACTUAL [-0.095, nan], DESIRED [-0.1, -0.1]
```

After (Rust extension rebuilt with `maturin develop --release`):

```
python -m pytest tests/test_returns.py tests/test_engine.py
128 passed
black --check (line-length 120) and cargo fmt --check: clean
```

### Side note, not in this PR

`tests/utils.py::isclose` starts with `if np.isnan(a) == np.isnan(b): return True`, which is true whenever neither value is NaN. Every `assert isclose(...)` on finite numbers therefore passes no matter what the values are. Happy to open a separate issue if that's useful.
