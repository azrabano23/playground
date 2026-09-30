## Summary

`te_form_res_rels` computes `max_rel` like this:

```c
max_rel = qrels_ptr->rel;   /* first qrel, unconditionally */
```

It then sizes and zeroes `rel_levels` with `max_rel + 1`. This fails in two cases.

1. **Every judgment for a topic is negative.** Negative values are allowed (unjudged pool docs, #29). With a value of -2 or below, `max_rel + 1 <= -1`. `memset(rel_levels, 0, (max_rel + 1) * sizeof(long))` then gets a negative size and **segfaults**. You can reproduce this from the command line:

   ```
   $ printf "q1 0 d1 1\nq1 0 d2 0\nq2 0 d3 -2\nq3 0 d1 1\n" > qrels
   $ printf "q1 Q0 d1 1 3.0 r\nq1 Q0 d2 2 2.0 r\nq2 Q0 d3 1 3.0 r\nq3 Q0 d1 1 3.0 r\n" > results
   $ ./trec_eval -q -m ndcg qrels results
   Segmentation fault (exit 139)
   ```

   An ASan+UBSan build reports `negative-size-param: (size=-8)` in `memset` at `form_res_rels.c:157`. With exactly -1 there is no crash. However, `saved_res_rels.num_rel_levels` is never reset for the topic, so it is carried over from the previous topic.

2. **A topic has no qrels at all** (`num_text_qrels == 0`). This cannot happen through `get_qrels`, but it does through library users such as pytrec_eval, which builds `ALL_REL_INFO` from Python dicts. `qrels_ptr->rel` is then read from beyond the list. In pytrec_eval that memory is uninitialised heap (valgrind: "Conditional jump or move depends on uninitialised value(s)" at `te_chk_and_malloc` <- `form_res_rels.c`).

   The outcome depends on the garbage value. A negative value crashes as above. A huge value makes `te_chk_and_malloc` fail, and that failure leaves two pieces of persistent static state inconsistent:

   - `current_query` has already been set to the new qid *before* the allocations. After the `UNDEF` return, the next measure for the same qid takes the cache path and gets the **previous topic's** `saved_res_rels`. Its `rel_levels` was just freed by `te_chk_and_malloc`, so this is a use-after-free.
   - `te_chk_and_malloc` has already freed the old buffer and added `needed` to `*current_bound` when `malloc` returns NULL. From then on, every call returns the NULL pointer (`needed <= *current_bound`), so every later topic fails too.

   In pytrec_eval this is the root cause of scores that change from process to process, including NDCG > 1 for every topic after the empty one (cvangysel/pytrec_eval#57 and #49, embeddings-benchmark/mteb#3030).

## Changes

- `form_res_rels.c`
  - Start `max_rel` at 0 and only read the first qrel if there is one. `rel_levels` always has room for level 0.
  - Reset `saved_res_rels.num_rel_levels` to 0 before recounting, so it cannot carry over from the previous topic.
  - Add `current_query_valid`. It is cleared before a topic is recomputed and set only after all cached values are complete, so an error can never leave a half-built cache under that qid. It is also cleared in `te_form_res_rels_cleanup`. (As a side effect, a topic literally named `no query`, or `no_query` after a cleanup, can no longer match the placeholder string and get the empty, zero-filled cache.)
- `utility_pool.c`: when `malloc` fails in `te_chk_and_malloc`, reset `*current_bound` to 0. The old space has already been freed, so the bound no longer describes allocated memory.
- `utility_pool.c` (second commit): `te_chk_and_malloc` now reserves at least one item. Before, a request for 0 items with nothing allocated yet returned NULL, which callers treat as failure. So a query with no retrieved documents gave `UNDEF` on first use, but "worked" after `te_form_res_rels_cleanup`, because it then got the freed, dangling pointer back.
  - This can't happen from the command line, where every query in the results file has at least one document.
  - It can happen through library users. In pytrec_eval, `num_rel` for an empty ranking is 0 on the first call in a process and correct on later calls.
  - No command-line test is possible for this. The pytrec_eval PR covers it.
- Test: new `quicktest` case. `test/qrels.neg_only.test` is `test/qrels.test` with every judgment for topic 302 set to -2. The expected output is `test/out.test.neg_only`.

## Behaviour

- Output is unchanged for any qrels where each topic has at least one judgment >= 0. All existing `quicktest` cases pass unchanged.
- In the new case, topics 301 and 303 are byte-identical to their lines in `test/out.test.aq`. That is, a topic with only negative judgments no longer affects its neighbours.
- Topic 302 gets `num_rel 0` and 0 for the relevance-based measures. `unj_*` and `rbp_resid` are 1.0, because all retrieved docs are unjudged.

## Testing

```
make && make quicktest                    # passes (includes the new case)
# before this change the new case segfaults:
./trec_eval -m all_trec -q test/qrels.neg_only.test test/results.test   # exit 139
# sanitizers (Linux, gcc 13):
make clean && make CC="gcc -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer"
ASAN_OPTIONS=detect_leaks=0 make quicktest   # passes, no reports
```

`detect_leaks=0` is needed only because of an existing, unrelated leak of `gains->rel_gains` in `te_calc_rbp` (m_rbp.c:65), which LeakSanitizer reports on `test/out.test.a`.

## Not changed / possible follow-ups

- `te_chk_and_realloc` has the same failure pattern (bound increased before `realloc` can fail). It is not on this code path, so I left it alone.
- `(max_rel + 1) * sizeof(long)` can still overflow for absurd relevance values (around 2^61 and above). Real qrels don't get anywhere near that. With this patch, values large enough to fail `malloc` return `UNDEF` cleanly and no longer poison later topics.
