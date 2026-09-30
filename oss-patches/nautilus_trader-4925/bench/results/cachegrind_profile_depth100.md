Per-delta instructions by function (self cost), depth-100 synthetic stream.
cachegrind, (5 passes - 1 pass) / (4 x 100,002 deltas); stream generation cancels out.

### base: total 1077 Ir/delta

| Ir/delta | share | function |
|---|---|---|
| 203.8 | 18.9% | `<std::hash::random::RandomState as core::hash::BuildHasher>::hash_one::<&u64>` |
| 140.7 | 13.1% | `<alloc::collections::btree::map::BTreeMap<orderbook::ladder::BookPrice, orderbook::own::OwnBookLevel>>::get_mut::<orderbook::ladder::Book...` |
| 124.0 | 11.5% | `<core::hash::sip::Hasher<core::hash::sip::Sip13Rounds> as core::hash::Hasher>::write` |
| 112.8 | 10.5% | `<indexmap::map::IndexMap<u64, data::order::BookOrder>>::insert_full` |
| 106.7 | 9.9% | `<alloc::collections::btree::map::BTreeMap<orderbook::ladder::BookPrice, orderbook::level::BookLevel>>::insert` |
| 75.2 | 7.0% | `<orderbook::ladder::BookLadder>::update` |
| 62.5 | 5.8% | `<orderbook::book::OrderBook>::increment` |
| 48.0 | 4.5% | `<orderbook::book::OrderBook>::apply_delta` |
| 47.4 | 4.4% | `<orderbook::book::OrderBook>::apply_delta_inner` |
| 37.9 | 3.5% | `__memcpy_avx_unaligned_erms` |
| 32.9 | 3.1% | `<hashbrown::raw::RawTable<usize>>::reserve_rehash::<indexmap::inner::get_hash<u64, data::order::BookOrder>::{closure#0}>` |
| 24.4 | 2.3% | `_int_free` |
| 20.5 | 1.9% | `malloc` |
| 18.0 | 1.7% | `<orderbook::book::OrderBook>::report_out_of_order_snapshot` |
| 14.1 | 1.3% | `free` |
| 4.0 | 0.4% | `_int_malloc` |

### new: total 916 Ir/delta

| Ir/delta | share | function |
|---|---|---|
| 203.7 | 22.2% | `<std::hash::random::RandomState as core::hash::BuildHasher>::hash_one::<&u64>` |
| 124.0 | 13.5% | `<core::hash::sip::Hasher<core::hash::sip::Sip13Rounds> as core::hash::Hasher>::write` |
| 101.0 | 11.0% | `<indexmap::map::IndexMap<u64, data::order::BookOrder>>::insert_full` |
| 75.4 | 8.2% | `<alloc::collections::vec_deque::VecDeque<orderbook::level::BookLevel>>::binary_search_by::<<orderbook::levels::SortedLevels>::find::{clos...` |
| 75.1 | 8.2% | `<alloc::collections::vec_deque::VecDeque<orderbook::level::BookLevel>>::binary_search_by::<<orderbook::levels::SortedLevels>::find::{clos...` |
| 72.6 | 7.9% | `<orderbook::ladder::BookLadder>::update` |
| 62.5 | 6.8% | `<orderbook::book::OrderBook>::increment` |
| 48.4 | 5.3% | `<orderbook::book::OrderBook>::apply_delta_inner` |
| 48.0 | 5.2% | `<orderbook::book::OrderBook>::apply_delta` |
| 44.1 | 4.8% | `<orderbook::book::OrderBook>::update` |
| 42.7 | 4.7% | `<orderbook::levels::LadderLevels>::get_mut` |
| 18.0 | 2.0% | `<orderbook::book::OrderBook>::report_out_of_order_snapshot` |

