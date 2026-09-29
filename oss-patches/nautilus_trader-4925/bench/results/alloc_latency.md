host: Linux 6.18.44-fc-v37 x86_64, 4 vCPU, Intel(R) Xeon(R) Processor @ 2.10GHz
toolchain: rustc 1.98.1 (48a229cea 2026-09-01), from rust-toolchain.toml
profile: bench, pinned to CPU 3, ASLR disabled
note: shared VM with unrelated jobs running (load average ~40-55 on 4 vCPU during the runs); treat wall-clock tails as indicative only. Latency percentiles include the ~25 ns Instant pair overhead.

## base (round 1)
timer overhead p50 (Instant pair): 25 ns

| scenario | deltas | add/upd/del % | mean ns/delta | p50 | p90 | p99 | p99.9 | max | allocs/delta | deallocs/delta | reallocs/delta | warm-up allocs | book KiB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| synthetic depth 10 | 100001 | 21.1/57.7/21.1 | 92.7 | 117 | 180 | 243 | 540 | 1119752 | 0.4229 | 0.4229 | 0.0000 | 42300 | 8.4 |
| synthetic depth 100 | 100002 | 21.3/57.6/21.1 | 111.5 | 125 | 222 | 332 | 536 | 63633 | 0.4557 | 0.4557 | 0.0000 | 45585 | 107.8 |
| synthetic depth 500 | 100000 | 21.9/57.1/20.9 | 124.4 | 150 | 289 | 472 | 935 | 2046289 | 0.4742 | 0.4742 | 0.0000 | 47440 | 586.3 |
| bybit XRPUSDT ob500 (real) | 3967 | 25.2/74.3/0.5 | 129.9 | 125 | 247 | 398 | 3178 | 286830 | 0.5551 | 0.5551 | 0.0000 | 2220 | 520.3 |

## new (round 1)
timer overhead p50 (Instant pair): 25 ns

| scenario | deltas | add/upd/del % | mean ns/delta | p50 | p90 | p99 | p99.9 | max | allocs/delta | deallocs/delta | reallocs/delta | warm-up allocs | book KiB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| synthetic depth 10 | 100001 | 21.1/57.7/21.1 | 76.3 | 107 | 138 | 209 | 387 | 2482327 | 0.0000 | 0.0000 | 0.0000 | 50 | 11.8 |
| synthetic depth 100 | 100002 | 21.3/57.6/21.1 | 86.4 | 122 | 174 | 293 | 629 | 448629 | 0.0000 | 0.0000 | 0.0000 | 418 | 112.2 |
| synthetic depth 500 | 100000 | 21.9/57.1/20.9 | 97.3 | 134 | 231 | 435 | 1110 | 1678345 | 0.0000 | 0.0000 | 0.0000 | 2024 | 562.3 |
| bybit XRPUSDT ob500 (real) | 3967 | 25.2/74.3/0.5 | 85.8 | 122 | 140 | 228 | 638 | 433743 | 0.0000 | 0.0000 | 0.0000 | 2028 | 497.0 |

## base (round 2)
timer overhead p50 (Instant pair): 25 ns

| scenario | deltas | add/upd/del % | mean ns/delta | p50 | p90 | p99 | p99.9 | max | allocs/delta | deallocs/delta | reallocs/delta | warm-up allocs | book KiB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| synthetic depth 10 | 100001 | 21.1/57.7/21.1 | 94.4 | 125 | 190 | 307 | 568 | 1922393 | 0.4229 | 0.4229 | 0.0000 | 42300 | 8.4 |
| synthetic depth 100 | 100002 | 21.3/57.6/21.1 | 106.4 | 124 | 224 | 355 | 601 | 290431 | 0.4557 | 0.4557 | 0.0000 | 45585 | 107.8 |
| synthetic depth 500 | 100000 | 21.9/57.1/20.9 | 128.8 | 147 | 286 | 498 | 3415 | 114679 | 0.4742 | 0.4742 | 0.0000 | 47439 | 553.3 |
| bybit XRPUSDT ob500 (real) | 3967 | 25.2/74.3/0.5 | 120.7 | 133 | 283 | 485 | 4084 | 213672 | 0.5551 | 0.5551 | 0.0000 | 2220 | 520.3 |

## new (round 2)
timer overhead p50 (Instant pair): 25 ns

| scenario | deltas | add/upd/del % | mean ns/delta | p50 | p90 | p99 | p99.9 | max | allocs/delta | deallocs/delta | reallocs/delta | warm-up allocs | book KiB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| synthetic depth 10 | 100001 | 21.1/57.7/21.1 | 76.0 | 107 | 134 | 188 | 344 | 69930 | 0.0000 | 0.0000 | 0.0000 | 50 | 11.8 |
| synthetic depth 100 | 100002 | 21.3/57.6/21.1 | 70.2 | 109 | 164 | 321 | 506 | 69394 | 0.0000 | 0.0000 | 0.0000 | 418 | 112.2 |
| synthetic depth 500 | 100000 | 21.9/57.1/20.9 | 97.0 | 124 | 168 | 266 | 445 | 227675 | 0.0000 | 0.0000 | 0.0000 | 2024 | 562.3 |
| bybit XRPUSDT ob500 (real) | 3967 | 25.2/74.3/0.5 | 86.9 | 123 | 144 | 256 | 891 | 687826 | 0.0000 | 0.0000 | 0.0000 | 2028 | 497.0 |

