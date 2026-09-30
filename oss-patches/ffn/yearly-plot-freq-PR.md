# Fix `freq="y"` shorthand in stats plots on pandas 3

## Problem

`PerformanceStats._get_series` and `GroupStats._get_series` turn the `"y"` shorthand into the `"a"` alias before calling `asfreq`. pandas 3 no longer accepts `"a"`/`"A"`, so `plot(freq="y")`, `plot_histogram(freq="y")` and the `GroupStats` plotting methods raise:

```
ValueError: Invalid frequency: a. Failed to parse with error message: ValueError("Invalid frequency: a. ...")
```

(On pandas 2.2.x it still works but warns that `"A"` is deprecated.)

## Fix

Map `"y"` to `_YearEnd`, which `core.py` already sets to `"YE"` on pandas >= 2.2 and `"Y"` on older versions. Two one-line changes, no behaviour change on older pandas.

## Evidence

Before (pandas 3.0.6):

```
>>> df["AAPL"].calc_stats().plot(freq="y")
ValueError: Invalid frequency: a. ...
```

After: the plot draws 10 year-end points for the test data, and `plot_histogram(freq="y")` and `GroupStats.plot(freq="y")` also work.

## Tests

Added `test_yearly_series_shorthand` in `tests/test_core.py`. It checks that `_get_series("y")` on both `PerformanceStats` and `GroupStats` matches `asfreq(_YearEnd, "ffill")`.

- Before the fix: `pytest tests/test_core.py -k yearly_series_shorthand` fails with `ValueError: Invalid frequency: a`
- After the fix: it passes
- `pytest tests`: 832 passed (Python 3.11, pandas 3.0.6)
- `ruff check ffn` and `ruff format --check ffn`: clean
