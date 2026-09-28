#!/usr/bin/env bash
# Deterministic instruction and cache-miss counts per delta (immune to host load).
# Runs the harness binary under cachegrind with P1 and P2 replay passes and reports
# (count(P2) - count(P1)) / ((P2 - P1) * deltas), which cancels stream generation and warm-up.
#
# Usage: BIN_BASE=... BIN_NEW=... ./cachegrind.sh   (paths to the built book_l2_alloc_latency binaries)
set -euo pipefail
P1="${P1:-1}"; P2="${P2:-3}"
SCENARIOS="${SCENARIOS:-10 100 500 bybit}"
echo "| scenario | build | Ir/delta | D1 misses/delta | LL misses/delta |"
echo "|---|---|---|---|---|"
for scenario in $SCENARIOS; do
  for build in base new; do
    bin="$BIN_BASE"; [[ "$build" == new ]] && bin="$BIN_NEW"
    declare -A ir d1 ll
    for p in "$P1" "$P2"; do
      out=$(mktemp)
      n=$(CG_SCENARIO="$scenario" CG_PASSES="$p" valgrind --tool=cachegrind --cache-sim=yes \
            --cachegrind-out-file="$out" "$bin" 2>/dev/null | awk '{print $1}')
      summary=$(grep '^summary:' "$out" | cut -d' ' -f2-)
      events=$(grep '^events:' "$out" | cut -d' ' -f2-)
      ir[$p]=$(paste <(echo "$events" | tr ' ' '\n') <(echo "$summary" | tr ' ' '\n') | awk '$1=="Ir"{print $2}')
      d1[$p]=$(paste <(echo "$events" | tr ' ' '\n') <(echo "$summary" | tr ' ' '\n') | awk '$1=="D1mr"||$1=="D1mw"{s+=$2} END{print s}')
      ll[$p]=$(paste <(echo "$events" | tr ' ' '\n') <(echo "$summary" | tr ' ' '\n') | awk '$1=="DLmr"||$1=="DLmw"{s+=$2} END{print s}')
      rm -f "$out"
    done
    awk -v n="$n" -v dp="$((P2 - P1))" -v s="$scenario" -v b="$build" \
      -v i1="${ir[$P1]}" -v i2="${ir[$P2]}" -v a1="${d1[$P1]}" -v a2="${d1[$P2]}" -v l1="${ll[$P1]}" -v l2="${ll[$P2]}" \
      'BEGIN { d = dp * n; printf "| %s | %s | %.0f | %.2f | %.3f |\n", s, b, (i2-i1)/d, (a2-a1)/d, (l2-l1)/d }'
  done
done
