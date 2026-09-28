# Job radar: the hourly agent graph

Runs every hour as a Claude Code routine ("Job Radar hourly"). Each run is a fresh session, so
everything it needs is in this file, the wiki, and the dashboard's database.

- **Dashboard:** https://claude.ai/artifact/534oBzYhipqSatwCJgc3r3 (source `radar/job-radar.html`).
  Its database is read and written with the `ArtifactData` tool (load via ToolSearch).
- **Private facts:** dashboard DB doc `meta/private` (phone, canonical grad date, pipeline,
  do-not-resurface list). The dashboard is private to Azra. A fuller human copy is the Google Drive
  doc **"Career Wiki — Private"**, but routine sessions have no Drive connector, so they use the DB doc.
- **Resume builder:** `career/resume/build.py` (needs `pip install typst pymupdf`).

The shape follows Anthropic's guidance on effective agents: an **orchestrator** routes work to
narrow **workers** in parallel, and an **evaluator** gates their output before anything reaches
Azra. Workers return structured JSON, not prose.

```
                 ┌──────────── load state ────────────┐
                 │ wiki/profile.md · private doc ·    │
                 │ ArtifactData list jobs, programs   │
                 └───────────────┬────────────────────┘
          ┌──────────────────────┼──────────────────────────┐
          ▼                      ▼                          ▼
  A. RESUME-ON-YES       B. SCOUTS (parallel)        C. PROGRAMS (1×/day, 12 UTC run)
  one worker per row     aggregator · AI labs &      KP Fellows, a16z speedrun, YC,
  status=="yes" and      startups · quant & HW       Contrary, Anthropic Fellows,
  no resume_url          → candidates JSON           Z Fellows → programs/*
          │                      │
          ▼                      ▼
  drafter → critic →     D. EVALUATOR: dedupe, eligibility, US, comp, freshness,
  build.py gate →           fit score, verify posting is open  → top 5–10 (never pad)
  asset upload →                 │
  row update                     ▼
                         E. REFERRALS: Rutgers alumni search + DM draft per kept job
                                 │
                                 ▼
                         F. WRITE: ArtifactData batch → jobs/*, meta/radar; prune; log
```

## 0. Setup (every run)

1. Get the repo: `git clone -q https://github.com/azrabano23/playground && cd playground`. If
   `career/` is missing (the PR that adds it is not merged yet):
   `git fetch -q origin claude/sleepy-wright-h3e4gl && git checkout FETCH_HEAD -- career`.
2. Read `career/CLAUDE.md`, `career/wiki/profile.md`, `career/wiki/resume-rules.md`.
3. `ArtifactData get` `meta/private` (phone, grad date, pipeline, do-not-resurface list).
4. `ArtifactData list` collection `jobs` (all pages) and `programs`, and `get` `meta/radar`.
   Build the set of known posting URLs and companies to exclude.
5. **Exa (preferred when available).** If `mcp__exa__*` tools are loaded, use them first.
   `web_search_exa` with `category:people <Company> Rutgers University` returns LinkedIn
   profiles showing current employer and school, which is the best alumni source (verified
   2026-09-28: found OpenAI, HRT, Jane Street and Anthropic alumni that plain search missed).
   `agent_run` with an `outputSchema` works well for "postings published since <date>" sweeps,
   and it reads each ATS page's "Published" date. Scheduled routines only get Exa if Azra
   attaches the connector to the routine in the claude.ai routines UI.
6. **Network:** the container's shell proxy blocks most job boards (greenhouse, ashby, lever,
   company career sites, linkedin, levels.fyi). Use the `WebSearch` and `WebFetch` tools, not
   curl. `raw.githubusercontent.com` and `github.com` do work.

## A. Resume-on-yes (do this first; it is what Azra is waiting on)

For every `jobs/*` row with `status == "yes"` and no `resume_url`, run one worker (subagent):

1. **Read the posting** (WebFetch the `url`; if blocked, WebSearch the title + company and use
   the snippet or a mirror). Extract the top 3–5 requirements, in the posting's words.
