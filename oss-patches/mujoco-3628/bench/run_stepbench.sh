#!/bin/bash
# Interleaved A/B step-time benchmark (base vs fix), best of ROUNDS rounds.
# usage: run_stepbench.sh <bindir with stepbench_{base,fix}-{double,single}> <mujoco src> [ROUNDS]
BIN=$1; M=$2; ROUNDS=${3:-5}
CASES=(
  "model/humanoid/humanoid.xml 2000 -1"
  "model/humanoid/humanoid.xml 2000 1 10"
  "model/humanoid/22_humanoids.xml 300 -1"
  "model/humanoid/22_humanoids.xml 300 1 10"
  "test/benchmark/testdata/boxpile.xml 300 -1"
  "test/benchmark/testdata/boxpile.xml 300 1 10"
)
for prec in double single; do
  for c in "${CASES[@]}"; do
    set -- $c
    for r in $(seq $ROUNDS); do
      for v in base fix; do
        echo "$prec $v $("$BIN/stepbench_$v-$prec" "$M/$1" "$2" 1 "${@:3}" | sed "s|$M/||")"
      done
    done
  done
done
