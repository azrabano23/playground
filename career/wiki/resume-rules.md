# Resume rules

Azra's standing instructions. They apply to every resume, every time. Source: her own words
(chat, 2026-09-28) plus the two master resumes in `raw/`.

## Format (non-negotiable)

1. **Jake's Resume layout** (sb2nov/resume): centered name in small caps, one contact line,
   small-caps section headers with a full-width rule, bold headline left / dates right, italic role
   left / location right, tight bullets. Implemented in `resume/template.typ`. Do not restyle.
2. **Exactly one page**, filled to 97–100%. `resume/build.py` enforces this.
3. **Everything black.** No blue links, no gray text, no color. Links are underlined in black.
4. **Real, live hyperlinks**: email (mailto), LinkedIn, GitHub, arXiv paper, each OSS PR,
   each project repo, hackathon result pages where they exist. Verify each one with WebFetch
   before shipping; a dead link is worse than no link.
5. **A nicer header** than the Google Docs version: large small-caps name, a one-line
   contact strip (phone | email | linkedin | github | arXiv | location). No "followers" counts.
6. **Every experience entry has a `Stack:` line** listing the actual technologies used.

## Content

7. **Problem → action → quantified impact → stack.** Every bullet starts with a strong verb,
   names what was broken or needed, what she built, and a number. Example:
   "Cut distributed recovery time 99.7% (60 min → 10 s) across 100+ servers by replacing a
   synchronous RPC path with a push-based event queue sustaining up to 2B edges/s."
8. **Quantify everything.** If a bullet has no number, find one in the wiki. If none exists,
   cut the bullet or ask Azra. Never invent or round up a metric.
9. **Not AI-sloppy.** Banned: "leveraged", "spearheaded", "cutting-edge", "robust", "seamless",
   "passionate", "innovative", "utilized", "various", "state-of-the-art", "synergy", "dynamic",
   "fostered", "delve", "showcasing", "ensuring", trailing "-ing" impact clauses
   ("…, enabling X"), stacked adjectives, and bullets that list skills instead of results. Write
   the way an engineer describes their work to another engineer.
10. **Always include** (trim bullets, never whole categories):
    - Experience: Google (YouTube Ads infra), Columbia (paper), NASA (Horizons + swarm robotics),
      Rutgers Sensing & Reasoning Lab, Goldman Sachs, NSF/Princeton, WINLAB.
    - Research: first-author arXiv:2601.18710.
    - Open source: upstream PRs: merged statsmodels ×3, inspect_evals, TransformerLens, nnsight, moabb,
      braindecode; open Dynamo, FlashInfer, SkyPilot. **Never claim NVIDIA Warp was merged.**
    - Hackathon wins: YC RL hackathon #1 (Nomos), NASA/XFoundry Horizons #1 nationally, Verizon
      Smart Campus national winner (AeroBin), JacHacks defense track (BLACKSTART).
    - Projects: the Jane Street-style hardware / low-latency projects, the Mars rover,
      agentic reasoning layer, interp, evalkit, cross-sae, the `playground` research repo.
    - Technical skills.
11. **Tailor per posting**: reorder sections and pick bullets so the first third of the page
    answers the posting's top 3 requirements. Mirror the posting's own words for skills she
    really has. Never add a skill she does not have.
12. **Accuracy.** Titles, dates and employers must match the wiki exactly. If two sources
    disagree, use the one the wiki marks as canonical and mention the conflict to Azra.

## Tailoring by track

| track | lead with | then |
|---|---|---|
| Frontier AI research / research eng | Columbia paper, interp / cross-sae / evalkit, inspect_evals PR, YC Nomos (MARL), Sensing & Reasoning Lab | Google infra |
| Quant trading / quant dev | Google low-latency infra, Jane Street hardware projects, Goldman backtester, evalkit statistics, statsmodels PRs | Nomos, math major |
| Performance / ML systems / GPU | Google (C++, 2B edges/s), FlashInfer / Dynamo / SkyPilot PRs (open), SkyPilot, hardware projects | playground integer-C99 codegen |
| Hardware / ECE / FPGA | Jane Street hardware projects, Mars rover, NASA swarm, WINLAB edge platforms, playground MCU work | Google |
| SWE (product/infra) | Google, Goldman, WINLAB, AeroBin | OSS |

## Build

```
python career/resume/build.py career/applications/<slug>/resume.typ --png
```
Output must end with `ok`. Name the file `Azra_Bano_<Company>_<Role>.pdf`.
