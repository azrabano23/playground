// Bench-only harness (not part of the upstream patch): allocation counts, memory and per-delta
// latency percentiles for L2_MBP delta processing. Uses only the public OrderBook API so the
// identical file runs against the baseline commit and the patched branch.
//
// Registered temporarily as a [[bench]] by run_benches.sh.

use std::{
    alloc::{GlobalAlloc, Layout, System},
    collections::BTreeMap,
    hint::black_box,
    sync::atomic::{AtomicI64, AtomicU64, Ordering::Relaxed},
    time::Instant,
};

use nautilus_model::{
    data::{BookOrder, OrderBookDelta},
    enums::{BookAction, BookType, OrderSide, RecordFlag},
    identifiers::InstrumentId,
    orderbook::OrderBook,
    types::{Price, Quantity},
};

struct CountingAlloc;

static ALLOCS: AtomicU64 = AtomicU64::new(0);
static DEALLOCS: AtomicU64 = AtomicU64::new(0);
static REALLOCS: AtomicU64 = AtomicU64::new(0);
static LIVE_BYTES: AtomicI64 = AtomicI64::new(0);

unsafe impl GlobalAlloc for CountingAlloc {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCS.fetch_add(1, Relaxed);
        LIVE_BYTES.fetch_add(layout.size() as i64, Relaxed);
        unsafe { System.alloc(layout) }
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        DEALLOCS.fetch_add(1, Relaxed);
        LIVE_BYTES.fetch_sub(layout.size() as i64, Relaxed);
        unsafe { System.dealloc(ptr, layout) }
    }
    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        ALLOCS.fetch_add(1, Relaxed);
        LIVE_BYTES.fetch_add(layout.size() as i64, Relaxed);
        unsafe { System.alloc_zeroed(layout) }
    }
    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        REALLOCS.fetch_add(1, Relaxed);
        LIVE_BYTES.fetch_add(new_size as i64 - layout.size() as i64, Relaxed);
        unsafe { System.realloc(ptr, layout, new_size) }
    }
}

#[global_allocator]
static GLOBAL: CountingAlloc = CountingAlloc;

const STREAM_LEN: usize = 100_000;
const SEED: u64 = 0x5EED_4925;

struct SplitMix64(u64);

impl SplitMix64 {
    fn next_u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    fn below(&mut self, n: u64) -> u64 {
        self.next_u64() % n
    }

    // Distance from the top of book, where each deeper level is 45% as likely as the previous
    fn distance(&mut self, max: usize) -> usize {
        let mut k = 0;
        while k + 1 < max && self.below(100) < 45 {
            k += 1;
        }
        k
    }

    fn size(&mut self) -> u64 {
        1 + self.below(5_000)
    }
}

/// One side of the modeled book, keyed by distance-ordered tick (best first).
struct ModelSide {
    side: OrderSide,
    levels: BTreeMap<i64, u64>,
}

impl ModelSide {
    // Keys are stored so that ascending iteration is best first
    fn key(&self, tick: i64) -> i64 {
        match self.side {
            OrderSide::Buy => -tick,
            _ => tick,
        }
    }

    fn tick(&self, key: i64) -> i64 {
        self.key(key)
    }

    fn view(&self, depth: usize) -> Vec<(i64, u64)> {
        self.levels
            .iter()
            .take(depth)
            .map(|(key, size)| (self.tick(*key), *size))
            .collect()
    }

    fn best_tick(&self) -> i64 {
        self.tick(*self.levels.keys().next().expect("side is never empty"))
    }

    fn nth_key(&self, n: usize) -> i64 {
        *self.levels.keys().nth(n.min(self.levels.len() - 1)).unwrap()
    }

    fn worst_tick(&self) -> i64 {
        self.tick(*self.levels.keys().next_back().unwrap())
    }

    // Moves `steps` ticks away from the top of book
    fn deeper(&self, tick: i64, steps: i64) -> i64 {
        match self.side {
            OrderSide::Buy => tick - steps,
            _ => tick + steps,
        }
    }
}

fn price(tick: i64) -> Price {
    Price::from_mantissa_exponent(tick, -2, 2)
}

