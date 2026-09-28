# playground

Research projects that turn published scientific data into controllers small enough for
the cheapest chip in the robot, three hardware × quantization projects, and the harness that runs them.

| project | question | data | result so far |
|---|---|---|---|
| [pocketpolicy](pocketpolicy) | How much of a big robot policy survives compression into a microcontroller? | SO-101 arm URDF | 90.5% closed-loop success in 6.4 KB (teacher 98.5%); DAgger adds 13–31 points to small students |
| [wormstage](wormstage) | Does a robot driven by the worm's connectome develop the way the worm does? | *C. elegans* connectomes at 8 ages (Witvliet 2021) + adult (Cook 2019) | CPG-free crawling, worm-like gait change with the medium, and avoidance wiring specific from birth |
| [myoedge](myoedge) | Can a $5 chip decode EMG for a prosthetic hand that still works after the armband is taken off and put back on? | 21 subjects, electrode-shift dataset (Campbell 2024) | one 3-second fist restores post-shift accuracy from 52% to 90%, at 100 ms delay in 456 B of weights |
| [ticktotrade](ticktotrade) | How fast can an FPGA go from a NASDAQ ITCH tick to an OUCH order? | synthetic ITCH 5.0 over MoldUDP64 | 4-cycle (12.4 ns at an assumed 322 MHz) book-update-to-order in Verilog, bit-exact vs a Python golden model; 6.9k LUT on 7-series (yosys, no P&R) |
| [lowbit](lowbit) | How fast can a CPU multiply by 4-bit LLM weights without unpacking them? | W4A16, W4A8, MXFP4 at LLM decode/prefill shapes | cold-cache decode 5.3× numpy fp32 (W4A8 VNNI); 2.2–2.9× llama.cpp Q4_0 on its default CPU path; int32 accumulators bit-exact on scalar/AVX2/VNNI/AMX |
| [qfuzz](qfuzz) | Does ONNX Runtime compute quantized graphs the way the ONNX spec says? | 150k generated quantized graphs vs an exact reference | 4 real wrong-result bugs in ORT 1.30 (e.g. Q→DQ→Q→DQ fusion returns -6.504 where the spec gives -7.0), 55 minimized repros |
| [loopgraph](loopgraph) | the harness | | |

## How the work is run

Every experiment is a graph, every run lands in a ledger, and agents choose what to run next.

```
 planner agents ──proposals──► pipeline graph ──metrics──► gates ──► ledger.jsonl
 (pareto, random,              (content-addressed,          (bit-exact C,      │
  llm, committee)               cached per node)             budgets, floors)   │
        ▲                                                                       │
        └──────────── read every run, its verdicts and who proposed it ─────────┘
```

- **Graphs, not notebooks.** Each pipeline stage is a pure function, cached by the hash of its code and inputs. Changing one knob re-runs only what is downstream of it.
- **Agents decide, gates judge.** A Pareto-frontier walker, a random explorer and an optional language-model planner all share one interface. None of them can override a gate, and the ledger records which agent proposed each run and why.
- **Numbers are checked.** Every figure in a README is a claim bound to a ledger entry. CI runs `loopgraph claims` and fails if a documented number drifts from what was measured.
- **The deployed code is the tested code.** All three projects emit integer-only C99 (no malloc, no floats in the hot path), compile it with `-Werror`, run it, and compare every output byte against the reference implementation.

## Honesty

Each project README has a "what is real and what is not" section:

- Nothing here has run on physical hardware yet.
- Microcontroller timings are derived from operation counts, not measured.
- The robot policy teacher is a scripted expert standing in for a foundation model.
- The worm's body circuit per stage comes from the literature, not from a per-stage EM matrix.

## Run

```bash
pip install -e ./loopgraph[test] -e ./pocketpolicy[test] -e ./wormstage[test] -e ./myoedge[test]
(cd myoedge && myoedge fetch)       # EMG data, cloned at pinned commits
for p in loopgraph pocketpolicy wormstage myoedge; do (cd $p && pytest -q); done
```
