# Talking points: the NDCG > 1 / nondeterminism bug (mteb#3030, pytrec_eval#57/#49)

## 1. One-paragraph summary

MTEB scores retrieval with `pytrec_eval`, a C++ Python extension that wraps NIST's C program `trec_eval`. A query with an **empty** qrels dict made trec_eval read an **uninitialised** `long` as the "maximum relevance level" and size a buffer from it. The garbage depends on the heap layout, and CPython's heap layout depends on `PYTHONHASHSEED`, so every process got different garbage. The outcomes were:
- a crash;
- a multi-GB `memset`; or
- a failed allocation. That failure left trec_eval's static per-query cache pointing at the previous query's results, with a freed buffer, and pytrec_eval ignored the error code. Every later query was then scored from stale memory, giving NDCG > 1.

0.5.8 hid this in Python by dropping empty qrels. I fixed the cause in both C layers, added deterministic regression tests, and raised MTEB's minimum version.

## 2. How pytrec_eval wraps trec_eval

- trec_eval is a CLI. It reads a qrels file and a run file, builds `ALL_REL_INFO` (per-query `TEXT_QRELS` arrays, sorted by docno) and `ALL_RESULTS`, then for each query and each measure calls `tm->calc_meas(epi, rel_info, results, tm, eval)`.
- Most measures first call **`te_form_res_rels`**. It merges the ranked list with the qrels into a `RES_RELS`: the relevance of each rank, counts per relevance level (`rel_levels`), `num_rel`, and so on.
  - Because many measures need the same `RES_RELS` for the same query, it **caches** the last result in **file-static** variables (`current_query`, `saved_res_rels`, `rel_levels`, ...).
  - The buffers are grown with `te_chk_and_malloc(ptr, &bound, needed, size)`.
- pytrec_eval compiles all of trec_eval's `.c` files, except `trec_eval.c` (`main`), into the extension and replaces file parsing with dict conversion:
  - `RelevanceEvaluator.__init__`: Python `{qid: {docid: rel}}` -> `REL_INFO[]`. `RankingBuilder` allocates `n + 1` `TEXT_QRELS` per query and uses the extra one as a `docno = NULL` end marker, which its own cleanup uses.
  - `evaluate(run)`: builds `RESULTS[]`, then loops over queries x measures calling `calc_meas`, copies `q_eval.values` into Python dicts, and calls `te_form_res_rels_cleanup()` at the end.
  - The Python layer (`py/__init__.py`) expands nicknames and merges parameterised measures (`ndcg_cut.1,3,5`).
- MTEB (`mteb/_evaluators/retrieval_metrics.py`) builds one evaluator per task split with `{map_cut, ndcg_cut, recall, P, success}` at k = 1..1000, then averages the per-query values.

## 3. The exact bug mechanism (trec_eval submodule `de6a29f`)

1. **Uninitialised end marker.** `pytrec_eval.cpp:154` does `Malloc(PyDict_Size(value) + 1, TEXT_QRELS)`, and `:180` sets only `.docno = NULL`. `.rel` is never written.
2. **Unconditional read.** `form_res_rels.c:143-145`:
   ```c
   qrels_ptr = trec_qrels->text_qrels;
   end_qrels = &trec_qrels->text_qrels[trec_qrels->num_text_qrels];
   max_rel = qrels_ptr->rel;      /* reads entry 0 even if num_text_qrels == 0 */
   ```
   On the CLI, a query only exists if it has a qrels line, so this was safe there. The library interface broke that assumption. For `{}`, entry 0 *is* the end marker, so `max_rel` = garbage.