fn delta(
    instrument_id: InstrumentId,
    action: BookAction,
    side: OrderSide,
    tick: i64,
    size: u64,
    flags: u8,
    sequence: u64,
) -> OrderBookDelta {
    let order = BookOrder::new(side, price(tick), Quantity::from(size), 0);
    OrderBookDelta::new(
        instrument_id,
        action,
        order,
        flags,
        sequence,
        sequence.into(),
        sequence.into(),
    )
}

fn emit_diff(
    out: &mut Vec<OrderBookDelta>,
    instrument_id: InstrumentId,
    side: OrderSide,
    before: &[(i64, u64)],
    after: &[(i64, u64)],
    sequence: u64,
) {
    let start = out.len();

    for (tick, size) in before {
        if !after.iter().any(|(t, _)| t == tick) {
            out.push(delta(
                instrument_id,
                BookAction::Delete,
                side,
                *tick,
                *size,
                0,
                sequence,
            ));
        }
    }

    for (tick, size) in after {
        match before.iter().find(|(t, _)| t == tick) {
            None => out.push(delta(
                instrument_id,
                BookAction::Add,
                side,
                *tick,
                *size,
                0,
                sequence,
            )),
            Some((_, old)) if old != size => out.push(delta(
                instrument_id,
                BookAction::Update,
                side,
                *tick,
                *size,
                0,
                sequence,
            )),
            Some(_) => {}
        }
    }

    if out.len() > start {
        out.last_mut().unwrap().flags |= RecordFlag::F_LAST as u8;
    }
}

/// Generates a snapshot followed by incremental deltas publishing the top `depth` levels.
fn generate_stream(depth: usize, len: usize, seed: u64) -> Vec<OrderBookDelta> {
    let instrument_id = InstrumentId::from("AAPL.XNAS");
    let mut rng = SplitMix64(seed);
    let model_depth = depth * 2 + 8;
    let mut sides = [
        ModelSide {
            side: OrderSide::Buy,
            levels: BTreeMap::new(),
        },
        ModelSide {
            side: OrderSide::Sell,
            levels: BTreeMap::new(),
        },
    ];

    for k in 0..model_depth as i64 {
        let bid_key = sides[0].key(9_999 - k);
        let ask_key = sides[1].key(10_000 + k);
        sides[0].levels.insert(bid_key, rng.size());
        sides[1].levels.insert(ask_key, rng.size());
    }

    let mut out = Vec::with_capacity(len + 4 * depth);
    let mut sequence = 1;
    out.push(OrderBookDelta::clear(
        instrument_id,
        sequence,
        sequence.into(),
        sequence.into(),
    ));

    let snapshot: Vec<(OrderSide, i64, u64)> = sides
        .iter()
        .flat_map(|s| s.view(depth).into_iter().map(|(t, q)| (s.side, t, q)))
        .collect();
    for (idx, (side, tick, size)) in snapshot.iter().enumerate() {
        let mut flags = RecordFlag::F_SNAPSHOT as u8;
        if idx + 1 == snapshot.len() {
            flags |= RecordFlag::F_LAST as u8;
        }
        out.push(delta(
            instrument_id,
            BookAction::Add,
            *side,
            *tick,
            *size,
            flags,
            sequence,
        ));
    }

    while out.len() < len {
        sequence += 1;
        let s = usize::from(rng.below(2) == 1);
        let before = sides[s].view(depth);
        let event = rng.below(1_000);

        if event < 700 {
            // Size change at an existing level, mostly near the top
            let key = sides[s].nth_key(rng.distance(model_depth));
            let size = rng.size();
            sides[s].levels.insert(key, size);
        } else if event < 800 {
            // New level at a gap, mostly near the top
            let best = sides[s].best_tick();
            let tick = sides[s].deeper(best, rng.distance(model_depth) as i64);
            let key = sides[s].key(tick);
            let size = rng.size();
            sides[s].levels.entry(key).or_insert(size);
        } else if event < 900 {
            // Level cancelled, mostly near the top
            let key = sides[s].nth_key(rng.distance(model_depth));
            sides[s].levels.remove(&key);
        } else {
            // Top level traded through, the opposite side may step into the gap
            let key = sides[s].nth_key(0);
            sides[s].levels.remove(&key);

            if rng.below(2) == 0 {
                let o = 1 - s;
                let other_before = sides[o].view(depth);
                let new_best = sides[s].best_tick();
                let candidate = sides[o].deeper(sides[o].best_tick(), -1);
                let crosses = match sides[o].side {
                    OrderSide::Buy => candidate >= new_best,
                    _ => candidate <= new_best,
                };
                if !crosses {
                    let key = sides[o].key(candidate);
                    let size = rng.size();
                    sides[o].levels.insert(key, size);
                }
                let other_after = sides[o].view(depth);
                let side = sides[o].side;
                emit_diff(
                    &mut out,
                    instrument_id,
                    side,
                    &other_before,
                    &other_after,
                    sequence,
                );
            }
        }

        // Keep the modeled book deeper than the published view
        while sides[s].levels.len() < model_depth {
            let tick = sides[s].deeper(sides[s].worst_tick(), 1);
            let key = sides[s].key(tick);
            let size = rng.size();
            sides[s].levels.insert(key, size);
        }

        let after = sides[s].view(depth);
        let side = sides[s].side;
        emit_diff(&mut out, instrument_id, side, &before, &after, sequence);
    }

    out
}


