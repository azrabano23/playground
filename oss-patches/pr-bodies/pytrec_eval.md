## Background

0.5.8 (2d4d506) fixed cvangysel/pytrec_eval#57 by dropping queries with an empty qrels dict in the Python wrapper. That fixes the symptom for `pytrec_eval.RelevanceEvaluator`. The underlying memory bug is still in the extension, though: it can still be reached through `pytrec_eval_ext.RelevanceEvaluator`, and `evaluate()` still hides trec_eval errors. This PR fixes the cause.

## Root cause

1. `RankingBuilder` allocates `PyDict_Size(value) + 1` pairs per query (`src/pytrec_eval.cpp:154`). It only sets the end marker's `docno = NULL` (`:180`); the marker's `rel` field is left uninitialised.
2. trec_eval's `te_form_res_rels` starts with `max_rel = text_qrels[0].rel` without checking the count (`trec_eval/form_res_rels.c:145`). For an empty dict, entry 0 *is* the end marker, so `max_rel` is heap garbage. It is then used to size and `memset` `rel_levels` (`:157-162`). Valgrind confirms this: "Uninitialised value was created by a heap allocation at pytrec_eval.cpp:154", used at `form_res_rels.c:158/162/243`. ASan reports a `memset` of about 1.7e19 bytes at `form_res_rels.c:162`.
3. What happens next depends on the garbage value:
   - **Negative:** segfault.
   - **Large:** a multi-GB `memset`, which is slow or gets the process OOM-killed.
   - **Too large to allocate:** `te_chk_and_malloc` fails *after* freeing `rel_levels` and adding to its bound, and `te_form_res_rels` has already recorded the qid as cached. The following measures for that query then get the previous query's cached `RES_RELS`, with a dangling `rel_levels`. Every later query fails the same way.
4. `evaluate()` ignores the return value of `calc_meas` (`:652`). So from the empty query onward, every query silently gets the same stale numbers: `P` = 0, `recall` = 1, and `ndcg_cut` normalised by freed memory (e.g. 1.63).
5. The garbage is whatever the allocator hands back, which depends on the heap layout of the process. Python's heap layout depends on `PYTHONHASHSEED` (dict/set sizes and resizes), the platform, and what ran before. That is why the scores in #57 and mteb#3030 changed from one run to the next but stayed the same within a run.

## Changes

- Zero the whole end marker (`memset(&pairs[n], 0, sizeof(PairT))`), not just `docno`. trec_eval then sees relevance 0 for an empty qrels list. The per-query result is well-defined: every measure is 0, as for a query with no relevant documents, and later queries are unaffected. This works with the current trec_eval submodule.
- Check the return value of `calc_meas`. On `UNDEF`, raise `RuntimeError("trec_eval failed to compute measure <m> for query <q>.")` instead of returning whatever is left in the buffers. The existing cleanup still runs (`print_final_and_cleanup_meas`, `builder.cleanup`, `te_form_res_rels_cleanup`), so the evaluator can still be used afterwards.
  - An existing case that silently gave wrong numbers is `{'q1': {'d1': 10**12}, 'q2': {'d1': 1}}`. On 0.5.10, `q2` scores `P_1 = 0, ndcg = 0` instead of 1. It now raises.
  - One exception is kept on purpose: an **empty ranking** (`{'q1': {}}`). trec_eval's `te_chk_and_malloc` returns NULL for a request of 0 items if nothing has been allocated yet, so the very first evaluation in a process reports `UNDEF` for it. After any earlier evaluation it "succeeds", because it reuses a freed pointer. To avoid turning a common input into an exception, `UNDEF` for a query with 0 retrieved documents keeps the old result (all zeros).
  - Side effect of this trec_eval quirk on 0.5.10 (see `repro/outputs/empty_ranking.txt`): `num_rel` for an empty ranking is 0 on the first call in a process and 2 on later calls. The trec_eval PR fixes that too; after a submodule bump the exception can be removed.
- The Python-level filter from 0.5.8 is unchanged. Public API results are identical to 0.5.10.

## Tests

- `test_empty_qrels_c_extension`: calls `pytrec_eval_ext.RelevanceEvaluator` with `{"q2": {}}` between normal queries. Each run is a fresh interpreter (`subprocess`), for `PYTHONHASHSEED=0..7`. There are also two glibc runs with `MALLOC_PERTURB_=1` and `MALLOC_PERTURB_=128`, both with `GLIBC_TUNABLES=glibc.malloc.tcache_count=0`. Tcache allocations are not perturbed, so the tcache has to be off for the fill to reach the marker; this makes the bug deterministic on glibc. The test asserts exact per-query values. Other platforms ignore these variables and still exercise the seeds.
- `test_failed_measure_raises`: the `10**12` case above raises `RuntimeError`, and the evaluator still works afterwards.
- `test_empty_ranking_in_fresh_process`: an empty ranking as the first evaluation in a fresh interpreter does not raise.

Results:

```
master (af2270d):  11 failed, 7 passed   (all 10 subtests + test_failed_measure_raises)
this branch:       8 passed, 10 subtests passed in 0.92s
```

Sweep of the reporter's file from mteb#3030 (78 queries, one empty), calling the C extension directly, PYTHONHASHSEED=0..200:

| build | distinct results | runs with NDCG > 1 |
|---|---|---|
| master af2270d | 2 (97 x NDCG@3 = 1.479, 104 x 0.77988; both wrong) | 97 / 201 |
| this branch | 1 (NDCG@3 = 0.74552, the empty query scored 0) | 0 / 201 |

Through the public API (empty query dropped), both give 1 distinct result: NDCG@3 = 0.75521.

## Related: trec_eval submodule

A qrels dict whose judgments are **all <= -2**, e.g. `{'q2': {'d1': -2}}`, still segfaults **through the public API**, on 0.5.10 and on this branch. `max_rel + 1` is negative and the `memset` gets a negative size. The empty-dict filter doesn't catch it, and a fix in the extension would only duplicate trec_eval logic. The fix belongs in trec_eval, and I've sent it upstream (usnistgov/trec_eval PR: "Fix te_form_res_rels crash/stale values for topics with no non-negative judgments"). That PR also:
- makes the per-query cache robust to errors;
- resets `te_chk_and_malloc`'s bound when `malloc` fails;
- makes `te_chk_and_malloc` return usable space for a request of 0 items, which fixes the empty-ranking case above.

I built this branch against that trec_eval change. The new tests pass, the all-negative case returns `q2: P_1 = 0, ndcg = 0` with neighbours unaffected, and an empty ranking gets `num_rel = 2` on the first call.

The existing `test_nicknames` fails against trec_eval master because TE10 adds measures (`unj_*`, `rbp`, `rbp_resid`) to `all_trec`; that is what #13 handles. For comparison, unpatched pytrec_eval against unpatched trec_eval master **segfaults** in that test. **Once the trec_eval PR is merged, the submodule should be bumped** (it could go in with #13), and a public-API test for all-negative qrels can be added then.

## Notes

- A separate, pre-existing issue: `CopyCString` uses `new[]`, but the memory is released with trec_eval's `Free` (`free`). ASan reports `alloc-dealloc-mismatch` in `RelevanceEvaluator_init` (`pytrec_eval.cpp:414` and in cleanup). It is harmless with glibc but undefined behaviour. I left it out of this PR to keep it focused; I'm happy to send a follow-up.
