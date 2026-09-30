Same synthetic stream replayed into an L3_MBO book (BTreeMap storage on both builds): measures the cost of the storage enum dispatch on the unchanged L3 path. Method as in cachegrind.md.

| scenario | build | Ir/delta | D1 misses/delta | LL misses/delta |
|---|---|---|---|---|
| l3:10 | base | 1062 | 1.50 | 0.000 |
| l3:10 | new | 1070 | 1.50 | 0.000 |
| l3:100 | base | 1207 | 2.59 | 0.000 |
| l3:100 | new | 1218 | 2.59 | 0.000 |
