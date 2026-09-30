#!/bin/sh
# Builds and runs the benchmark against a QuantLib checkout with the patch
# applied. QL points to the checkout; QLCFG to a CMake build directory of it
# (only the generated ql/config.hpp is used from there).
set -e
QL=${QL:-/home/user/oss3/QuantLib}
QLCFG=${QLCFG:-$QL/build-o0}
OUT=${OUT:-./obj}
mkdir -p "$OUT"
# the solvers and what they depend on, all at -O2
for f in pricingengines/blackformula pricingengines/letsberational \
         math/distributions/normaldistribution math/errorfunction errors \
         instruments/payoffs; do
    g++ -std=c++17 -O2 -DNDEBUG -I"$QL" -I"$QLCFG" -c "$QL/ql/$f.cpp" -o "$OUT/$(basename $f).o"
done
# Only the solver code is linked; the unresolved symbols are vtables of
# classes pulled in by the headers (Instrument, Observable, ...) and are
# never called.
g++ -std=c++17 -O2 -DNDEBUG -I"$QL" -I"$QLCFG" lbr_bench.cpp "$OUT"/*.o \
    -Wl,--unresolved-symbols=ignore-all -o lbr_bench
[ -f cases.csv ] || python3 gen_cases.py cases.csv
./lbr_bench cases.csv | tee results.txt
