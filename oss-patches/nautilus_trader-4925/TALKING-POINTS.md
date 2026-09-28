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
- **Skewed access.** Most updates hit the top few levels. The prototype stores each side
  worst-to-best, so the best price is the *last* element: inserting or deleting near the top
  moves only the handful of elements after it (`memmove` of a few hundred bytes), and the best
  price is `levels.last()`.
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
| Insert/remove level at distance k from top | O(log n) + allocation | O(log n) + O(k) element moves, no allocation |
| Insert/remove near the *bottom* of a deep book | O(log n) | O(n) moves |
| Best price | O(log n) (leftmost leaf) | O(1) |
| Iterate top N | O(N) node walking | O(N) contiguous |
| Memory | allocated per level, freed on removal | high-water capacity retained |

The honest weak spots: (a) a very deep book (thousands of levels) with churn at the deep end
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

- adds `LadderLevels`, an enum with a `Tree(BTreeMap)` backend (L1, L3) and a `Sorted` backend
  (L2) behind the same small map interface (`get`, `get_mut`, `insert`, `remove`, `iter`,
  `range`, ...);
- changes `BookLadder` in ~10 lines: new levels via `insert_new_level`, emptied levels via
  `discard` (which recycles in the sorted backend);
- keeps *all* the ladder logic (cache handling, L1 batching, zero-size handling, the move-on-ID
  logic) shared, so L2 behaviour is identical by construction and the differential test only has
  to confirm the storage swap.

The cost: one predictable enum branch per storage call on L1/L3 books (measure it, see results).
The open question for the maintainer is whether they prefer this or a dedicated L2 ladder type.

## 6. Capacity policy

- **Chosen: grow on demand, keep the high-water mark.** `Vec` doubles when needed; nothing is
  ever truncated; the spare pool plus active levels always equals the maximum depth seen. The
  first pass over a feed allocates, after that nothing does.
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

## 9. Results

(filled in from `bench/results/` below)

## 10. Likely interview questions

(filled in below)
