# Study guide: allocation-free L2 order book deltas (nautilus_trader #4925)

This is for you, not for GitHub. It explains every decision in the prototype so you can defend
it in review or in an interview. Numbers are in the "Results" section and come from
`bench/results/`.

## 1. The problem in one paragraph

`OrderBook` uses one `BookLadder` per side for every book type. Each ladder is a
`BTreeMap<BookPrice, BookLevel>` plus a `HashMap<OrderId, BookPrice>` cache, and each
`BookLevel` owns an `IndexMap<OrderId, BookOrder>` so L3 (market-by-order) books keep FIFO
queue position. An L2 (market-by-price) book has exactly one synthetic "order" per level (its
ID is a hash of the price), so it never needs the FIFO map, yet it pays for it: every time a
price level appears, a new `IndexMap` is allocated (two heap blocks: the hash index and the
entries vector) and a `BTreeMap` slot is inserted (sometimes a new ~1 KiB node); every time a
level disappears, those are freed again. In a real MBP feed, levels enter and leave all the time
(the top of book moves, levels drop out of the published depth), so the steady state is a
constant malloc/free churn on the hottest path in the system.

## 2. Why BTreeMap hurts on this path

- **Allocation.** `malloc`/`free` are tens of nanoseconds on a good day, and they are the source
  of the latency *tail*: occasionally the allocator takes a slow path (refilling a thread cache,
  coalescing, a page fault on fresh memory, or contention with another thread). A hot path that
  allocates therefore has a worse p99/p99.9 than its mean suggests.
- **Pointer chasing.** A B-tree lookup walks root -> child -> leaf. Each hop is a dependent load:
  the CPU cannot start fetching the child until it has read the parent. If a node is not in
  cache, that is a full memory latency (~80-100 ns) per level of the tree.
- **Poor locality of the payload.** The keys live in the tree node, but each `BookLevel`'s
  orders live in a separate heap block (the `IndexMap`), so reading "best bid size" touches the
  node and then another allocation somewhere else in the heap.
- **Generic comparisons.** Within a node the search is linear over up to 11 keys, and every
  `BookPrice` comparison asserts both sides match before comparing prices.
- **Churn fragments the heap** over hours of running, which slowly degrades locality further.

None of this matters for correctness, and for L3 the B-tree is the right tool (thousands of
levels, arbitrary insert positions, FIFO queues).

## 3. Why sorted arrays win for L2 depth distributions

- **Bounded depth.** MBP feeds publish a fixed depth (10, 20, 50, 400, 500 levels). The whole
  side fits in a few KiB to a few tens of KiB, i.e. in L1/L2 cache.
- **Skewed access, at both ends.** Most updates hit the top few levels, but in an MBP-N feed
  levels also enter and leave at the *published depth boundary* on nearly every price move (the
  11th level becomes visible, the 10th drops out). The prototype stores each side worst-to-best
  in a `VecDeque` (ring buffer): `insert`/`remove` move only the elements between the position
  and the *nearer* end, so churn at the top and at the bottom are both a few element moves, and
  the best price is `levels.back()`.
- **Lesson from v1:** the first version used a `Vec` with the best price at the end. Great for
  top-of-book churn, but the depth boundary was at index 0, so every boundary change shifted the
  whole array (500 levels x ~100 bytes = ~50 KB memmove). Cachegrind: 3,975 instructions and 134
  L1 data misses per delta at depth 500, vs 1,261 / 3.1 for the old BTreeMap. The ring buffer
  brought it to 1,006 / 3.0. This is the best war story in the project: measure the real access
  pattern, not the one you assumed.
- **Binary search over contiguous memory** has no dependent pointer loads beyond the array
  itself, and the hardware prefetcher handles the rest. For 10-100 levels that is 4-7
  comparisons, all likely in L1.
- **Reuse instead of free.** Removed levels go to a spare pool (`Vec<BookLevel>`); new levels
  take one from the pool and `clear()` its `IndexMap` (which keeps its capacity). After the book
  has once reached its maximum depth, no delta allocates or frees.

## 4. Complexity trade-offs (be ready to say where arrays lose)

| Operation | BTreeMap ladder | Sorted-array ladder |
|---|---|---|
| Find level | O(log n), pointer chasing | O(log n), contiguous |
| Size update at existing level | O(log n) | O(log n) |
| Insert/remove level at position k | O(log n) + allocation | O(log n) + O(min(k, n-k)) element moves, no allocation |
| Insert/remove in the *middle* of a deep book | O(log n) | O(n/2) moves (worst case) |
| Best price | O(log n) (leftmost leaf) | O(1) |
| Iterate top N | O(N) node walking | O(N) contiguous |
| Memory | allocated per level, freed on removal | high-water capacity retained |

