# Reproduction for mteb#3030 / pytrec_eval#57 / #49

Environment: Linux 6.18, glibc 2.39, gcc 13.3, CPython 3.11.15, valgrind 3.22. Every sweep runs under `ulimit -v 4000000` (4 GiB address space), so that a garbage-sized allocation fails fast instead of OOM-killing the machine. Without the cap, some seeds stall for 20+ s or get SIGKILLed instead.

## Files

| file | what |
|---|---|
| `dummy.json` | the reporter's `mteb_retrieval_dummy_test.json` from mteb#3030 (78 queries; query `"63"` has `{}` qrels) |
| `repro_dummy.py` | MTEB's measure set (`map_cut`, `ndcg_cut`, `recall`, `P` at 1,3,5,10,20,100,1000) through the **public** `pytrec_eval.RelevanceEvaluator`; prints mean NDCG@k and the queries with NDCG > 1 or NaN |
| `repro_ext.py` | same, but calls the C extension `pytrec_eval_ext.RelevanceEvaluator` **directly**, bypassing the 0.5.8 Python filter |
| `ext_tiny.py` | 4-query minimal version (`q2: {}`) against the C extension |
| `neg_only.py` | a query whose only judgments are `-2`; segfaults on 0.5.10 via the public API |
| `huge_rel.py` | relevance `10**12`; 0.5.10 silently scores the *next* query 0 |
| `empty_run.py` | empty ranking; `num_rel` depends on whether it is the first call in the process |
| `perq.py` | per-query dump, used to show every query after `"63"` frozen to the same values |
| `sweep.sh VENV OUTPREFIX [SCRIPT]` | runs SCRIPT for `PYTHONHASHSEED=0..200` (4 in parallel), writes `.per_seed.tsv` and `.distinct.txt` |
| `trec_eval_cli/` | command-line trec_eval reproducer (`qrels.neg2`, `results`) and before/after/ASan output |
| `outputs/` | all raw outputs referenced below |

## Builds compared

- **0.5.7**: `pip install pytrec-eval-terrier==0.5.7` (manylinux wheel), from before the Python-level filter.
- **0.5.10**: terrierteam/pytrec_eval master `af2270d` built from source, trec_eval submodule `de6a29f`. The PyPI 0.5.10 wheel gives identical results on the public API.
- **fixed**: `af2270d` + `pytrec_eval.patch`, same trec_eval submodule.
- **fixed + TE**: fixed pytrec_eval built against usnistgov/trec_eval master `ba38899` + `trec_eval.patch`.

## Results: distinct outcomes over 201 hash seeds (dummy.json)

| build / entry point | distinct | NDCG@3 values (runs) | runs with NDCG > 1 | crash / no output |
|---|---|---|---|---|
| 0.5.7, public API | **4** | 1.479 (98), 0.77988 (81), 0.74552 (7) | **98** | **15** |
| 0.5.10, public API | 1 | 0.75521 (201) | 0 | 0 |
| 0.5.10, C extension direct | **2** | 1.479 (97), 0.77988 (104) | **97** | 0 |
| fixed, C extension direct | **1** | 0.74552 (201) | **0** | 0 |
| fixed, public API | 1 | 0.75521 (201) | 0 | 0 |

- 0.75521 is the correct NDCG@3 with the empty query dropped (77 queries). 0.74552 is the correct value with the empty query kept and scored 0 (78 queries; 0.75521 x 77/78).
- 1.479 / 1.48225 / 1.4872 / 1.49091 and 0.77988 / 0.61173 / 0.45984 / 0.35702 are **exactly** the two outputs posted in mteb#3030 and pytrec_eval#57. The "normal" one is wrong as well.
- Per-query view (`outputs/perq_057_2.json` vs `outputs/perq_head.json`): on 0.5.7, the 63 queries from `"63"` onward all have identical values (P@1 = 0, recall@10 = 1.0, NDCG@10 = 1.631).

Source files: `outputs/before_0.5.7.*`, `after_0.5.10_public_api.*`, `head_0.5.10_ext_direct.*`, `fixed_ext_direct.*`, `fixed_public_api.*`.

## Deterministic trigger (glibc)

`GLIBC_TUNABLES=glibc.malloc.tcache_count=0 MALLOC_PERTURB_=N` makes glibc fill every new allocation with the byte `~N`. The tcache has to be off, because tcache hits skip perturbation. The end marker's `rel` then becomes `0xFEFE...` (negative, so the `memset` crashes) for N=1, or `0x7F7F...` (huge, so the allocation fails and the cache is poisoned) for N=128. `outputs/malloc_perturb.tsv` has the sweep without the tcache setting. It shows that perturbation alone is *not* enough, because the marker usually comes from the tcache, whose key field is zeroed on allocation.