/// Parses the Bybit `orderbook.500` sample (one JSON message per line) into L2 deltas.
fn load_bybit(path: &str) -> Vec<OrderBookDelta> {
    let instrument_id = InstrumentId::from("XRPUSDT-LINEAR.BYBIT");
    let text = std::fs::read_to_string(path).expect("read bybit sample");
    let mut out = Vec::new();
    for (seq, line) in text.lines().enumerate() {
        let msg: serde_json::Value = serde_json::from_str(line).expect("json");
        let seq = seq as u64 + 1;
        let is_snapshot = msg["type"] == "snapshot";
        if is_snapshot {
            out.push(OrderBookDelta::clear(instrument_id, seq, seq.into(), seq.into()));
        }
        let data = &msg["data"];
        let start = out.len();
        for (key, side) in [("b", OrderSide::Buy), ("a", OrderSide::Sell)] {
            for level in data[key].as_array().unwrap() {
                let px = Price::from(level[0].as_str().unwrap());
                let sz = Quantity::from(level[1].as_str().unwrap());
                let order = BookOrder::new(side, px, sz, 0);
                let (action, flags) = if is_snapshot {
                    (BookAction::Add, RecordFlag::F_SNAPSHOT as u8)
                } else if sz.is_zero() {
                    (BookAction::Delete, 0)
                } else {
                    (BookAction::Update, 0)
                };
                out.push(OrderBookDelta {
                    instrument_id,
                    action,
                    order,
                    flags,
                    sequence: seq,
                    ts_event: seq.into(),
                    ts_init: seq.into(),
                });
            }
        }
        if out.len() > start {
            out.last_mut().unwrap().flags |= RecordFlag::F_LAST as u8;
        }
    }
    out
}

fn percentile(sorted: &[u64], p: f64) -> u64 {
    let idx = ((sorted.len() as f64 - 1.0) * p).round() as usize;
    sorted[idx]
}

fn timer_overhead_ns() -> u64 {
    let mut samples = Vec::with_capacity(1_000_000);
    for _ in 0..1_000_000 {
        let t0 = Instant::now();
        let t1 = Instant::now();
        samples.push(t1.duration_since(t0).as_nanos() as u64);
    }
    samples.sort_unstable();
    percentile(&samples, 0.5)
}

