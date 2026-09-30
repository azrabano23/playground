# profile

Source for the GitHub profile README, generated from verified data rather than written by hand.

The problem it solves: the patch branches in my forks are invisible. A visitor sees
`azrabano23/llama.cpp — forked from ggml-org/llama.cpp` and reasonably reads it as a bookmark,
because the default branch is a synced mirror and the work sits on a branch beside it.

## Files

| File | What it is |
|---|---|
| `upstream-prs.tsv` | Pull requests opened against upstream, from the GitHub PR search: `project`, `number`, `state`, `title` |
| `patch-branches.txt` | Authored branches found in forks, confirmed by commit authorship: `fork`, `branch`, `author`, `date`, `subject`, pipe-separated |
| `fork-parents.txt` | Fork to upstream-parent mapping, used for display names |
| `generate.py` | Builds `CONTRIBUTIONS.md` and `README-profile.md` from the three files above |
| `CONTRIBUTIONS.md` | Generated: every pull request grouped by project, plus the patches not yet submitted |
| `README-profile.md` | Generated: drop-in replacement for the README of the `azrabano23/azrabano23` profile repo |

## Regenerating

```sh
python3 generate.py
```

Then copy `README-profile.md` to `README.md` and `CONTRIBUTIONS.md` in the profile repo.

## What is deliberately not claimed

GitHub's pull request search exposes `open` and `closed` only. A closed pull request may have
been merged or declined, and the two cannot be told apart without reading each one, so
`CONTRIBUTIONS.md` reports the state verbatim and claims no merges.

Likewise, a branch is not called unsubmitted just because its subject matches no pull request
title: a branch is often a later revision pushed to a pull request that is already open, which
is why `NVIDIA/warp` carries two GH-1734 branches against one title. Only projects with no pull
request at all are listed as unsubmitted; projects holding more branches than pull requests are
flagged separately for a human to check.
