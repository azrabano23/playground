# Comment for pmorissette/bt #567

This was a real bug, and it's fixed on master by f76ca25 ("Fix cash-aware rebalancing", Sep 20). `Rebalance` now keeps `target.value` as the base and scales each child weight by `1 - cash`, rather than shrinking the base. Child weights are shares of total value, so repeated rebalances no longer eat into the reserve.

I checked with a strategy like yours: `RunMonthly` + `WeighSpecified(a=1.0)` + `temp["cash"] = 0.75` + `Rebalance`, 100k capital. The cash share at each month end was:

- before f76ca25: 0.74, 0.54, 0.40, 0.29, 0.21, 0.15
- current master: 0.74, 0.74, 0.74, 0.74, 0.74, 0.75

It isn't in a tagged release yet, as far as I can tell. Until it is, you can install from master. Could this be closed?
