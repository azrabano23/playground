# career/ — Azra's career wiki (operating guide for agents)

This directory is a persistent knowledge base about Azra Bano, maintained by agents, following
Karpathy's LLM-wiki pattern (https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
Read this file first in any session that touches resumes, job search, applications or outreach.
Do not ask Azra to re-explain who she is or how her resume should look: it is written down here.

## Layers

| layer | path | who writes it | rule |
|---|---|---|---|
| raw sources | `raw/` | Azra (or an agent on her instruction) | immutable evidence; never edit, only add |
| wiki | `wiki/` | agents | every fact cites a raw source or a public URL |
| schema | this file | Azra + agents together | change it when a rule changes, log the change |
| tools | `resume/`, `radar/` | agents | resume builder, job-radar dashboard and agent prompts |

Private material (phone number, offer terms, interview pipeline, recruiter emails) never goes in
this repo, because the repo is **public**. It lives in Azra's Google Drive doc
**"Career Wiki — Private"** (search Drive by that title). Agents read it there.

## Start here

1. `wiki/index.md`: map of every page, one line each.
2. `wiki/profile.md`: who she is, goals, constraints, what to optimize.
3. `wiki/resume-rules.md`: the non-negotiable resume format. Read it before touching a resume.
4. `wiki/experience.md`, `wiki/projects.md`, `wiki/oss.md`, `wiki/awards.md`: the canonical bullet bank.
5. `radar/AGENTS.md`: how the hourly job radar and the resume-on-yes flow run.

## Operations

**Ingest a source.** When Azra shares a new resume, paper, offer, project or win: save the text
to `raw/` (strip phone numbers), update every wiki page it touches, reconcile conflicts
explicitly (write "Conflict: X says A, Y says B; using B because …"), update `wiki/index.md`,
append one line to `wiki/log.md`.

**Make a resume.** Follow `wiki/resume-rules.md` and `radar/AGENTS.md` § Resume flow. Start from
`resume/base.typ`, pick bullets from the bullet bank, build with `resume/build.py`. The build must
print `ok`. Never invent a number: every metric must already be in the wiki.

**Answer a question** (e.g. "which projects fit Jane Street?"): read `wiki/index.md`, open the
relevant pages, answer with citations; if the answer is reusable, file it as a wiki page.

**Lint** (weekly, or when asked): find stale claims (dates in the past marked "Present"),
contradictions between pages, bullets without a metric, links that 404, projects missing from the
bullet bank. Fix or flag them and log it.

## Conventions

- Dates: `Mon YYYY`. Graduation is **Aug 2027** on the two most recent master resumes; the
  Two Sigma variant said Dec 2027. See `wiki/profile.md` § Open questions.
- Metrics are written exactly as sourced (99.7%, 60 min → 10 s, 172 agents, 290+ teams).
- Links: use full https URLs, and check them with WebFetch before a resume ships.
- `wiki/log.md` is append-only: `YYYY-MM-DD HH:MM | op | what changed`.
