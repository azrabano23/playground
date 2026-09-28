#!/bin/sh
# Build owen_bench against a "before" and an "after" libompl and run the benchmark matrix.
# Usage: OMPL_SRC=/path/to/ompl BEFORE_LIB=/dir/with/old/libompl.so AFTER_LIB=/dir/with/new/libompl.so ./run_bench.sh
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
OMPL_SRC=${OMPL_SRC:-/home/user/oss3/ompl}
BEFORE_LIB=${BEFORE_LIB:-/home/user/oss3/baseline_lib}
AFTER_LIB=${AFTER_LIB:-$OMPL_SRC/build/src/ompl}
OUT=${OUT:-/tmp/owen_bench}
mkdir -p "$OUT"
for v in before after; do
  eval L=\$$(echo $v | tr a-z A-Z)_LIB
  g++ -O2 -std=c++17 -I"$OMPL_SRC/src" -I"$OMPL_SRC/build/src" -I/usr/include/eigen3 "$HERE/owen_bench.cpp" \
      -o "$OUT/owen_bench_$v" -L"$L" -lompl -Wl,-rpath,"$L"
done
# args: numPairs numRefPairs boundsHalfWidth seed maxPitch turnRadius
for cfg in "100000 2000 10 1 0.5235987755982988" \
           "100000 2000 3 1 0.5235987755982988" \
           "100000 2000 100 1 0.5235987755982988" \
           "100000 2000 1000 1 0.5235987755982988" \
           "100000 2000 100 1 0.2617993877991494"; do
  for v in before after; do
    echo "### $v: owen_bench $cfg"
    "$OUT/owen_bench_$v" $cfg
    echo
  done
done
