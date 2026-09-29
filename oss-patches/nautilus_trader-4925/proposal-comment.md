I'd like to work on this. Before opening anything I built a prototype to check the idea holds up,
and I'd like your view on the approach before I turn it into a PR.

## What I tried

The public API hands out `&BookLevel` (`bids()`/`asks()`, PyO3, and the FFI `orderbook_bids`), so a
pure `bid_px[N]`/`bid_sz[N]` layout would need either an API change or materializing levels on
every read. Instead I swapped only the level container under `BookLadder`:

- `BookLadder.levels` becomes a small `LadderLevels` enum: `Tree(BTreeMap<BookPrice, BookLevel>)` for
  L1/L3 (unchanged) and `Sorted` for `L2_MBP`.
- `Sorted` is a `VecDeque<BookLevel>` kept sorted worst-to-best (best at the back), with binary search
  for lookups. An insert or removal only moves elements toward the nearer end, so churn at the top of
  the book and at the published depth boundary are both cheap.
- Removed levels go to a spare pool and get reused (`IndexMap::clear` keeps its capacity), so once the
  book has reached its maximum depth, adding and removing levels never touches the heap.
- All the `BookLadder` logic (cache, L1 batching, zero-size handling) stays shared. The diff to
  `ladder.rs` is ~10 lines: new levels go through `insert_new_level` and emptied ones through `discard`.
- The `analysis` helpers take `impl IntoIterator<Item = (&BookPrice, &BookLevel)>` instead of
  `&BTreeMap<..>`, which still accepts a `&BTreeMap` from existing callers.

A first version used a plain `Vec` with the best price at the end. It was fine at depth 10, but it used
about 3x the instructions per delta of the current code at depth 500. In an MBP-N feed a level enters or leaves at the depth
boundary on almost every price move, and in that layout the boundary sat at index 0. The ring
buffer fixed this.

## Equivalence

- A proptest replays random delta streams into the new L2 book and into an L2 book forced onto the
  old `BTreeMap` storage. After every operation it compares the full level lists at several depths,
  the ID cache, sequence/`ts_last`/`update_count`, BBO, integrity check, `pprint`, `to_deltas`,
  `range(..=bound)` (the FFI path), the quantity/avg-price/exposure queries (bit-for-bit), and the
  results of `apply_delta` and `clear_stale_levels`. The streams mix Add/Update/Delete/Clear, no-side
  deltas, zero sizes, snapshot/`F_LAST`/`F_MBP` flags, and crossed books. It runs 512 cases of up to
  200 ops each, and it caught a mutation I planted in the level-reuse path.
- All existing `nautilus-model` tests pass without changes (high-precision + defi and standard precision).
- A new integration test uses a thread-local counting allocator. It asserts 0 heap calls on a second
  pass over a stream with a snapshot rebuild and top-of-book churn, at depths 10 and 100. On current
  `develop`, the same test counts 2,132 and 3,060 heap calls.

## Numbers

These are from a shared 4 vCPU VM, `bench` profile, and the same bench sources on both builds.
The machine was busy, so the cachegrind counts are the most reliable numbers here.

| workload | instructions/delta | mean ns/delta | allocs/delta (steady state) |
|---|---|---|---|
| synthetic MBP-10 | 1055 -> 923 (-12%) | 94 -> 76 | 0.42 -> 0 |
| synthetic MBP-100 | 1204 -> 978 (-19%) | 109 -> 78 | 0.46 -> 0 |
| synthetic MBP-500 | 1261 -> 1006 (-20%) | 127 -> 97 | 0.47 -> 0 |
| Bybit XRPUSDT ob500 sample from `test_data` | 1371 -> 977 (-29%) | 125 -> 86 | 0.56 -> 0 |

Criterion on the new `book_l2_criterion` bench shows -21% at depth 10 and -14% at depth 100.
p90/p99 per-delta latency improves consistently. p99.9 improves on the Bybit data but is within
noise at depth 100/500 on this machine. Memory is about the same, because the spare pool replaces
the B-tree nodes. The L3 path is +0.9% instructions from the enum dispatch.

One thing the profile showed: after this change, about 36% of the remaining instructions per L2
delta are SipHash in `BookLadder.cache` (std `HashMap`). For L2 the key is just a hash of the price,
so that map is redundant with the level array. I left it alone to keep this change behaviour-identical,
but it could be a follow-up.

## Questions

1. **Shape:** is a storage enum inside `BookLadder` OK with you, or would you rather have a separate
   L2 ladder type, even if it duplicates some of the ladder logic?
2. **Capacity:** the prototype grows on demand and keeps its high-water capacity, so the first pass
   through a feed allocates and later ones don't. Should there also be a way to preallocate (for
   example `OrderBook::with_capacity`)? Or should memory be released on `reset()`? I'd avoid a fixed
   cap that drops deep levels, since that changes behaviour.
3. **Scope:** keep this PR to the storage change and do the L2 cache follow-up separately?

If this direction works for you, I'll open the PR with the tests and the bench.
