# Issue comments

## 1. embeddings-benchmark/mteb#3030

I tracked this down to the C layer. Summary:

**Root cause.** The one query in the attached file whose qrels are empty (`"63": {}`) makes trec_eval read uninitialised memory.

- pytrec_eval allocates `n + 1` qrel entries per query and marks the end of the list with `docno = NULL`, but leaves that entry's `rel` field unset (`pytrec_eval.cpp:154/180`).
- trec_eval's `te_form_res_rels` starts with `max_rel = text_qrels[0].rel` without checking the count (`form_res_rels.c:145`). For an empty dict, entry 0 is that unset end marker, so `max_rel` is heap garbage, and it is used to size and `memset` a buffer. Valgrind shows the uninitialised value from `pytrec_eval.cpp:154` used at `form_res_rels.c:158/162`.
- What happens next depends on the garbage value:
  - **negative:** segfault;
  - **large:** a multi-GB `memset` (slow, or OOM-killed);
  - **too large to allocate:** trec_eval has already recorded query 63 as "cached" and already freed its old buffer. Every later measure and query is then served the *previous* query's cached result, with a dangling pointer, and pytrec_eval ignores the error code. So query "63" and all 62 queries after it get the same stale numbers (per query, P@1 = 0, recall@10 = 1, NDCG@10 = 1.631). That gives the mean NDCG@10 of 1.487.

**Why it changes between runs.** The garbage is whatever the allocator hands back, which depends on the process's heap layout. For CPython that depends on `PYTHONHASHSEED`, the platform and allocator (probably why macOS/Windows looked stable: different allocators hand back different leftover bytes), and what ran earlier in the process. Within one process the layout repeats, so results are stable inside a run.

**Numbers** (this file, `PYTHONHASHSEED=0..200`, Linux / glibc 2.39):

| | distinct results | runs with NDCG > 1 | crashes |
|---|---|---|---|
| pytrec-eval-terrier 0.5.7 | 4 | 98 | 15 |
| pytrec-eval-terrier 0.5.10 | 1 | 0 | 0 |

Both of your outputs are among the 0.5.7 outcomes: NDCG@3 = 1.479 (98 runs) and 0.77988 (81 runs). Note that 0.77988 is *also* wrong. The correct NDCG@3 with query 63 excluded is **0.75521**, or 0.74552 if it is kept and scored 0.

**Affected versions.** pytrec_eval (cvangysel) up to 0.5, and pytrec-eval-terrier < 0.5.8.
- terrierteam/pytrec_eval@2d4d506 (0.5.8, Aug 2025) drops empty qrels in the Python wrapper, and #3058 filters them in `AbsTaskRetrieval`.
- With 0.5.8+, results for this file are identical across all 201 seeds.

**What this means for existing results.** A result is suspect if it was computed with pytrec-eval-terrier < 0.5.8 (or `pytrec_eval` 0.5) on a retrieval task that had at least one query with an empty qrels dict before #3058. Those scores can be arbitrarily wrong, including NDCG > 1, and the wrong queries aren't limited to the empty one. (I didn't reproduce the NaN you reported. Given that later queries are scored from freed memory, I wouldn't rule it out.) They include every query evaluated after it. Checking a stored result is cheap:
- any `ndcg_at_k` > 1 is proof;
- otherwise, re-run with >= 0.5.8.

I can't re-check the specific leaderboard rows without the model outputs.

**Follow-ups:**
- mteb PR: raise the floor to `pytrec-eval-terrier>=0.5.8` (the current pin still allows 0.5.6/0.5.7);
- terrierteam/pytrec_eval PR: fix the C extension itself (zero the end marker; raise instead of returning stale values when trec_eval reports an error);
- usnistgov/trec_eval PR: guard empty and all-negative qrels in `te_form_res_rels`, and don't keep a broken cache after an error. All-negative qrels (e.g. every judgment -2) still segfault even on 0.5.10, from both pytrec_eval and the trec_eval command line.

With 0.5.8+ and #3058 merged, I think this issue can be closed once the version floor is in.

## 2. cvangysel/pytrec_eval#57

Root cause: the empty qrels dict for one query (`"63": {}` in the attached file). pytrec_eval leaves the `rel` field of each qrel list's end marker uninitialised (`src/pytrec_eval.cpp:180` only sets `docno = NULL`), and trec_eval's `te_form_res_rels` reads `text_qrels[0].rel` as the maximum relevance level even when the list is empty (`form_res_rels.c:145`). Depending on the garbage value, the run:
- crashes;
- does a huge `memset`; or
- fails an allocation after trec_eval has already cached the query id. In that case every later query gets the previous query's cached values (with a freed buffer), and `evaluate()` ignores the error.

The garbage depends on the process's heap layout, which on CPython varies with `PYTHONHASHSEED`. That is why reruns differ but repeated calls within one run agree.

On the attached file with seeds 0..200, pytrec-eval-terrier 0.5.7 (same C code path as pytrec_eval 0.5) gives 4 distinct outcomes, and 98 of the 201 runs report NDCG > 1. The fork pytrec-eval-terrier fixed the symptom in 0.5.8 (terrierteam/pytrec_eval@2d4d506) by dropping empty qrels, and gives 1 outcome. A fix for the C layer is proposed in terrierteam/pytrec_eval and usnistgov/trec_eval. Suggest pointing users to `pip install "pytrec-eval-terrier>=0.5.8"` and closing.

## 3. cvangysel/pytrec_eval#49

Same root cause as #57. An empty relevance dict (`'q2': {}`) makes trec_eval read the uninitialised relevance of the list's end marker as `max_rel` (`form_res_rels.c:145`). When the resulting allocation fails, trec_eval keeps `q2` in its per-query cache after freeing the buffer the cache points to, so `q2` and every later query get stale values.

That is exactly the "erroneous scores for that query and all later queries" you saw. It depends on the process (heap contents), so it doesn't reproduce every time. It is fixed for the public API in pytrec-eval-terrier 0.5.8+, which drops empty qrels, and the C-level fix is proposed upstream. Suggest closing in favour of `pytrec-eval-terrier>=0.5.8`.
