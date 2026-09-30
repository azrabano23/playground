---

## What

Raise the minimum `pytrec-eval-terrier` version from 0.5.6 to 0.5.8. The change is in `pyproject.toml` and in the matching `requires-dist` entry in `uv.lock`. The locked version is already 0.5.10, so no resolved package changes.

## Why

This closes the loop on #3030.

- In pytrec-eval-terrier **< 0.5.8**, a query whose qrels dict is empty makes trec_eval read an uninitialised relevance value. Depending on the heap contents, the run then:
  - segfaults,
  - stalls while zeroing gigabytes, or
  - gets stuck in a broken internal cache, so **every later query** in the same `evaluate()` call returns the same stale numbers. That is where the NDCG@10 = 1.487 in #3030 comes from.

  The garbage depends on the process's heap layout, so results change from run to run, and with `PYTHONHASHSEED`.
- 0.5.8 (terrierteam/pytrec_eval@2d4d506) drops empty qrels before they reach the C code.
- #3058 already filters these queries in `AbsTaskRetrieval`. However, `calculate_retrieval_scores` does not filter them itself, and it is also used for the FollowIR `og`/`changed` scores and for max-over-subqueries. The version floor is a cheap backstop for anyone who installs mteb next to an old pin.

Evidence on the reporter's `mteb_retrieval_dummy_test.json` (78 queries, query `63` has `{}`), `PYTHONHASHSEED=0..200`:

| pytrec-eval-terrier | distinct NDCG results | runs with NDCG > 1 | crashes |
|---|---|---|---|
| 0.5.7 | 4 | 98 / 201 | 15 / 201 |
| 0.5.10 | 1 (NDCG@10 = 0.76906) | 0 | 0 |

The reporter's two outputs in #3030 (NDCG@3 = 1.479 and 0.77988) are exactly two of the 0.5.7 outcomes. Both are wrong: the correct NDCG@3 is 0.75521.

The root cause is also being fixed in the C code (terrierteam/pytrec_eval and usnistgov/trec_eval PRs, linked in #3030), but this pin doesn't depend on those.

## Checklist

- [x] One-line dependency change (plus the matching `uv.lock` `requires-dist` specifier). No code changes.
- [ ] `uv lock --check` already fails on current `main` before this change (the lockfile needs regenerating). I edited only the matching specifier line, so this PR's diff stays at one dependency. Happy to run a full `uv lock` if maintainers prefer.