The honest weak spots: (a) a very deep book (thousands of levels) with churn in the *middle*
moves a lot of memory per insert, since `BookLevel` is ~100 bytes; (b) the spare pool keeps
memory after a depth spike; (c) the array is still AoS (array of `BookLevel` structs), so the
binary search touches ~100-byte strides, not a dense `[i64]` price array like the issue sketch.
That is a deliberate compromise to keep the public API (next point).

## 5. The key design decision: storage inside `BookLadder`, not a new book type

`OrderBook::bids()`/`asks()` return `impl Iterator<Item = &BookLevel>`, and `BookLevel` is exposed
to Python (PyO3 class) and C (FFI `orderbook_bids` returns cloned `BookLevel`s). A pure
struct-of-arrays `bid_px[N]`/`bid_sz[N]` layout (the issue's sketch) has no `BookLevel` objects
to hand out by reference, so it would force either an API change or materializing levels on
every read. The prototype instead:

- adds `LadderLevels`, an enum with a `Tree(BTreeMap)` backend (L1, L3) and a `Sorted`
  (`VecDeque` + spare pool) backend (L2) behind the same small map interface (`get`, `get_mut`, `insert`, `remove`, `iter`,
  `range`, ...);
- changes `BookLadder` in ~10 lines: new levels via `insert_new_level`, emptied levels via
  `discard` (which recycles in the sorted backend);
- keeps *all* the ladder logic (cache handling, L1 batching, zero-size handling, the move-on-ID
  logic) shared, so L2 behaviour is identical by construction and the differential test only has
  to confirm the storage swap.

The cost: one predictable enum branch per storage call on L1/L3 books (measure it, see results).
The open question for the maintainer is whether they prefer this or a dedicated L2 ladder type.

## 6. Capacity policy

- **Chosen: grow on demand, keep the high-water mark.** The ring buffer doubles when needed;
  nothing is ever truncated; active levels plus spare levels always equals the maximum depth
  seen. When a brand-new `BookLevel` is created, the spare pool reserves room for every level in
  existence, so returning levels to the pool later (including a full `clear()` before a
  snapshot) never reallocates. The first pass over a feed allocates, after that nothing does.
  (That reserve was a bug the zero-allocation test caught: without it, the first `clear()` after
  warm-up grew the pool and cost 2 heap calls.)
- **Alternatives:** (1) preallocate a configured capacity at construction (`OrderBook::with_capacity`
  or a config field) so even the first snapshot is allocation-free; (2) a hard fixed capacity
  that drops deep levels. Option 2 changes observable behaviour (levels disappear), so it is not
  behaviour-identical and I did not choose it. Option 1 is additive and easy; it is a question for
  the maintainer.
- **Memory trade-off:** a depth spike (e.g. a 5,000-level snapshot on a 500-level feed) is
  retained until the book is dropped. A `shrink_to_fit` on `reset()` would be a simple mitigation.

## 7. Equivalence testing methodology

- **Differential (reference-model) testing:** replay the same random delta stream into the new
  L2 book and into an L2 book whose ladders are forced onto the old `BTreeMap` storage (same
  `BookLadder` code, old container). After *every* operation compare everything observable:
  full level lists (prices, orders, sizes, IDs) at depth None/1/3, the ID cache, sequence,
  `ts_last`, `update_count`, best bid/ask and sizes, `book_check_integrity`, the `Debug` output of
  the levels, `pprint`, `to_deltas`, quantity-for-price, quantity-at-level, crossed levels,
  `range(..=bound)` (the FFI path), average/worst price and exposure (compared bit-for-bit as
  `f64::to_bits`), and the return value of each operation (including `clear_stale_levels`'s
  removed levels and error variants).
- **Stream generator (proptest):** Add/Update/Delete/Clear with sides Buy/Sell/None, 48 price
  ticks (dense, so collisions, crossing and re-adding are frequent), sizes 0-5 (zero sizes hit
  the removal paths), IDs either arbitrary or the book's own price-hash ID (so no-side deltas
  actually resolve), random `F_SNAPSHOT`/`F_LAST`/`F_MBP` flags, plus clear bids/asks,
  `clear_stale_levels`, and `reset`. 512 cases x up to 200 operations; proptest shrinks any
  failure to a minimal sequence.
- **Existing suite unchanged:** all existing orderbook tests (which include L2-specific ones that
  poke `levels.insert` and `levels.range` directly) run unmodified against the new storage.