2. **Draft**: copy `career/resume/base.typ` to `career/applications/<job-id>/resume.typ`.
   Reorder and swap bullets from the wiki bullet bank (`wiki/experience.md`,
   `wiki/projects.md`, `wiki/oss.md`, `wiki/awards.md`) using the "Tailoring by track" table
   in `resume-rules.md`, so the first third of the page answers those requirements. Only facts
   from the wiki; no new numbers.
3. **Critic** (a separate subagent that did not write the draft): check against every rule in
   `resume-rules.md` (one page, black, stack line on every entry, problem → impact → number,
   banned words, accuracy against the wiki, required categories present). It returns a list of
   violations. Fix them and re-run the critic, at most 3 rounds.
4. **Gate**: `python career/resume/build.py career/applications/<job-id>/resume.typ` must print
   `ok`. The phone number comes from `meta/private` via env `RESUME_PHONE`.
   WebFetch every link it prints; drop or fix any that fail.
5. **Deliver**: name the file `Azra_Bano_<Company>_<Role>.pdf` and upload it to the dashboard's
   asset store: `Artifact` tool, `action: "publish"`, `url` = the dashboard URL, `file_path` = the PDF,
   `asset: true`. Then `ArtifactData update` `jobs/<id>` (pinned with `if_version`) with
   `resume_url` = the `url` the upload returned (exactly as given), `resume_asset_id`,
   `resume_notes` (3–5 lines on what was emphasized and why), and `referral_dm` if missing. If a
   Google Drive connector happens to be available, also upload a copy to the Drive folder
   "Tailored Resumes".
6. Do not commit tailored resumes to the public repo.

## B. Scouts (parallel workers; each returns candidates JSON)

Each scout returns `[{company, title, url, location, posted_at, kind, track, comp_text,
comp_low_usd, equity, source, evidence}]`. `posted_at` is ISO 8601 and must come from evidence
(posting text, the ATS "updated" date, or the aggregator's `date_posted`). Unknown means null,
never a guess.

1. **Aggregator scout.** Structured lists on raw.githubusercontent.com, diffed against the DB:
   SimplifyJobs `Summer2027-Internships` and `New-Grad-Positions` (their `.github/scripts/
   listings.json` carries `date_posted`, `active`, `is_visible`, `terms`, `locations`),
   vanshb03/Summer2027-Internships, speedyapply 2027 lists, northwesternfintech quant lists.
   Keep only `active && is_visible`, US locations, and entries from the last 21 days.
2. **Frontier AI and startups scout.** WebSearch, for example
   `site:jobs.ashbyhq.com OR site:job-boards.greenhouse.io ("new grad" OR "2027" OR "intern")
   <company>`, across OpenAI, Anthropic, Google DeepMind, Meta superintelligence/FAIR, xAI,
   Thinking Machines, SSI, Perplexity, Cursor, Cognition, Physical Intelligence, Figure, Skild,
   Decagon, Harvey, Sierra, Mistral (US), Together, Fireworks, Modal, Baseten, Etched, MatX,
   Cerebras, Groq, Tenstorrent, NVIDIA; plus a16z portfolio (jobs.a16z.com) and YC Work at a
   Startup search results. Zero2Sudo posts on Instagram/TikTok are not indexable; use a WebSearch
   for "zero2sudo" plus the week to catch any mirrored lists.
3. **Quant and hardware scout.** Jane Street, HRT, Citadel / Citadel Securities, Jump, Two Sigma,
   DE Shaw, SIG, IMC, Optiver, Five Rings, Radix, Tower, Headlands, DRW, XTX, Virtu, Old Mission,
   Akuna, Squarepoint, Point72/Cubist, plus FPGA / hardware / performance-engineer roles.

## C. Programs (only on the run whose UTC hour is 12)

Refresh `programs/*`: KP Fellows, a16z speedrun, YC (next batch deadline plus Early Decision),
Contrary, Z Fellows, Neo Scholars, Anthropic Fellows, OpenAI residency, MATS, Cohere Scholars.
Document shape: `{name, org, deadline (ISO date or null), deadline_text, url, note, status}`.

## D. Evaluator (the gate; run it yourself or as one subagent)

Drop a candidate if any of these hold:
- Already in the DB (same URL, or same company + title), or the company/role is on the
  `meta/private` do-not-resurface list (rejections with a cooldown, roles already applied to).
- Not in the US, or PhD-only, or senior-only (4+ years required).
- Eligibility clashes with her graduation date (the private doc has the canonical date;
  e.g. "must graduate Dec 2027 or later" for an Aug 2027 grad). Keep borderline cases but
  put the clash in `why`.
- Comp is known and below target (new grad total comp < $250k; intern < ~$55/hr), unless the
  company is a frontier lab or tier-1 quant firm where the door matters more than the number.
- The posting is not verifiably open: an aggregator saying `active` plus a search hit counts;
  a 404 or "no longer accepting" does not.

Score `fit` from 0 to 100: track match with her ranked goals (40), evidence her projects match
the stated requirements (25), comp/equity against the $350–400k goal (15), freshness (10; ≤48h
full, ≤7d half), eligibility certainty (10). Keep the top **5–10** with fit ≥ 60. If fewer
qualify, write fewer. Never pad with weak roles.

## E. Referrals

For each kept job: `alumni_search_url` =
`https://www.linkedin.com/search/results/people/?keywords=<Company>%20Rutgers`. Then Exa
`category:people <Company> Rutgers University` (or, without Exa, WebSearch
`site:linkedin.com/in "Rutgers" "<Company>"`) and record up to 3 **public** matches as
`{name, role, url}`, only if the snippet shows both Rutgers and the company. Never guess.
Write `referral_dm`: at most 5 sentences, specific, no flattery, of this shape:
"Hi <first name>, I'm a Rutgers ECE + Math student (Google SWE intern this summer, YouTube Ads
infra). I'm applying to <role> and saw you're at <Company> after Rutgers. <one line tying her
most relevant project to the team>. Would you be open to a 10-minute chat, or to referring me
if it seems like a fit? <posting URL>"