fn run_scenario(name: &str, deltas: &[OrderBookDelta], passes: usize) {
    let n = deltas.len() as f64;
    let (adds, updates, deletes, clears) = deltas.iter().fold((0, 0, 0, 0), |acc, d| match d.action {
        BookAction::Add => (acc.0 + 1, acc.1, acc.2, acc.3),
        BookAction::Update => (acc.0, acc.1 + 1, acc.2, acc.3),
        BookAction::Delete => (acc.0, acc.1, acc.2 + 1, acc.3),
        BookAction::Clear => (acc.0, acc.1, acc.2, acc.3 + 1),
    });

    // Memory: live heap bytes owned by the book after the first (warm-up) pass
    let live_before = LIVE_BYTES.load(Relaxed);
    let mut book = OrderBook::new(deltas[0].instrument_id, BookType::L2_MBP);
    let a0 = ALLOCS.load(Relaxed);
    for d in deltas {
        book.apply_delta(d).unwrap();
    }
    let warmup_allocs = ALLOCS.load(Relaxed) - a0;
    let book_bytes = LIVE_BYTES.load(Relaxed) - live_before;

    // Allocations after warm-up
    let (a0, d0, r0) = (ALLOCS.load(Relaxed), DEALLOCS.load(Relaxed), REALLOCS.load(Relaxed));
    for _ in 0..passes {
        for d in deltas {
            book.apply_delta(black_box(d)).unwrap();
        }
    }
    let total = n * passes as f64;
    let allocs = (ALLOCS.load(Relaxed) - a0) as f64 / total;
    let deallocs = (DEALLOCS.load(Relaxed) - d0) as f64 / total;
    let reallocs = (REALLOCS.load(Relaxed) - r0) as f64 / total;

    // Throughput: tight loop, no per-delta timers
    let mut best_mean = f64::MAX;
    for _ in 0..5 {
        let t0 = Instant::now();
        for _ in 0..passes {
            for d in deltas {
                book.apply_delta(black_box(d)).unwrap();
            }
        }
        best_mean = best_mean.min(t0.elapsed().as_nanos() as f64 / total);
    }

    // Per-delta latency (includes Instant::now pair overhead)
    let mut samples: Vec<u64> = Vec::with_capacity(deltas.len() * passes);
    for _ in 0..passes {
        for d in deltas {
            let t0 = Instant::now();
            book.apply_delta(black_box(d)).unwrap();
            samples.push(t0.elapsed().as_nanos() as u64);
        }
    }
    samples.sort_unstable();
    black_box(book.best_bid_price());

    println!(
        "| {name} | {} | {:.1}/{:.1}/{:.1} | {:.1} | {} | {} | {} | {} | {} | {:.4} | {:.4} | {:.4} | {} | {:.1} |",
        deltas.len(),
        100.0 * adds as f64 / n,
        100.0 * updates as f64 / n,
        100.0 * deletes as f64 / n,
        best_mean,
        percentile(&samples, 0.5),
        percentile(&samples, 0.9),
        percentile(&samples, 0.99),
        percentile(&samples, 0.999),
        samples[samples.len() - 1],
        allocs,
        deallocs,
        reallocs,
        warmup_allocs,
        book_bytes as f64 / 1024.0,
    );
    let _ = clears;
}

/// Instruction-count mode for cachegrind: warm up once, then apply `passes` replays and exit.
/// Differencing two runs with different `passes` removes setup cost from the count.
fn cachegrind_mode(scenario: &str, passes: usize) {
    let deltas = if scenario == "bybit" {
        load_bybit(&std::env::var("BYBIT_OB500").expect("BYBIT_OB500"))
    } else {
        generate_stream(scenario.parse().expect("depth"), STREAM_LEN, SEED)
    };
    let mut book = OrderBook::new(deltas[0].instrument_id, BookType::L2_MBP);
    for d in &deltas {
        book.apply_delta(d).unwrap();
    }
    for _ in 0..passes {
        for d in &deltas {
            book.apply_delta(black_box(d)).unwrap();
        }
    }
    println!("{} {}", deltas.len(), black_box(book.best_bid_price()).is_some());
}

fn main() {
    if let (Ok(scenario), Ok(passes)) = (std::env::var("CG_SCENARIO"), std::env::var("CG_PASSES")) {
        cachegrind_mode(&scenario, passes.parse().expect("passes"));
        return;
    }
    let label = std::env::var("BENCH_LABEL").unwrap_or_else(|_| "unlabelled".to_string());
    println!("## {label}");
    println!("timer overhead p50 (Instant pair): {} ns", timer_overhead_ns());
    println!();
    println!("| scenario | deltas | add/upd/del % | mean ns/delta | p50 | p90 | p99 | p99.9 | max | allocs/delta | deallocs/delta | reallocs/delta | warm-up allocs | book KiB |");
    println!("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|");
    for depth in [10_usize, 100, 500] {
        let deltas = generate_stream(depth, STREAM_LEN, SEED);
        run_scenario(&format!("synthetic depth {depth}"), &deltas, 10);
    }
    if let Ok(path) = std::env::var("BYBIT_OB500") {
        let deltas = load_bybit(&path);
        run_scenario("bybit XRPUSDT ob500 (real)", &deltas, 200);
    }
}