- **Allocation test:** an integration test with a thread-local counting global allocator asserts
  zero heap calls for a second pass over a stream with snapshot rebuild and top-of-book churn, at
  depth 10 and 100. Thread-local so other test threads do not pollute the count.

## 8. Benchmark methodology (and pitfalls)

- **Warm-up matters twice:** CPU caches/branch predictors, *and* the data structure's own
  capacity. The first pass over the stream grows the arrays and the spare pool; "allocations per
  delta" is measured only after that, which is exactly the steady state the issue is about. The
  warm-up allocations are reported separately so nothing is hidden.
- **Allocation counting:** a counting `GlobalAlloc` wrapper in a bench-only binary. It adds an
  atomic increment per allocation, so timing runs should not use it: the Criterion bench has no
  counting allocator; the alloc/latency harness reports counts from a separate pass.
- **Per-delta latency percentiles:** timed with `Instant::now()` around each delta, so every
  sample includes the timer pair overhead (reported, ~20-30 ns here). Percentiles are still
  comparable between builds because the overhead is the same; do not read p50 as absolute cost.
  The tight-loop mean (no per-delta timers) and Criterion give the absolute ns/delta.
- **Criterion vs iai/cachegrind:** Criterion measures wall-clock time, which is what users feel,
  but it is noisy on a shared machine (this VM had a load average above 40 from unrelated jobs).
  Cachegrind counts instructions and simulated cache misses deterministically, independent of
  load, which makes it the most trustworthy comparison here. The catch: instruction counts are not
  time (a cache miss costs 100x an add), which is why the simulated D1/LL misses are reported too.
  I difference two runs with 1 and 3 passes to cancel the setup cost of generating the stream.
- **Same bench source on both sides:** the bench only uses the public `OrderBook` API, so the
  identical file runs against the parent commit and the patched branch; the only difference is
  the library code.
- **Noise controls:** pin to one core (`taskset`), disable ASLR (`setarch -R`), alternate
  base/new runs (ABAB) so machine drift hits both, keep `bench` profile consistent (the repo's
  `bench-lto` profile is preferred for published numbers).
- **Realistic stream:** a synthetic MBP-N feed from a deeper modeled book: 70% size changes, 10%
  new levels, 10% cancels, 10% trade-throughs (all at geometric distance from the top, so most
  activity is near the top), and deltas emitted as the diff of the published top-N view, so
  levels also enter/leave at the depth boundary. Plus the real Bybit XRPUSDT orderbook.500
  sample shipped in the repo's `test_data`.
- **Pitfall: replaying the stream in a loop.** Each replay starts with a Clear and snapshot, so
  it exercises the rebuild path too; sequences go backwards on replay, which triggers the
  out-of-order warning check (a cheap branch, logging disabled). Same for both builds.

- **Pitfall found for real:** the repo's `book_iai` bench (iai 0.1.1) panics under valgrind 3.22
  while parsing cachegrind output, so iai numbers were unavailable; I drove cachegrind directly.
- **Pitfall: benchmarking the generator.** The first profile was 80% stream-generation code. The
  fix was differencing runs with different pass counts so setup cancels out.
- **Pitfall: shared target dirs.** Two git worktrees of the same workspace collide in one cargo
  target dir (path-independent metadata hashes), so my first "patched" test run silently reused
  the baseline build. Separate target dirs per tree.

## 9. Results (details in `bench/RESULTS.md`)

| workload | instructions/delta | mean ns/delta | allocs/delta after warm-up |
|---|---|---|---|
| synthetic MBP-10 | 1055 -> 923 (-12.5%) | 93.6 -> 76.2 | 0.42 -> 0 |
| synthetic MBP-100 | 1204 -> 978 (-18.8%) | 109.0 -> 78.3 | 0.46 -> 0 |
| synthetic MBP-500 | 1261 -> 1006 (-20.2%) | 126.6 -> 97.2 | 0.47 -> 0 |
| Bybit XRPUSDT ob500 (real, repo test_data) | 1371 -> 977 (-28.7%) | 125.3 -> 86.4 | 0.56 -> 0 |

- Criterion: -21.5% at depth 10 (99.8 -> 78.4 ns/delta), -14.5% at depth 100 (110.7 -> 94.7).
- p90/p99 improve everywhere (e.g. Bybit p99 398-485 ns -> 228-256 ns). p99.9 is better on the
  real data and depth 10, but within noise at depth 100/500 on that busy VM, so do not claim it.
