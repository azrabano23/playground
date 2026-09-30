<!--
HOLD: do not open this PR until a maintainer has agreed on the approach in #4925.
Before opening:
  1. Apply any changes the maintainer asked for (ladder shape, capacity policy) and re-run the
     tests, the differential proptest and the benches.
  2. Rebase on current develop, then run `make format` and `make pre-commit` (they need
     `make install-tools` / prek, which were not installed in the environment the prototype was
     built in) and `make cargo-test-crate-nautilus-model`.
  3. Re-run bench/run_benches.sh and bench/cachegrind.sh and update the numbers below if they moved.
     If you can, use the `bench-lto` profile and a quiet machine for the published numbers.
  4. Tick only the checkboxes that are true at that point.
  5. Sign the CLA when CLA Assistant prompts you.
PR title (becomes the squash commit subject):
  Add sorted array level storage for L2 order books
-->

# Pull Request

**NautilusTrader can execute live trades involving real capital. Pull requests are held to a very
high standard for correctness, reliability, testing, clarity, and maintainability.**

- [ ] A maintainer agreed on the problem and approach in an issue, or this is a small,
  self-contained fix that does not need prior discussion
- [ ] I have read and followed
  [CONTRIBUTING.md](https://github.com/nautechsystems/nautilus_trader/blob/develop/CONTRIBUTING.md)
  and, if I used AI,
  [AI_POLICY.md](https://github.com/nautechsystems/nautilus_trader/blob/develop/AI_POLICY.md)
- [ ] I understand and can explain every submitted change and all information in this PR description
- [ ] This change is complete, locally validated, and ready for review, or a maintainer requested
  this draft
- [ ] I ran `make format`, then ran `make pre-commit` locally and confirmed it passed, or I
  described an agreed limitation below
- [ ] I ran all relevant tests locally, no tests apply to this change, or I described an agreed
  limitation below
- [x] I have not modified `RELEASES.md` (maintainers keep it current to avoid merge conflicts)

## Summary

`L2_MBP` ladders now store price levels in a sorted ring buffer (`VecDeque<BookLevel>`, worst to
best) with binary search, and reuse emptied levels from a spare pool. This replaces the
`BTreeMap<BookPrice, BookLevel>` for L2 books. Once a book has reached its maximum depth, applying
L2 deltas no longer allocates or frees. On current `develop` it averages 0.4-0.6 heap allocations
per delta. L1 and L3 books keep the `BTreeMap`.

The change is confined to the level container. `BookLadder` holds a `LadderLevels` enum
(`Tree` / `Sorted`) with the same small map interface, and all ladder logic stays shared, so L2
behaviour and the public API (`bids()`/`asks()` returning `&BookLevel`, PyO3, FFI) are unchanged.
The `analysis` helpers now take any best-first iterator of `(&BookPrice, &BookLevel)`, which
existing `&BTreeMap` callers still satisfy.

Capacity grows on demand and is kept at the high-water mark (agreed in #4925: <fill in>).

## Related issues/PRs

Resolves #4925

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [x] Improvement (non-breaking)
- [ ] Breaking change (impacts existing behavior)
- [ ] Documentation update
- [ ] Maintenance / chore

## Breaking change details (if applicable)

None. The `analysis::get_*` functions are generalized from `&BTreeMap<BookPrice, BookLevel>` to
`impl IntoIterator<Item = (&BookPrice, &BookLevel)>`, which is source-compatible for existing callers.

## Documentation

- [ ] Documentation changes follow the style guide (`docs/developer_guide/docs.md`)
- [ ] For PyO3 binding or wrapped Rust doc changes, I ran `make py-stubs` and committed the generated output

No PyO3 bindings or wrapped docs changed.

## Testing

- [x] Affected code paths are already covered by the test suite
- [x] I added/updated tests to cover new or changed logic
- [ ] No logic changed (documentation, comments, or metadata only)

- All existing `nautilus-model` tests pass unchanged: 4,140 lib tests with
  `arrow,defi,ffi,high-precision,test-support` and 3,555 with standard precision, plus the
  integration tests.
- `prop_test_l2_sorted_levels_match_tree_levels` replays random L2 delta streams into the new book
  and into a book forced onto the `BTreeMap` storage (512 cases, up to 200 ops each). After every
  operation it asserts identical level lists, cache, BBO, sequence metadata, integrity result,
  `pprint`, `to_deltas`, `range(..=bound)`, and the analysis queries (bit-for-bit). The streams
  cover Add/Update/Delete/Clear, no-side deltas, zero sizes, snapshot/`F_LAST`/`F_MBP` flags,
  crossed books, `clear_stale_levels`, and `reset`.
- `tests/l2_book_allocations.rs` counts heap calls with a thread-local counting allocator and
  asserts zero for a steady-state pass that includes a snapshot rebuild, at depth 10 and 100.
  The same test counts 2,132 and 3,060 heap calls on `develop`.
- Unit tests cover best-first iteration, `range` parity with `BTreeMap::range` for all bound
  kinds, spare-level reuse, and `Debug` parity.

### Benchmarks

New Criterion bench `book_l2_criterion` replays a 100k-delta synthetic MBP stream (a seeded model
of a deeper book, published as the top N levels; most activity near the top). Run back-to-back
against `develop` on the same machine (4 vCPU Xeon @ 2.1 GHz, `bench` profile, pinned core,
ASLR off; the host was shared, so the instruction counts are the steadier signal):

| workload | instructions/delta (cachegrind) | Criterion / mean ns per delta | allocs/delta |
|---|---|---|---|
| MBP-10 | 1055 -> 923 (-12%) | 99.8 -> 78.4 (-21%) | 0.42 -> 0 |
| MBP-100 | 1204 -> 978 (-19%) | 110.7 -> 94.7 (-14%) | 0.46 -> 0 |
| MBP-500 | 1261 -> 1006 (-20%) | 127 -> 97 | 0.47 -> 0 |
| Bybit XRPUSDT ob500 (`test_data`) | 1371 -> 977 (-29%) | 125 -> 86 | 0.56 -> 0 |

p90/p99 per-delta latency improves in every workload. Memory held by the book is about the same
(the spare pool replaces the B-tree nodes). The L3 path, which still uses the `BTreeMap`, shows
+0.9% instructions from the enum dispatch.
