# L2 delta processing: baseline vs sorted ring-buffer ladder

- base: `develop` at b916d05 (unmodified library)
- new: the patch in `../l2-array-ladder.patch` on top of b916d05
- host: shared cloud VM, 4 vCPU Intel Xeon @ 2.10 GHz, Linux 6.18, rustc 1.98.1, `bench` profile
  (release + debuginfo, no LTO). Unrelated jobs kept the load average at ~40-55 during all runs,
  so wall-clock numbers are indicative; the cachegrind counts are deterministic and are the
  primary evidence.
- Both builds run the identical bench sources (public `OrderBook` API only).

## Workloads

- **synthetic depth N** (N = 10, 100, 500): 100k deltas from a seeded model of a book deeper than
  the published view, emitted as the diff of the top-N view per event. Event mix: 70% size change,
  10% new level, 10% cancel, 10% trade-through (all at geometric distance from the top). Resulting
  delta mix: ~21% Add / ~58% Update / ~21% Delete. Every replay starts with Clear + snapshot.
- **Bybit XRPUSDT orderbook.500 (real)**: `test_data/bybit/xrpusdt-ob500.data.zip` from the repo,
  1 snapshot + 49 delta messages = 3,967 deltas (25% snapshot adds, 74% updates, 0.5% deletes),
  replayed 200 times per measurement.

## Headline

| workload | Ir/delta base -> new (cachegrind) | mean ns/delta base -> new (average of 2 ABAB rounds) | allocs/delta after warm-up base -> new |
|---|---|---|---|
| synthetic depth 10 | 1055 -> 923 (-12.5%) | 93.6 -> 76.2 (-19%) | 0.42 -> 0 |
| synthetic depth 100 | 1204 -> 978 (-18.8%) | 109.0 -> 78.3 (-28%, noisy) | 0.46 -> 0 |
| synthetic depth 500 | 1261 -> 1006 (-20.2%) | 126.6 -> 97.2 (-23%) | 0.47 -> 0 |
| Bybit ob500 (real) | 1371 -> 977 (-28.7%) | 125.3 -> 86.4 (-31%) | 0.56 -> 0 |

Criterion (`book_l2_criterion`, 100k-delta stream per iteration, `--save-baseline`/`--baseline`):

| bench | base | new | change (95% CI) |
|---|---|---|---|
| apply_delta/10 | 9.976 ms (99.8 ns/delta) | 7.835 ms (78.4 ns/delta) | -21.5% [-23.8%, -18.8%] |
| apply_delta/100 | 11.075 ms (110.7 ns/delta) | 9.471 ms (94.7 ns/delta) | -14.5% [-16.9%, -11.8%] |

## Per-delta latency (ns, includes ~25 ns timer overhead; round 1 / round 2)

| workload | build | p50 | p90 | p99 | p99.9 |
|---|---|---|---|---|---|
| depth 10 | base | 117 / 125 | 180 / 190 | 243 / 307 | 540 / 568 |
| depth 10 | new | 107 / 107 | 138 / 134 | 209 / 188 | 387 / 344 |
| depth 100 | base | 125 / 124 | 222 / 224 | 332 / 355 | 536 / 601 |
| depth 100 | new | 122 / 109 | 174 / 164 | 293 / 321 | 629 / 506 |
| depth 500 | base | 150 / 147 | 289 / 286 | 472 / 498 | 935 / 3415 |
| depth 500 | new | 134 / 124 | 231 / 168 | 435 / 266 | 1110 / 445 |
| Bybit ob500 | base | 125 / 133 | 247 / 283 | 398 / 485 | 3178 / 4084 |
| Bybit ob500 | new | 122 / 123 | 140 / 144 | 228 / 256 | 638 / 891 |

p90/p99 improve consistently. p99.9 improves on the real data and depth 10, but at depth
100/500 it is within this machine's noise (one round better, one worse), so I do not claim it.
Max values (tens of microseconds to milliseconds) are scheduler preemption on the shared VM.

## Memory (live heap owned by the book after the first pass)

| workload | base KiB | new KiB | new warm-up allocations (whole first pass) |
|---|---|---|---|
| depth 10 | 8.4 | 11.8 | 50 |
| depth 100 | 107.8 | 112.2 | 418 |
| depth 500 | 553-586 | 562.3 | 2,024 |
| Bybit ob500 | 520.3 | 497.0 | 2,028 |

Roughly equal: the new ladder keeps a spare pool (high-water retention) but drops the B-tree
nodes. Base allocates ~0.4-0.6 times per delta forever; new allocates only while growing to the
high-water depth.

## Where the remaining time goes (depth 100, new build, `cachegrind_profile_depth100.md`)

| share | what |
|---|---|
| ~36% | SipHash in `BookLadder.cache: std HashMap<OrderId, BookPrice>` (`hash_one` + `Sip13::write`) |
| ~16% | ring-buffer binary search (`SortedLevels::find`) |
| ~11% | `IndexMap::insert_full` (size update inside the level) |
| rest | `apply_delta` / `increment` / ladder bookkeeping |

The biggest remaining cost is not allocation but hashing the price-derived order ID into the
std `HashMap` cache on every delta. For L2 that cache is redundant with the price (the ID is a
hash of the price), which makes it the natural follow-up.

## L3 path check (`cachegrind_l3_regression_check.md`)

Same stream into an `L3_MBO` book, which keeps `BTreeMap` storage on both builds: 1062 -> 1070
Ir/delta at depth 10 (+0.8%), 1207 -> 1218 at depth 100 (+0.9%). That is the cost of the storage
enum dispatch; D1 misses are unchanged.

## First prototype (kept for the record)

The first version stored levels in a `Vec` with the best price at the end. It was faster at
depth 10 (896 Ir/delta) but slower than baseline at depth 100 (1522) and badly so at depth 500
(3975 Ir/delta, 134 D1 misses/delta), because in an MBP-N feed levels enter and leave at the
published depth boundary on almost every price move, and that end sat at index 0, forcing a
shift of the whole array. The ring buffer moves only toward the nearer end.

## Reproduce

```bash
# worktrees: base at b916d05, new with the patch applied
BASE=/path/to/base NEW=/path/to/new ./run_benches.sh          # alloc/latency ABAB + criterion
BIN_BASE=... BIN_NEW=... BYBIT_OB500=/path/to/unzipped.data ./cachegrind.sh
```

Note: the repo's existing `book_iai` bench panics with iai 0.1.1 under valgrind 3.22
(`no entry found for key` while parsing cachegrind output), which is why the instruction counts
here come from driving cachegrind directly.