- Memory is about the same (e.g. 108 KiB vs 112 KiB at depth 100).
- L3 costs +0.8-0.9% instructions from the enum dispatch.
- After the change, ~36% of the remaining instructions per L2 delta are SipHash in the ID cache
  (`std::collections::HashMap<u64, BookPrice>`), ~16% binary search, ~11% the `IndexMap` size
  update. So the next win is not allocation at all, it is the hash map.
- Tests: all 4,140 existing lib tests (high-precision + defi) and 3,555 (standard precision) pass
  unchanged. The new proptest (512 cases x up to 200 ops) caught a planted mutation. The allocation
  test fails on `develop` with 2,132 / 3,060 heap calls and passes with 0 on the patch.

**How to summarize it in one breath:** "Swapping the L2 level container for a sorted ring buffer
with a reuse pool made steady-state L2 deltas allocation-free and 12-29% cheaper in instructions,
with identical behaviour verified by a differential property test. The profile then showed the
real remaining cost is hashing in the ID cache, which is the obvious next step."

## 10. Likely interview questions

1. **Why not just use a faster allocator (mimalloc/jemalloc)?**
   It would shave the mean, but the work is still there (allocate, initialize an `IndexMap`,
   insert into a tree, free), and allocator slow paths still show up in the tail. Removing
   allocation from the hot path is deterministic; a faster allocator is a constant factor.
   Also, the library does not control the application's global allocator.

2. **Why does the win look modest (12-29%) if allocation is "so bad"?**
   Because in this workload only ~21% of deltas add a level and ~21% remove one; 58% are size
   updates that never allocated. glibc's tcache fast path is ~20-50 instructions. The profile shows
   allocator functions (malloc/free internals) were ~6% of base instructions, and the B-tree insert/lookup another ~23%.
   The bigger effect of allocation is variance, which is why p99 improved more than p50.

3. **Binary search on a sorted array vs a B-tree: both O(log n), why is one faster?**
   Constants and memory. The array is contiguous, so there are no dependent pointer loads and the
   prefetcher helps; the tree walks nodes allocated wherever the allocator put them. For 10-500
   levels the array sits in L1/L2. Big-O hides the ~100x gap between an L1 hit and a DRAM miss.

4. **When would your design be worse than the BTreeMap?**
   Deep books with churn in the middle (O(n/2) moves of ~100-byte elements), and after depth
   spikes (memory retained). That is why L3 keeps the tree, and why I measured depth 500 and a
   real 500-level feed rather than only MBP-10. v1 of my own design was 3x worse at depth 500.

5. **How do you know the new book behaves exactly like the old one?**
   Differential testing: same random streams into both implementations, compare every observable
   after every operation, including error results and float outputs bit-for-bit. The generator
   deliberately creates collisions, crossing, zero sizes, no-side deltas and snapshot flags. I
   checked the test's power by planting a bug (not clearing a reused level) and confirming it
   fails. Plus the whole existing suite runs unmodified.

6. **Why keep `BookLevel` (array of structs) instead of the issue's `px[N]`/`sz[N]` (struct of
   arrays)?**
   The public API returns `&BookLevel` (Rust, PyO3 and FFI). SoA would need an API break or
   building `BookLevel`s on every read. SoA would make the search denser (16-byte prices vs
   ~100-byte strides) and is a reasonable phase 2 if the maintainers accept an API change or add
   a separate "view" API.

7. **How did you measure allocations, and what can go wrong?**
   A `GlobalAlloc` wrapper that counts calls, in a bench-only binary. Pitfalls: counting other
   threads (the test uses a thread-local flag), counting the warm-up (I report it separately),
   and letting the counting overhead distort timing (the Criterion bench has no counting
   allocator).

8. **Why cachegrind and Criterion, not just Criterion?**
   The VM was shared with a load average near 50. Criterion still found significant improvements
   (p < 0.05), but tails were noisy. Cachegrind instruction and simulated-miss counts do not
   depend on load, so they give a reproducible comparison. They are not time, though, so I use both.

9. **What would you do next?**
   Drop or replace the L2 ID cache (36% of remaining instructions are SipHash): for L2 the ID is a
   hash of the price, so the level can be found by binary search on the price. The no-side
   resolution path needs a fallback that scans both ladders by ID. Then consider a denser price
   index (a parallel `VecDeque<PriceRaw>`) for the search, and optional preallocation.

10. **Why an enum instead of a trait/generic `BookLadder<S: LevelStore>`?**
    `OrderBook` is not generic and is exposed to Python and C, so a generic ladder would push a
    type parameter or dynamic dispatch through the whole API. An enum keeps one concrete type and
    one predictable branch (+0.9% on L3). A dedicated L2 ladder type is the other option, and I
    asked the maintainer which they prefer.
