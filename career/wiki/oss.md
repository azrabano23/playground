# Open-source contributions

Verified 2026-09-28 against the GitHub API (author search for azrabano23, 74 PRs).
Older resumes said "45 upstream PRs, 9 merged" and "NVIDIA Warp #1911 landed on main". **The Warp
claim is false: #1911 was closed without merging. Never use it.** Merged count verified below: **8**.

### Merged (safe to say "merged")
| project | PR | title | merged |
|---|---|---|---|
| statsmodels | [#10230](https://github.com/statsmodels/statsmodels/pull/10230) | Use final seasonal factor in Holt-Winters forecasts | 2026-09-06 |
| statsmodels | [#10231](https://github.com/statsmodels/statsmodels/pull/10231) | Print seasonal MA order as an integer in SARIMAX summary | 2026-09-04 |
| statsmodels | [#10232](https://github.com/statsmodels/statsmodels/pull/10232) | Fix out-of-bounds write and dropped observations in fast_linbin | 2026-09-06 |
| UK AISI inspect_evals | [#1765](https://github.com/UKGovernmentBEIS/inspect_evals/pull/1765) | Register MedCalc-Bench eval (tamper-safe scoring) | 2026-06-10 |
| TransformerLens | [#1369](https://github.com/TransformerLensOrg/TransformerLens/pull/1369) | Add Direct Logit Attribution tool | 2026-06-08 |
| nnsight | [#671](https://github.com/ndif-team/nnsight/pull/671) | (verify title) | 2026-07-25 |
| moabb | [#1140](https://github.com/NeuroTechX/moabb/pull/1140) | Nadeau & Bengio corrected resampled t-test | 2026-08-24 |
| braindecode | [#1128](https://github.com/braindecode/braindecode/pull/1128) | (verify title) | 2026-08-25 |

### Open (say "PR" or "open PR", never "merged")
| project | PR | title |
|---|---|---|
| NVIDIA Dynamo | [#13326](https://github.com/ai-dynamo/dynamo/pull/13326) | parse DYN_LOG filter directives when deriving engine log level |
| FlashInfer | [#4548](https://github.com/flashinfer-ai/flashinfer/pull/4548) | enumerate artifact downloads from checksums.txt so cute-dsl kernels are pre-fetched |
| SkyPilot | [#10484](https://github.com/skypilot-org/skypilot/pull/10484) | fix endpoint lookup when ingress-nginx is in a custom namespace |
| SkyPilot | [#10659](https://github.com/skypilot-org/skypilot/pull/10659) | scope enabled-clouds cache per user for Slurm |
| lifelines | [#1696](https://github.com/CamDavidsonPilon/lifelines/pull/1696) | return RMST Greenwood sampling variance |
| NVIDIA Warp | #1929, #1915, #1831 | open; #1911, #1914, #1810, #1833 were closed unmerged |

### Issues / other
- NVIDIA garak issue [#2155](https://github.com/NVIDIA/garak/issues/2155): shared mutable state leaking between test attempts.
- Stanford HELM scoring defect zeroing 35% of a test set: find the link before using it.
- Closed unmerged: QuantLib #2780, medplum #10293, openai-agents-python #4459.

The org slugs for TransformerLens, nnsight and braindecode are best guesses. WebFetch the link before putting it on a resume.

**Resume rule:** say "merged" only for rows marked merged. Otherwise say "PR" or "patch".
Before a resume ships, the agent opens each linked PR with WebFetch and updates the status
column here.

Resume one-liner:
> **Open source**: 8 merged upstream PRs: statsmodels ×3, UK AISI inspect_evals, TransformerLens,
> nnsight, moabb, braindecode. Open PRs: NVIDIA Dynamo, FlashInfer, SkyPilot. Every fix starts
> from a reproducing case.
