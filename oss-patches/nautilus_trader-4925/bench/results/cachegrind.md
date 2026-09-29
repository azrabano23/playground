Deterministic per-delta counts from cachegrind (valgrind 3.22, simulated caches), bench profile,
`(count(3 passes) - count(1 pass)) / (2 x deltas)` so stream generation and the warm-up pass cancel.
base = parent commit b916d05, v1 = sorted `Vec` (first prototype), v2 = sorted `VecDeque` (patch).

| scenario | deltas/pass | base Ir/delta | v1 Vec Ir/delta | v2 VecDeque Ir/delta | v2 vs base | base D1 miss/delta | v1 D1 | v2 D1 |
|---|---|---|---|---|---|---|---|---|
| synthetic depth 10 | 100,002 | 1055 | 896 | 923 | -12.5% | 1.50 | 1.50 | 1.50 |
| synthetic depth 100 | 100,002 | 1204 | 1522 | 978 | -18.8% | 2.59 | 2.11 | 2.52 |
| synthetic depth 500 | 100,000+ | 1261 | 3975 | 1006 | -20.2% | 3.12 | 134.57 | 3.01 |
| Bybit XRPUSDT ob500 (real, 50 msgs) | see alloc_latency.md | 1371 | 1627 | 977 | -28.7% | 9.11 | 14.54 | 7.26 |

LL (last-level) misses were ~0 for every case: all working sets fit in the simulated LL cache.

v1 kept the best price at the end of a `Vec`. That makes top-of-book churn cheap but puts the
published-depth boundary (where a level enters or leaves on almost every price move in an MBP-N
feed) at index 0, so each boundary change shifted the whole array of ~100-byte levels. v2 uses a
ring buffer, where an insert or removal moves only the elements toward the nearer end.
