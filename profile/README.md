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
| `upstream-bases.tsv` | Each upstream's default branch, resolved with `git ls-remote --symref` rather than assumed — `nautilus_trader` is `develop`, and five of the twelve are `master` |
| `generate.py` | Builds the three generated files below from the four data files above |
| `CONTRIBUTIONS.md` | Generated: every pull request grouped by project, plus the patches not yet submitted |
| `README-profile.md` | Generated: drop-in replacement for the README of the `azrabano23/azrabano23` profile repo |
| `submit-unsent.sh` | Generated: a reviewable `gh pr create` per unsubmitted patch |
| `patch-readiness.md` | Hand-written from real test runs: which unsubmitted patches have a test that actually fails without the fix |

## Submitting the unsent patches

```sh
./submit-unsent.sh                      # dry run, all of them
./submit-unsent.sh llama.cpp mujoco     # dry run, only these forks
SUBMIT=1 ./submit-unsent.sh llama.cpp   # actually open it
```

Dry run is the default: opening a pull request on someone else's project notifies its
maintainers immediately and is not meaningfully undoable. Each patch prints its diffstat
against the real upstream base, and warns when a branch is more than one commit ahead —
which means the fork's base has drifted and a maintainer would see more than just the fix.
As of the last run that flags `pytrec_eval` (95 commits), `mujoco` (3) and `trec_eval` (2).

`gh` is only required with `SUBMIT=1`; a dry run just reads branches.

Read `patch-readiness.md` before submitting: six of the patches have a test confirmed to fail
without the fix, and one (`exchange_calendars`) has a test that cannot fail on a current pandas
and needs a note in its pull request.

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
