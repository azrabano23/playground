I don't think the RSI calculation is wrong. It's a different smoothing from the one TradingView uses.

TradingView's `ta.rsi` is Wilder's RSI. Average gain and loss go through an RMA (seeded with an SMA, then `alpha = 1/length`). By default, `vbt.RSI` uses a **simple** rolling mean of gains and losses (`ewm=False`, see `rsi_cache_nb` → `ma_nb` in `vectorbt/indicators/nb.py`). The docstring only links Investopedia and doesn't promise Wilder smoothing. `ewm=True` doesn't give you Wilder either, because `ewm_mean_nb` interprets `window` as a pandas-style **span** (`alpha = 2 / (window + 1)`). With `window=14`, that's `alpha = 2/15`, not `1/14`.

To get Wilder's smoothing, set `2 / (window + 1) = 1 / 14`, i.e. `window = 2*14 - 1 = 27` with `ewm=True`:

```python
rsi_tv = vbt.RSI.run(close, window=27, ewm=True).rsi   # Wilder / TradingView RSI(14)
```

I checked this against a hand-rolled Wilder RSI(14) that uses TradingView's RMA seeding, on a 500-bar random walk (vectorbt @ ceffc50):

| variant | max abs diff vs Wilder RSI(14), bars 200+ | 30/70 threshold crossings |
|---|---|---|
| `vbt.RSI.run(close, 14)` (SMA, default) | 23.07 | 25 |
| `vbt.RSI.run(close, 14, ewm=True)` | 15.83 | 34 |
| `vbt.RSI.run(close, 27, ewm=True)` | 0.000014 | 14 |
| Wilder reference | 0 | 14 |

The SMA and span-14 versions are much noisier and cross the 30/70 levels far more often, which probably explains most of the 90-vs-~21 trade gap. The only difference left is in the first bars, from the seed: pandas-style `adjust=False` starts from the first value, while TradingView seeds with an SMA. It dies out after a few dozen bars.

@polakowo, would a note in the `RSI` docstring on how to reproduce Wilder/TradingView help (or a `wilder`-style option)? I'm happy to send a small PR if you'd like one.
