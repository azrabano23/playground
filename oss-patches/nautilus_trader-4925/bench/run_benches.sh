#!/usr/bin/env bash
# Back-to-back L2 order book benchmarks: baseline commit vs patched branch.
#
# BASE: a worktree at the parent commit (unmodified library code).
# NEW:  the branch with the patch applied.
# Both trees get the same bench sources (they use only the public OrderBook API), so the only
# difference between the two builds is the library code under test.
#
# Usage: BASE=/path/to/base NEW=/path/to/new PROFILE=bench ./run_benches.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="${BASE:-/home/user/oss3/nautilus_base}"
NEW="${NEW:-/home/user/oss3/nautilus_trader}"
PROFILE="${PROFILE:-bench}"
CPU="${CPU:-3}"
ROUNDS="${ROUNDS:-2}"
# Separate target dirs: cargo's path-independent metadata hashing makes two worktrees of the
# same workspace collide in a shared target dir. Criterion results go to one shared place.
BASE_TARGET="${BASE_TARGET:-/home/user/oss3/target-shared}"
NEW_TARGET="${NEW_TARGET:-/home/user/oss3/target-new}"
export CRITERION_HOME="${CRITERION_HOME:-/home/user/oss3/criterion}"
export CARGO_INCREMENTAL=0
OUT="${OUT:-$HERE/results}"
mkdir -p "$OUT"

# Real L2 sample shipped in the repo (Bybit XRPUSDT orderbook.500, 2024-12-01)
SAMPLE_DIR="$(mktemp -d)"
unzip -o -q "$NEW/test_data/bybit/xrpusdt-ob500.data.zip" -d "$SAMPLE_DIR"
export BYBIT_OB500="$(ls "$SAMPLE_DIR"/*.data)"

register() {
  local tree="$1" name="$2"
  if ! grep -q "name = \"$name\"" "$tree/crates/model/Cargo.toml"; then
    printf '\n[[bench]]\nname = "%s"\npath = "benches/%s.rs"\nharness = false\n' "$name" "$name" \
      >> "$tree/crates/model/Cargo.toml"
  fi
}

# The criterion bench is part of the patch; the baseline tree gets an identical copy
cp "$NEW/crates/model/benches/book_l2_criterion.rs" "$BASE/crates/model/benches/"
register "$BASE" book_l2_criterion

# The allocation/latency harness is bench-only tooling, copied into both trees
for tree in "$BASE" "$NEW"; do
  cp "$HERE/book_l2_alloc_latency.rs" "$tree/crates/model/benches/"
  register "$tree" book_l2_alloc_latency
done

run() {
  # Pin to one core and disable ASLR to reduce run-to-run noise
  taskset -c "$CPU" setarch "$(uname -m)" -R "$@"
}

{
  echo "host: $(uname -srm), $(nproc) vCPU, $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)"
  echo "toolchain: $(cd "$NEW" && rustc --version)"
  echo "profile: $PROFILE, pinned to CPU $CPU, ASLR disabled"
  echo
} > "$OUT/alloc_latency.md"

# Alternate base/new so slow drift in machine state affects both equally
for round in $(seq 1 "$ROUNDS"); do
  for label in base new; do
    tree="$BASE"; target="$BASE_TARGET"
    [[ "$label" == new ]] && tree="$NEW" && target="$NEW_TARGET"
    (cd "$tree" && CARGO_TARGET_DIR="$target" BENCH_LABEL="$label (round $round)" run cargo bench -q -p nautilus-model \
      --profile "$PROFILE" --bench book_l2_alloc_latency) | tee -a "$OUT/alloc_latency.md"
    echo >> "$OUT/alloc_latency.md"
  done
done

# Criterion: save the baseline, then compare the patched build against it
(cd "$BASE" && CARGO_TARGET_DIR="$BASE_TARGET" run cargo bench -p nautilus-model --profile "$PROFILE" --bench book_l2_criterion \
  -- --save-baseline base) 2>&1 | tee "$OUT/criterion_base.txt"
(cd "$NEW" && CARGO_TARGET_DIR="$NEW_TARGET" run cargo bench -p nautilus-model --profile "$PROFILE" --bench book_l2_criterion \
  -- --baseline base) 2>&1 | tee "$OUT/criterion_new_vs_base.txt"

rm -rf "$SAMPLE_DIR"
