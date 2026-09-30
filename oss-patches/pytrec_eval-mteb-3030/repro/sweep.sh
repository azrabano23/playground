#!/bin/bash
# usage: sweep.sh <venv> <outprefix> [script]  -- runs the repro for PYTHONHASHSEED=0..200
# address space capped at 4 GiB so a garbage-sized malloc fails fast instead of OOM-killing the box
VENV=$1; OUT=$2; SCRIPT=${3:-repro_dummy.py}; D=$(cd $(dirname $0); pwd)
seq 0 200 | xargs -P 4 -I{} bash -c "ulimit -v 4000000; r=\$(cd $D; PYTHONHASHSEED={} timeout 120 $VENV/bin/python $SCRIPT 2>/dev/null | tail -1); echo \"{}	\${r:-CRASH/NO-OUTPUT}\"" > $OUT.raw
sort -n $OUT.raw > $OUT.per_seed.tsv; rm $OUT.raw
cut -f2 $OUT.per_seed.tsv | sort | uniq -c | sort -rn > $OUT.distinct.txt
echo "distinct outcomes: $(wc -l < $OUT.distinct.txt)"; cut -c1-300 $OUT.distinct.txt
