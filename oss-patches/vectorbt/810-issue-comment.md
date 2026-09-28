I looked into this and I don't think `Best Trade [%]` is wrong here; it's measuring something different from the "PnL %" column in the snippet.

In `Portfolio.stats()`, `Best Trade [%]` is `trades.returns.max() * 100`. Each trade's return is its PnL divided by the **entry value of that trade** (`size * entry_price`), not by the portfolio's initial capital. That's the `Return` column in `pf.trades.records_readable`. For shorts the sign of the price move is flipped first, but the denominator is the same (see `get_trade_stats_nb` in `vectorbt/portfolio/nb.py`).

The snippet ranks trades by `PnL / CAPITAL`, so the trade with the largest absolute PnL comes out on top. That doesn't have to be the trade with the largest return: a bigger position can earn more dollars at a lower percentage. It also explains why your number can be larger than the stats value. If trade 153's entry value was above ~1.245M, i.e. more than the 1M initial capital, which a short-only strategy can easily reach, then its PnL/1M = 1.157% while its PnL/entry value is below 0.929%.

Here's a quick way to check on your portfolio:

```python
t = pf.trades.records_readable
closed = t[t["Status"] == "Closed"]  # stats() excludes open trades by default
print(closed["Return"].max() * 100)  # should equal pf.stats()["Best Trade [%]"]
print(closed.loc[closed["Exit Trade Id"] == 153, ["Size", "Avg Entry Price", "PnL", "Return"]])
```

On a synthetic short-only portfolio (60 closed trades, varying sizes, fees=0.001) with vectorbt at `ceffc50`, `Best Trade [%]` was 2.881003 and `closed["Return"].max() * 100` was 2.881003 as well. For comparison, the same trade's PnL / initial capital was only 0.513%, because the denominators differ. Two more things to keep in mind:

- `stats()` counts only closed trades unless you pass `settings=dict(incl_open=True)`. `records_readable` includes the open trade too.
- If you want the "PnL as % of initial capital" view, that's `pf.trades.closed.pnl.max() / pf.init_cash * 100`.

About the missing trades on the plot: could you share a minimal reproducible example (data + signals)? #869 fixes a plotting error with non-finite open-trade returns, but that's an exception, not missing markers, so it may be something else.
