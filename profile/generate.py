#!/usr/bin/env python3
"""Regenerate CONTRIBUTIONS.md and the profile README from the verified data files.

Inputs (all verified by inspecting git history and the GitHub PR search, not by hand):
  upstream-prs.tsv    project<TAB>number<TAB>state<TAB>title  -- PRs opened against upstream
  patch-branches.txt  fork|branch|author|date|subject         -- authored branches in forks
  fork-parents.txt    fork upstream/name                      -- fork -> parent mapping
  upstream-bases.tsv  upstream/name<TAB>branch                -- default branch, from ls-remote

Nothing here claims a PR was merged: GitHub's search exposes open/closed only, and a
closed PR may be either merged or declined. State is reported as GitHub reports it.
"""
from __future__ import annotations

import collections
import difflib
import pathlib
import re
import shlex

HERE = pathlib.Path(__file__).parent


def load():
    prs = collections.defaultdict(list)
    for line in (HERE / "upstream-prs.tsv").read_text().splitlines():
        if line.strip():
            proj, num, state, title = line.split("\t")
            prs[proj].append((int(num), state, title))
    branches = collections.defaultdict(list)
    for line in (HERE / "patch-branches.txt").read_text().splitlines():
        if line.strip():
            fork, branch, _author, date, subject = line.split("|")
            branches[fork].append((branch, date, subject.strip()))
    parents = dict(
        l.split() for l in (HERE / "fork-parents.txt").read_text().splitlines() if l.strip()
    )
    bases = dict(
        l.split("\t")
        for l in (HERE / "upstream-bases.tsv").read_text().splitlines()
        if l.strip()
    )
    return prs, branches, parents, bases


def issue_of(branch: str, subject: str) -> str | None:
    """The upstream issue a patch addresses, or None.

    Only two shapes are trusted, because a looser digit search reads the year in
    `fix-ice-carter-2025` as issue 2025:
      * a branch that literally starts `fix-<digits>-`
      * an explicit `#<digits>` in the commit subject
    """
    m = re.match(r"^fix[-/](\d+)[-/]", branch)
    if m:
        return m.group(1)
    m = re.search(r"#(\d+)", subject)
    return m.group(1) if m else None


def unsent(prs, branches):
    """Split authored branches by how certain it is that no pull request covers them.

    Subject-to-title matching alone over-reports, because a branch is often a later
    revision pushed to a pull request that is already open: NVIDIA/warp carries two
    branches for GH-1734 against one pull request title. So certainty comes from
    counting per project rather than from comparing wording.

    Returns (certain, likely):
      certain -- every branch in a project that has no pull request at all
      likely  -- projects holding more authored branches than pull requests, as
                 (project, branches, pull requests); which branch is the spare
                 needs a human to look
    """
    counts = collections.Counter()
    for proj, items in prs.items():
        counts[proj.split("/")[-1].lower()] += len(items)
    certain, likely = [], []
    for fork, items in branches.items():
        n = counts.get(fork.lower(), 0)
        if n == 0:
            certain += [(fork, b, d, s) for b, d, s in items]
        elif len(items) > n:
            likely.append((fork, len(items), n))
    return (
        sorted(certain, key=lambda x: (x[0].lower(), x[2])),
        sorted(likely, key=lambda x: x[0].lower()),
    )