## F. Write, prune, log

- `ArtifactData batch` `set` on `jobs/<id>` where `id` = `<company-slug>-<ats-id or 8-char hash of
  url>`. Fields: `company, title, url, location, posted_at, found_at (now), kind
  (newgrad|intern-summer|intern-spring|fellowship), track (ai-research|quant|perf|hardware|swe),
  comp_text, comp_low_usd, equity, fit, why (≤ 2 sentences, name the matching project),
  source, alumni_search_url, alumni[], referral_dm, status: "new", batch (run hour ISO)`.
  Never overwrite `status`, `resume_url` or `decided_at` on an existing row.
- `set` `meta/radar` = `{last_run, last_count, note}`. `note` is one short line, e.g. "12 checked,
  7 kept, 2 resumes built".
- Prune: if the DB has more than 1,500 job docs, delete `status in (new, pass)` rows older than
  30 days.
- Notable events (a fit ≥ 85 posting under 48 hours old, or a resume built) go in `meta/radar`
  field `log`: an array of `"YYYY-MM-DD HH:MM | event"` strings, newest first, max 50. The Drive
  connector cannot edit an existing doc, so the private doc is updated only by Azra or an
  interactive session.
- **Writes to an existing doc need `if_version`** (from the `list` in step 0). If a pinned write
  fails because Azra just changed the row, re-read that row and redo the write; never drop her
  status change.
- The final message of the run is the notification text: lead with the best new posting and the
  number of resumes built. If nothing new, say so in one line.

## Failure modes seen so far

- 2026-09 Signalboard runs failed for 3 weeks because they used the shell to reach job boards.
  Use WebSearch / WebFetch and GitHub raw files instead.
- Comp numbers from search snippets are unverified. Label the source in `comp_text`, e.g.
  "$300k base (posting via search)".
