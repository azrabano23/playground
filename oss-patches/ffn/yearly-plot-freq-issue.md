# `plot(freq="y")` raises ValueError on pandas 3

`PerformanceStats` and `GroupStats` accept `freq="y"` as a shorthand for yearly data in `plot`, `plot_histogram`, `plot_scatter_matrix`, `plot_histograms` and `plot_correlation`. Internally `_get_series` rewrites `"y"` to `"a"`, which pandas 3 removed as a frequency alias (it was deprecated in 2.2), so every one of these calls fails:

```python
import ffn, pandas as pd
df = pd.read_csv("tests/data/test_data.csv", index_col=0, parse_dates=True)
df["AAPL"].calc_stats().plot(freq="y")
# ValueError: Invalid frequency: a. Failed to parse with error message: ...
```

pandas 3.0.6, ffn master (582998c). On pandas 2.2.x the same call still works but emits a FutureWarning about `"A"`.

`core.py` already defines `_YearEnd` ("YE" on pandas >= 2.2, "Y" before), so the shorthand could map to that.