def contributions_md(prs, branches, parents):
    total = sum(len(v) for v in prs.values())
    op = sum(1 for v in prs.values() for _, s, _ in v if s == "open")
    L = [
        "# Upstream contributions\n\n",
        f"{total} pull requests opened against {len(prs)} upstream projects "
        f"({op} currently open, {total - op} closed). State is as GitHub reports it; "
        "a closed pull request may have been merged or declined.\n\n",
    ]
    for proj in sorted(prs, key=lambda p: (-len(prs[p]), p.lower())):
        L.append(f"### [{proj}](https://github.com/{proj})\n\n")
        for num, state, title in sorted(prs[proj], reverse=True):
            L.append(f"- [#{num}](https://github.com/{proj}/pull/{num}) — {title} `{state}`\n")
        L.append("\n")
    certain, likely = unsent(prs, branches)
    if certain:
        L.append("## Patches authored but not yet submitted\n\n")
        L.append(
            "Each sits on a branch in my fork, rebased on upstream HEAD, in a project "
            "I have not opened a pull request against yet.\n\n"
        )
        for fork, branch, date, subject in certain:
            up = parents.get(fork, fork)
            link = f"https://github.com/azrabano23/{fork}/tree/{branch}"
            L.append(f"- **{up}** — {subject} ([`{branch}`]({link}), {date})\n")
    if likely:
        L.append("\nProjects holding more patch branches than pull requests, so one branch "
                 "there may still be unsubmitted rather than a revision of an open one: ")
        L.append(", ".join(
            f"{parents.get(f, f)} ({b} branches / {n} pull request{'s' if n != 1 else ''})"
            for f, b, n in likely
        ))
        L.append("\n")
    return "".join(L)


def readme_md(prs, branches):
    total = sum(len(v) for v in prs.values())
    top = sorted(prs, key=lambda p: (-len(prs[p]), p.lower()))
    L = [
        "parkinsons law maximizer\n\n",
        "逆水行舟，不進則退\n\n",
        "---\n\n",
        "### Upstream\n\n",
        f"{total} pull requests across {len(prs)} projects — "
        "[full list with state](CONTRIBUTIONS.md).\n\n",
    ]
    # Every project, not a top-N: at one pull request each the tail is where
    # Tesla, OpenAI and QuantLib sit, and an alphabetical cut would drop them.
    for proj in top:
        n = len(prs[proj])
        suffix = f" ({n})" if n > 1 else ""
        L.append(f"- [{proj}](https://github.com/{proj}){suffix}\n")
    L.append(
        "\nMy forks of these projects are not bookmarks: each holds the patch branch "
        "for its pull request, rebased on upstream HEAD.\n\n"
        "### Own work\n\n"
        "[loopgraph](https://github.com/azrabano23/loopgraph) is an experiment harness: a "
        "content-addressed DAG, an append-only run ledger, an int8 quantizer that emits C99, "
        "and a gate that compiles the emitted C with `-Werror` and checks it is bit-exact "
        "against the numpy reference.\n\n"
        "[myoedge](https://github.com/azrabano23/myoedge) (EMG prosthetic control after "
        "electrode shift), [wormstage](https://github.com/azrabano23/wormstage) (C. elegans "
        "connectome locomotion) and [pocketpolicy](https://github.com/azrabano23/pocketpolicy) "
        "(SO-101 arm distillation) run on it. In each, CI runs "
        "`loopgraph claims results/ledger.jsonl results/claims.json`, so every number in the "
        "README is checked against a recorded run and the build fails if one drifts.\n"
    )
    return "".join(L)


