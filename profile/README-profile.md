parkinsons law maximizer

逆水行舟，不進則退

---

### Upstream

44 pull requests across 25 projects — [full list with state](CONTRIBUTIONS.md).

- [NVIDIA/warp](https://github.com/NVIDIA/warp) (7)
- [stanford-crfm/helm](https://github.com/stanford-crfm/helm) (4)
- [ArduPilot/pymavlink](https://github.com/ArduPilot/pymavlink) (3)
- [NVIDIA-NeMo/Skills](https://github.com/NVIDIA-NeMo/Skills) (3)
- [skypilot-org/skypilot](https://github.com/skypilot-org/skypilot) (3)
- [statsmodels/statsmodels](https://github.com/statsmodels/statsmodels) (3)
- [ai-dynamo/dynamo](https://github.com/ai-dynamo/dynamo) (2)
- [NeuroTechX/moabb](https://github.com/NeuroTechX/moabb) (2)
- [anthropics/anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python)
- [braindecode/braindecode](https://github.com/braindecode/braindecode)
- [CamDavidsonPilon/lifelines](https://github.com/CamDavidsonPilon/lifelines)
- [decoderesearch/SAELens](https://github.com/decoderesearch/SAELens)
- [flashinfer-ai/flashinfer](https://github.com/flashinfer-ai/flashinfer)
- [lballabio/QuantLib](https://github.com/lballabio/QuantLib)
- [medplum/medplum](https://github.com/medplum/medplum)
- [ndif-team/nnsight](https://github.com/ndif-team/nnsight)
- [NVIDIA/garak](https://github.com/NVIDIA/garak)
- [openai/openai-agents-python](https://github.com/openai/openai-agents-python)
- [Project-MONAI/MONAI](https://github.com/Project-MONAI/MONAI)
- [stanfordnlp/pyvene](https://github.com/stanfordnlp/pyvene)
- [sunlabuiuc/PyHealth](https://github.com/sunlabuiuc/PyHealth)
- [teslamotors/vehicle-command](https://github.com/teslamotors/vehicle-command)
- [TorchIO-project/torchio](https://github.com/TorchIO-project/torchio)
- [TransformerLensOrg/TransformerLens](https://github.com/TransformerLensOrg/TransformerLens)
- [UKGovernmentBEIS/inspect_evals](https://github.com/UKGovernmentBEIS/inspect_evals)

My forks of these projects are not bookmarks: each holds the patch branch for its pull request, rebased on upstream HEAD.

### Own work

[loopgraph](https://github.com/azrabano23/loopgraph) is an experiment harness: a content-addressed DAG, an append-only run ledger, an int8 quantizer that emits C99, and a gate that compiles the emitted C with `-Werror` and checks it is bit-exact against the numpy reference.

[myoedge](https://github.com/azrabano23/myoedge) (EMG prosthetic control after electrode shift), [wormstage](https://github.com/azrabano23/wormstage) (C. elegans connectome locomotion) and [pocketpolicy](https://github.com/azrabano23/pocketpolicy) (SO-101 arm distillation) run on it. In each, CI runs `loopgraph claims results/ledger.jsonl results/claims.json`, so every number in the README is checked against a recorded run and the build fails if one drifts.
