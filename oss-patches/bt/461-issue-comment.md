# Comment for pmorissette/bt #461

This looks fixed on master by #530, which merged Sep 1 and says it fixes #461 in its description. Its regression test uses the same min/per-share/capped commission from this issue. I also ran a quick randomized check of `SecurityBase.allocate` on current master with this issue's commission (8,000 cases: integer and fractional positions, prices 0.05–250): no "not smooth" errors, and no buy spent more than its allocation. Could this be closed?