3. **Garbage sizes a buffer.** `:157-162`: `te_chk_and_malloc(rel_levels, &max_rel_levels, max_rel + 1, sizeof(long))`, then `memset(rel_levels, 0, (max_rel + 1) * sizeof(long))`. The result depends on the garbage:
   - **0** (e.g. a tcache chunk, whose key field glibc zeroes): correct result.
   - **Negative**: `(max_rel + 1) * 8` becomes a huge `size_t`, and `memset` segfaults.
   - **Large but allocatable**: gigabytes zeroed. The run is slow or OOM-killed, but correct.
   - **Too large** (e.g. a libc pointer such as `0x7f8bcc603b20`, left in a freed chunk's `bk` field): `malloc` fails. This leads to step 4.
4. **The failure poisons two pieces of persistent state.**
   - `te_chk_and_malloc` (`utility_pool.c:35-38`) has already done `Free(ptr)` and `*current_bound += needed` *before* `malloc` returns NULL. So `rel_levels` = NULL with a bound of about 1.4e14. Every later call sees `needed <= bound`, returns the NULL pointer, and fails too.
   - `te_form_res_rels` has already copied the qid into `current_query` (`:84-88`), *before* those allocations. The first measure (P) gets `UNDEF`. The next measure for the same qid hits the cache check (`:69`) and gets `saved_res_rels` from the **previous** query, whose `rel_levels` was just freed. That is a **use-after-free**.
   - For every later query: the new qid fails, the cache gets set, and the other measures read the stale cache again.
5. **The error is swallowed.** `pytrec_eval.cpp:652` ignores `calc_meas`'s return value. `P@k` = 0 (the buffer was zeroed and the measure never wrote), while `recall`, `ndcg_cut` and `map` are computed from the previous query's `RES_RELS`. `ndcg_cut` divides by an ideal DCG built from the **freed** `rel_levels`, which gives 1.631. On the reporter's file, 63 of 78 queries are frozen to identical numbers, and the mean NDCG@10 is 1.487.
6. **Also:** `saved_res_rels.num_rel_levels` is only assigned when some level has a non-zero count (`:242-249`). A query with no judgments >= 0 therefore inherits the previous query's value. This is the same bug family, and the one reachable from the CLI (see section 7).

## 4. Why it depends on the hash seed and the process

- The value read is **whatever bytes were in that 16-byte heap chunk**. glibc hands back a recently freed chunk of the right size. Its offset-8 word (which overlays `.rel`) holds the tcache key (zeroed on allocation), a `bk` pointer into `main_arena` (a libc address, huge and positive), or leftover user data.
- Which chunk you get depends on the exact sequence of allocations and frees that came before. In CPython that sequence depends on:
  - `PYTHONHASHSEED`: string hashes drive dict/set probe sequences, resize points, and sometimes iteration order of sets, which changes which objects are allocated and freed and when;
  - the Python version, the imported modules, and the platform allocator (so macOS/Windows can look "stable": their allocators leave different bytes);
  - ASLR, which changes the high bits of any leftover pointer.
- **Dict iteration order was not the cause.** Dicts keep insertion order, so the query order never changed. It was **heap layout**, not order.
- Within one process the layout repeats, which is why "repeated calls inside one script agree".
- Observed: seed 1 gave the correct result in one serial run and 1.479 in the parallel sweep (with `ulimit`). So the seed is only one of several inputs to the heap state.

## 5. How I found it (methodology)

1. **Reproduce first.** I downloaded the reporter's JSON and swept `PYTHONHASHSEED` 0..200. On current master nothing happened, because 0.5.8 already filters `{}`. On 0.5.7 I got 4 distinct outcomes, and the reporter's exact numbers appeared. So I had a reproducer, and I knew the Python filter was masking the bug rather than fixing it.
2. **Bypass the mask.** Calling `pytrec_eval_ext.RelevanceEvaluator` directly reproduced the bug on master. That proved the C bug was still there.
3. **valgrind memcheck** with `PYTHONMALLOC=malloc` (so CPython's small-object allocator doesn't hide allocations from valgrind) and `--track-origins=yes`. It gave both the *use site* (`form_res_rels.c:158/162/243`) and the *origin* (`pytrec_eval.cpp:154`). That pins down the uninitialised read exactly.
4. **ASan + UBSan.** I built the extension with `-fsanitize=address,undefined` and ran Python with `LD_PRELOAD` of libasan/libubsan (the interpreter itself isn't instrumented). ASan fills new allocations with `0xbe`, so the garbage became deterministic, and ASan reported a `memset` of about 1.7e19 bytes at `form_res_rels.c:162`. I needed `alloc_dealloc_mismatch=0` to get past an unrelated pre-existing `new[]`/`free` mismatch, and `detect_leaks=0`.
5. **Instrumented build.** I added `fprintf`s in a throwaway copy to print `max_rel`, the bound, and each `calc_meas` return code. This showed the exact cascade: P returns -1, then recall returns 1 from the cache, and the bound stays poisoned.
6. **Deterministic trigger for CI.** `MALLOC_PERTURB_` makes glibc fill allocations with a byte. At first it didn't work, because tcache allocations skip perturbation. With `GLIBC_TUNABLES=glibc.malloc.tcache_count=0` it reproduces every time (crash with byte 1, cache poisoning with byte 128).
7. **Look for siblings.** Reading the same function showed that all-negative qrels (e.g. every judgment -2) also give `max_rel + 1 <= 0`, which is a CLI-reachable segfault in upstream trec_eval 10.0. Checking `calc_meas` return codes then revealed `te_chk_and_malloc` returning NULL for 0 items, which made empty rankings depend on process history.

## 6. The fixes and their trade-offs

**usnistgov/trec_eval** (two commits):
- Start `max_rel` at 0, and only read the first qrel if there is one. `rel_levels` always has level 0. Reset `num_rel_levels` for every query.
- Add a `current_query_valid` flag: cleared before recomputing, set only on success, cleared in cleanup. This is better than "move the `strncpy` to the end", because a failed recompute may already have freed buffers that the *old* cache points to.
- In `te_chk_and_malloc`, reset the bound when `malloc` fails, so the bound always matches the memory that is actually allocated.
- In `te_chk_and_malloc`, reserve at least one item, so a request for 0 items never returns NULL. Before, it returned NULL before the first allocation and a dangling pointer after cleanup.
- Test: a `quicktest` case with topic 302's judgments set to -2. It segfaults before. After the fix, topics 301 and 303 are byte-identical to the existing expected output. That checks that a bad topic can't affect its neighbours.
- Trade-offs:
  - Behaviour only changes for inputs that crashed or were undefined before.
  - The test adds a 3.7k-line qrels copy. I kept it because it lets me compare against an existing expected file instead of inventing new expected numbers.

**terrierteam/pytrec_eval**:
- `memset` the whole end marker, not just `docno`. This fixes empty qrels even with the old submodule: `max_rel` becomes 0, and the query scores 0 everywhere.
- Check `calc_meas`'s return value and raise `RuntimeError` on `UNDEF`. The existing cleanup still runs, so the evaluator stays usable.
- Trade-off: **silent wrong numbers become an exception.** That is the right default for an evaluation library, but it's a behaviour change. One exception is kept on purpose: `UNDEF` for an *empty ranking* keeps the old all-zeros result. Otherwise the first `evaluate({'q': {}})` in a process would start raising, and that is common input. After the trec_eval bump that case returns correct values and the exception can be removed.
- The Python-level filter from 0.5.8 stays. Public API results are unchanged.
- Tests run in **subprocesses**, because the bug depends on process state:
  - 8 hash seeds, plus 2 deterministic glibc runs (`MALLOC_PERTURB_` with the tcache disabled), all asserting exact values;
  - a test that an allocation failure raises;
  - a test that an empty ranking in a fresh process doesn't raise.

**MTEB**:
- Raise the floor to `pytrec-eval-terrier>=0.5.8`. The old `>=0.5.6` still allowed the buggy versions, and `calculate_retrieval_scores` doesn't filter empty qrels itself. #3058 already filters in `AbsTaskRetrieval`, so no MTEB code change is needed.

## 7. Impact on leaderboards

- **Affected:** any result computed with pytrec-eval-terrier < 0.5.8 (or cvangysel `pytrec_eval` 0.5) on a retrieval split that contained at least one query with an empty qrels dict, before MTEB #3058 (Aug 2025).
- **Size of the damage:**
  - it isn't limited to that query: every query evaluated after it can be stale;
  - it can inflate scores (NDCG 1.48 on the dummy file) or deflate them (0.77988 vs a correct 0.75521 is +3%; P@k frozen at 0);
  - it varies from run to run, so the same model can get different numbers.
- **Cheap triage:** any stored `ndcg_at_k > 1` proves corruption. Otherwise re-run with >= 0.5.8.
- I couldn't re-verify the specific leaderboard rows without the model outputs.
- **Still open on 0.5.10:** qrels whose judgments are all <= -2 segfault through the public API. The trec_eval PR plus a submodule bump fixes that. It's a crash, not silent corruption, so it doesn't affect published numbers.

## 8. Likely interview questions

**Q1. Why did NDCG exceed 1 at all? Isn't it normalised?**
It's DCG divided by ideal DCG. After the failed allocation, the DCG came from the previous query's cached ranking, and the ideal DCG came from a *freed* `rel_levels` buffer. That no longer describes the same query, so the ratio isn't bounded by 1.

**Q2. Why did the hash seed matter if dict order is deterministic?**
Order didn't change; the heap did. The value read is leftover bytes in a recycled 16-byte chunk. Which chunk malloc returns depends on the allocation history, and in CPython that depends on string hashing (dict/set sizes, resizes, probe sequences). The seed changes the history, and so the garbage.

**Q3. Why wasn't the 0.5.8 fix enough?**
It drops empty dicts in Python, so the public API is safe for that input. But the C code still reads uninitialised memory, still keeps a poisoned cache after errors, and still ignores error codes. Other inputs reach the same code: all-negative qrels segfault on 0.5.10, and a huge relevance value silently zeroes the next query. Direct users of the extension are unprotected. It treated the symptom, not the cause.

**Q4. How did valgrind pinpoint it, and why `PYTHONMALLOC=malloc`?**
`--track-origins=yes` reports both where an uninitialised value affects control flow (`form_res_rels.c:158`) and where it was allocated (`pytrec_eval.cpp:154`). `PYTHONMALLOC=malloc` makes CPython use the system malloc for everything, so valgrind sees each allocation instead of large pymalloc arenas.

**Q5. How do you write a regression test for a heisenbug?**
Take away the randomness. Under glibc, `MALLOC_PERTURB_=N` fills new allocations with `~N`. The tcache skips that, so I also set `GLIBC_TUNABLES=glibc.malloc.tcache_count=0`. That fails every time on the old code. Each case runs in a fresh subprocess, because the bug depends on process state, and I assert exact per-query values, not just "no crash". I also sweep hash seeds for platforms that ignore those variables.

**Q6. Why fix it in both pytrec_eval and trec_eval?**
Each layer had its own defect. pytrec_eval handed trec_eval uninitialised memory and ignored errors. trec_eval assumed at least one non-negative judgment and kept inconsistent static state after errors. Fixing both is defence in depth. The pytrec_eval fix ships without waiting for NIST; the trec_eval fix also covers its own CLI crash and other bindings.

**Q7. Why raise an exception instead of returning 0 for a failed measure?**
A benchmark number that is silently wrong is worse than a crash, because it gets published. `UNDEF` means trec_eval couldn't compute a value, and there is no correct number to return. The one exception is the empty-ranking quirk, where trec_eval's `UNDEF` is itself a bug and the old result (0) was acceptable. I kept that so a common input doesn't start raising.

**Q8. Why the `current_query_valid` flag instead of just updating `current_query` at the end?**
Because the *old* cache can also be invalid after a failed recompute: `te_chk_and_malloc` may already have freed `rel_levels` or `ranked_rel_list`, and `saved_res_rels` still points at them. So an error has to invalidate the cache completely, not just leave the old key in place. A flag also removes the magic placeholder string (`"no query"`), which could match a real qid.

**Q9. What's the blast radius of your trec_eval change for normal CLI users?**
Output for every existing input with at least one judgment >= 0 per topic is unchanged, and all existing `quicktest` cases pass, also under ASan/UBSan. The only differences are for inputs that used to crash, or be undefined: all-negative topics, allocation failure, and requests for 0 items. I checked that the neighbouring topics' output is byte-identical to the existing expected file.

**Q10. What would you check next / what's still open?**
- The pytrec_eval submodule bump once NIST merges (it could go with terrierteam#13, TE10).
- The same "bound bumped before failure" pattern in `te_chk_and_realloc`.
- Integer overflow in `(max_rel + 1) * sizeof(long)` for absurd relevance values.
- The pre-existing `new[]` vs `free` mismatch in pytrec_eval's string handling.
- An MTEB-side audit of stored results for `ndcg > 1`.

## 9. Numbers to remember

- 201 seeds. Before (0.5.7): **4 distinct outcomes, 98 runs with NDCG > 1, 15 crashes**. After: **1 outcome, 0 > 1, 0 crashes**. C extension directly on master: 2 outcomes, 97 > 1. With the fix: 1 outcome.
- Correct NDCG@3 on the dummy file: **0.75521** (77 queries; 0.74552 if the empty one counts as 0). Reporter's numbers: 1.479 and 0.77988. Both are wrong.
- Key lines:
  - `pytrec_eval.cpp:154` / `:180` (allocation, end marker)
  - `:652` (ignored return code)
  - `form_res_rels.c:69` (cache hit)
  - `:84-88` (qid recorded early)
  - `:145` (unchecked read)
  - `:157-162` (allocation + `memset`)
  - `utility_pool.c:35-38` (bound bumped before `malloc`)
