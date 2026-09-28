# Comment for ranaroussi/yfinance #2855

I think I found the root cause. It can be reproduced offline, without MERKO.IS data.

The crash is in `_fix_prices_sudden_change`, in the per-range correction (dev `history.py` ~L3865):

```python
df2.iloc[r[0]:r[1], col_loc] = (df2.iloc[r[0]:r[1], col_loc] * m_rcp).round().astype('int')
```

This happens before the `f_na` / `[~f_na]` guard at the end of the function. The function only drops rows whose OHLC is NaN (`f_nan`). A row with valid prices but NaN `Volume` stays in `df2`. If that row falls in a range being split-corrected, `.astype('int')` raises. The same pattern appears at ~L3729/3731 (per-column correction) and ~L3905 (unit-switch revert).

Repro using the existing CNE.L fixture. The only change is NaN volume on the day that gets repaired:

```python
import numpy as np, pandas as pd, yfinance as yf
hist = yf.scrapers.history.PriceHistory(None, "CNE.L", "Europe/London", session=object())
df = pd.read_csv("tests/data/CNE-L-1d-bad-stock-split.csv", index_col="Date")
df.index = pd.to_datetime(df.index, utc=True)
df.loc[df.index[7], "Volume"] = np.nan   # 2023-05-09, the row the split repair rescales
hist._fix_bad_stock_splits(df, "1d", "Europe/London")
# pandas.errors.IntCastingNaNError: Cannot convert non-finite values (NA or inf) to integer...
```

Dropping `.astype('int')` from those lines and leaving the cast to the final block fixes it:

```python
if correct_volume:
    f_na = df2['Volume'].isna()
    if f_na.any():
        df2.loc[~f_na,'Volume'] = df2['Volume'][~f_na].round(0).astype('int')
```

With only the L3865 change, the repro returns the same repaired prices as `CNE-L-1d-bad-stock-split-fixed.csv`, and the NaN volume stays NaN. I didn't open a PR because this is assigned to you. I'm happy to send one with a regression test if you'd like.