def submit_script(prs, branches, parents, bases):
    """A reviewable `gh pr create` per unsubmitted patch.

    Dry run unless SUBMIT=1, because opening a pull request on someone else's
    project is not undoable in any way that matters -- maintainers get a
    notification the moment it lands. Each patch prints its diffstat against the
    real upstream base first, so a branch that has gone stale is obvious before
    anything is sent.
    """
    certain, _ = unsent(prs, branches)
    L = [
        "#!/usr/bin/env bash\n",
        "# Generated by generate.py -- do not edit; edit the data files and regenerate.\n",
        "#\n",
        f"# {len(certain)} patches that are written and rebased but never opened upstream.\n",
        "# Dry run by default. Review the diffstat each one prints, then:\n",
        "#     SUBMIT=1 ./submit-unsent.sh            # all of them\n",
        "#     SUBMIT=1 ./submit-unsent.sh llama.cpp  # just the forks you name\n",
        "set -uo pipefail\n\n",
        'SUBMIT="${SUBMIT:-0}"\n',
        'ONLY=("$@")\n\n',
        '# gh is only needed to actually open a pull request; a dry run just reads branches.\n',
        'if [ "$SUBMIT" = 1 ]; then\n',
        "  command -v gh >/dev/null || { echo 'need the gh CLI to submit' >&2; exit 1; }\n",
        "  gh auth status >/dev/null 2>&1 || { echo 'gh not authenticated: gh auth login' >&2; exit 1; }\n",
        "fi\n\n",
        "wanted() {\n",
        '  [ "${#ONLY[@]}" -eq 0 ] && return 0\n',
        '  for p in "${ONLY[@]}"; do [ "$p" = "$1" ] && return 0; done\n',
        "  return 1\n",
        "}\n\n",
        "submit() { # fork branch upstream base title body\n",
        '  local fork="$1" branch="$2" up="$3" base="$4" title="$5" body="$6"\n',
        '  wanted "$fork" || return 0\n',
        '  echo "=== $up  <-  azrabano23:$fork@$branch  (base: $base)"\n',
        '  echo "    $title"\n',
        '  git ls-remote --exit-code --heads "https://github.com/azrabano23/$fork" "$branch" \\\n',
        '    >/dev/null 2>&1 || { echo "    SKIP: branch is gone from the fork"; return 0; }\n',
        '  local tmp; tmp="$(mktemp -d)"\n',
        '  if git -c advice.detachedHead=false clone -q --filter=blob:none --no-checkout \\\n',
        '       --depth 200 -b "$branch" "https://github.com/azrabano23/$fork" "$tmp/f" 2>/dev/null \\\n',
        '     && git -C "$tmp/f" fetch -q --depth 200 --filter=blob:none \\\n',
        '       "https://github.com/$up" "$base" 2>/dev/null; then\n',
        '    local mb; mb="$(git -C "$tmp/f" merge-base HEAD FETCH_HEAD 2>/dev/null)"\n',
        '    if [ -n "$mb" ]; then\n',
        '      local ahead; ahead="$(git -C "$tmp/f" rev-list --count "$mb"..HEAD)"\n',
        '      echo "    commits ahead of $base: $ahead"\n',
        '      # More than one commit usually means the fork base drifted or unrelated work\n',
        '      # rode along; either way a maintainer sees a diff that is not just the fix.\n',
        '      if [ "$ahead" -gt 1 ]; then\n',
        '        echo "    REVIEW: $ahead commits -- rebase onto $base so the PR is only the fix"\n',
        "      fi\n",
        '      git -C "$tmp/f" diff --stat "$mb"..HEAD | tail -6 | sed "s/^/    /"\n',
        '    else\n',
        '      echo "    (no merge base within 200 commits -- rebase before sending)"\n',
        "    fi\n",
        "  fi\n",
        '  rm -rf "$tmp"\n',
        '  if [ "$SUBMIT" != 1 ]; then echo "    dry run; set SUBMIT=1 to open it"; echo; return 0; fi\n',
        '  gh pr create --repo "$up" --base "$base" --head "azrabano23:$branch" \\\n',
        '    --title "$title" --body "$body" || echo "    gh pr create failed"\n',
        "  echo\n",
        "}\n\n",
    ]
    for fork, branch, _date, subject in certain:
        up = parents.get(fork, fork)
        base = bases.get(up)
        if base is None:
            L.append(f"# {up}: no verified base branch on record; skipped\n\n")
            continue
        issue = issue_of(branch, subject)
        body = subject if not issue else f"{subject}\n\nFixes #{issue}."
        body += (
            "\n\n<!-- Check this project's CONTRIBUTING before sending: changelog entry,"
            " test placement and commit style vary. -->"
        )
        args = " ".join(shlex.quote(a) for a in (fork, branch, up, base, subject, body))
        L.append(f"submit {args}\n\n")
    return "".join(L)


if __name__ == "__main__":
    prs, branches, parents, bases = load()
    (HERE / "CONTRIBUTIONS.md").write_text(contributions_md(prs, branches, parents))
    (HERE / "README-profile.md").write_text(readme_md(prs, branches))
    script = HERE / "submit-unsent.sh"
    script.write_text(submit_script(prs, branches, parents, bases))
    script.chmod(0o755)
    certain, likely = unsent(prs, branches)
    print(f"projects={len(prs)} prs={sum(len(v) for v in prs.values())} "
          f"unsent_certain={len(certain)} projects_to_check={len(likely)}")