## Tool evidence

- **valgrind** (`outputs/valgrind_0.5.7_excerpt.txt`): `PYTHONMALLOC=malloc valgrind --track-origins=yes python repro_dummy.py` on 0.5.7:
  - "Conditional jump or move depends on uninitialised value(s)" at `te_chk_and_malloc (utility_pool.c:33)` <- `te_form_res_rels (form_res_rels.c:158)`, and further uses at `:162` and `:243`;
  - origin: "Uninitialised value was created by a heap allocation ... pytrec_eval.cpp:154".
  - After the fix (`outputs/valgrind_after_summary.txt`), no error context has a trec_eval frame. The remaining reports are in CPython itself, plus the pre-existing `new[]`/`free` mismatch.
- **ASan+UBSan**: extension built with `CFLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer -O1 -g"`, run with `LD_PRELOAD=$(gcc -print-file-name=libasan.so):$(gcc -print-file-name=libubsan.so)`, `ASAN_OPTIONS=detect_leaks=0:alloc_dealloc_mismatch=0`. ASan's malloc fills new memory with `0xbe`, so the bug is deterministic under it.
  - before (`outputs/asan_before.out`): `WRITE of size 17723342345328784888` in `memset` at `form_res_rels.c:162`, from `te_calc_P`, from `pytrec_eval.cpp:652`;
  - after (`outputs/asan_after.out`, `asan_after_repro_ext.out`): clean.
  - `alloc_dealloc_mismatch=0` suppresses an unrelated, pre-existing `new[]`-vs-`free` report in `RelevanceEvaluator_init`.
- **Instrumented trace** (`outputs/debug_trace_seed2_instrumented.txt`, a throwaway build with `fprintf`s):
  ```
  DBG qid=63 nq=0 max_rel=140238406040352 max_rel_levels(before)=2
  DBG calc P qid=63 rc=-1            <- first measure: allocation fails, UNDEF
  DBG calc recall qid=63 rc=1 v0=0.5 <- cache hit: previous query's RES_RELS
  DBG qid=64 nq=4 max_rel=1 max_rel_levels(before)=140238406040355   <- poisoned bound
  DBG calc P qid=64 rc=-1 ...        <- and so on for every later query
  ```
  `max_rel` = 140238406040352 = `0x7f8bcc603b20` is a leftover pointer, not a relevance label. In another run it was `0x7f9304203b20`: the same low bits `...03b20` with a different ASLR base. So it is most likely the same glibc `main_arena` bin address (a libc address), left in the `bk` field of a freed chunk, which overlaps the marker's `rel` field.

## Unit tests

- `outputs/pytest_before.txt`: master `af2270d` with the new tests: `11 failed, 7 passed`. All 10 `test_empty_qrels_c_extension` subtests fail (segfault -11, or `ndcg_cut_3` 1.6309 != 0.0), and `test_failed_measure_raises` fails.
- `outputs/pytest_after.txt`: with the fix: `8 passed, 10 subtests passed`.
- trec_eval: `make quicktest` passes before (without the new case) and after (with it). The new case segfaults on master (`trec_eval_cli/before.txt`, exit 139) and ASan reports `negative-size-param` (`trec_eval_cli/before_asan.txt`).

## Other edge cases (`outputs/api_edge_cases.txt`, `outputs/empty_ranking.txt`)

| input | 0.5.10 (PyPI) | fixed pytrec_eval | fixed + trec_eval patch |
|---|---|---|---|
| query with only `-2` judgments (public API) | **segfault** | segfault (needs the submodule bump) | correct (q2 = 0, neighbours unaffected) |
| relevance `10**12` | q2 silently 0 | `RuntimeError` | `RuntimeError` |
| empty qrels via the C extension | stale / NDCG > 1 | correct | correct |
| empty ranking, first call in process | `num_rel` = 0 (vs 2 later) | same (kept on purpose) | `num_rel` = 2 |

## Commands

```bash
# builds (examples)
python -m venv v && v/bin/pip install numpy pytest && v/bin/pip install ./pytrec_eval
# sweeps
./sweep.sh /path/to/venv outputs/NAME repro_dummy.py   # public API
./sweep.sh /path/to/venv outputs/NAME repro_ext.py     # C extension direct
# deterministic single run
GLIBC_TUNABLES=glibc.malloc.tcache_count=0 MALLOC_PERTURB_=128 python repro_ext.py
# trec_eval CLI
./trec_eval -q -m ndcg trec_eval_cli/qrels.neg2 trec_eval_cli/results
```
