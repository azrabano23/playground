# RebalanceOverTime ignores temp["cash"] after the first step

`Rebalance` supports `temp["cash"]` to hold back part of the strategy value. `RebalanceOverTime` passes it through only on the day new weights are set. `temp` is cleared every period, so later steps rebalance to the full-value targets and the strategy ends fully invested.

```python
import bt, pandas as pd

class SetCash(bt.Algo):
    def __call__(self, t):
        t.temp["cash"] = 0.75
        return True

idx = pd.date_range("2020-01-01", periods=60, freq="B")
data = pd.DataFrame({"a": 100.0}, index=idx)
s = bt.Strategy("s", [bt.algos.RunMonthly(), bt.algos.SelectAll(),
                      bt.algos.WeighSpecified(a=1.0), SetCash(),
                      bt.algos.run_always(bt.algos.RebalanceOverTime(n=2))])
r = bt.run(bt.Backtest(s, data, initial_capital=100000, integer_positions=False))
st = r.backtests["s"].strategy
print((st.data["cash"] / st.data["value"]).iloc[[1, 2, 3, 25, 50]].round(4).tolist())
# master: [0.875, 0.0, 0.0, 0.0, 0.0]   expected: [0.875, 0.75, 0.75, 0.75, 0.75]
```

With plain `Rebalance()` in place of `RebalanceOverTime`, the cash share stays at 0.75 as expected.
