# Projects: canonical bullet bank

Grouped by the track they sell best to. The one-line resume form goes first, then the facts
behind it. Links must resolve before shipping.

## Hardware / low-latency / embedded (this repo, `playground`)

Azra calls these "the hardware projects we made". All three emit integer-only C99 (no malloc, no
floats in the hot path), compile with `-Werror`, and are checked byte-for-byte against a NumPy
reference. Every README number is bound to a ledger entry that CI verifies. **Honesty boundary:
nothing has run on physical hardware yet, and MCU timings come from operation counts.** [R6]

- **pocketpolicy**: <https://github.com/azrabano23/playground/tree/main/pocketpolicy>.
  Distilled a robot pick-and-place policy (teacher 98.5%) into an int8 MLP for the SO-101 arm's
  microcontroller: **90.5% closed-loop success in 6.4 KB flash / 141 B RAM**, 97% at 144 KB; DAgger
  adds **13–31 points** over behavior cloning (3 seeds). *Python, int8 quantization, C99.*
- **myoedge**: <https://github.com/azrabano23/playground/tree/main/myoedge>.
  On-device EMG gesture decoding for low-cost prosthetic hands. On 21 subjects (Campbell 2024), a
  3-second fist recalibration restores post-shift accuracy from **52.4% to 90.4%**, at 100 ms delay,
  in **456 B of weights / 531 B RAM** (8-bit ATmega32U4). *Python, LDA, int8, C.*
- **wormstage**: <https://github.com/azrabano23/playground/tree/main/wormstage>.
  Compiled *C. elegans* connectomes at 8 developmental stages into a snake-robot controller. It crawls
  with no central pattern generator, gait frequency drops **2.63 → 0.97 Hz** from water-like to
  agar-like drag, and avoidance wiring is stage-specific from birth (**p = 0.014** vs 1,000 shuffles).
  *Python, graph dynamics, C99.*
- **loopgraph**: <https://github.com/azrabano23/playground/tree/main/loopgraph>.
  Research harness: content-addressed pipeline graph, append-only run ledger, planner agents
  (Pareto, random, LLM, committee) that cannot override gates; CI fails if any documented number
  drifts from the ledger. *Python, CI.*

Resume one-liner (hardware / quant track):
> **Integer-C inference for microcontrollers** (pocketpolicy, myoedge, wormstage): three models
> compiled to malloc-free, float-free C99 and verified bit-exact against NumPy. Robot policy at 90.5%
> success in 6.4 KB; EMG decoder that restores accuracy 52% → 90% in 456 B of weights.

### Proposed: an actual FPGA / trading-hardware project (not built)
If Azra wants a Jane Street / HRT / Optiver-style hardware project: an ITCH 5.0 feed handler plus
top-of-book order book in SystemVerilog or Hardcaml on the Xilinx/AMD board she has, with
cycle-accurate tick-to-trade latency measured in simulation (Verilator) and on board. **Do not list
it until it exists.**

## Frontier AI / interpretability / evals

- **Nomos (#1 ML Research, YC RL Hackathon)**: co-built with 1 other engineer. Decentralized
  shared-parameter MAPPO (CTDE, Deep Sets) trained in parallel JAX worlds coordinates a **172-agent**
  driverless fleet on the real San Francisco OSM road graph; dual-Lagrangian constrained PPO plus a
  higher-order control-barrier-function QP safety filter reach **98.7% collision-free** operation.
  *JAX, MAPPO, CBF-QP.* [R1, R3]
- **interp**: <https://github.com/azrabano23/interp>. Mechanistic-interpretability toolkit (logit
  lens, direct logit attribution, SAE features, steering) shipped as a CLI plus coding-agent skill;
  independently reproduces **2 published GPT-2 circuits** (IOI name movers, induction heads) at
  causal-patching recovery **≈ 1.0**. *PyTorch, TransformerLens.* [R1, R3]
- **evalkit**: <https://github.com/azrabano23/evalkit>. LLM-eval statistics on a pure-NumPy core:
  calibrated bootstrap CIs (**90% nominal → 91% empirical** coverage), unbiased pass@k that matches
  the analytic estimator exactly, exact McNemar tests, a position-bias check that recovers an
  injected biased judge at rate **1.00**, and 13-gram contamination detection. *NumPy.* [R3]
- **cross-sae**: FDR-controlled (Model-X knockoff) SAE feature matching between vision transformers
  and human visual cortex (EEG). Reported the null result (0 matches, permutation p = 1.0) and
  diagnosed it with RSA: raw ViT↔EEG do align (**ρ = 0.155, p = 0.0005**), and the attenuation is a
  capacity effect, not a sparsity effect. *PyTorch, SAEs, RSA.* [R1]
- **MedCalc-Bench × UK AISI Inspect**: ported MedCalc-Bench (NeurIPS 2024) to Inspect with
  tamper-safe scoring (removed `eval()` of model output); merged upstream as inspect_evals **PR
  #1765**. [R1]
- **neuroloop**: typed dataflow framework for closed-loop neuromodulation that rejects a pipeline at
  graph-build time if declared worst-case execution times exceed the latency budget or the
  stimulation-safety envelope is infeasible. *Python.* [R1]
- **Agentic reasoning layer**: **unverified** (see profile Open question 4).

## Systems / product

- **AeroBin (Verizon Smart Campus National Winner)**: React 19 + TypeScript ops dashboard over a
  live sensor fleet, with fill prediction and capacitated routing; wasteful pickups **87% → 0.5%**
  across **3 multi-city / campus pilots**. <https://github.com/azrabano23/AeroBin> [R3]
- **BLACKSTART (JacHacks defense track winner)**: graph-native microgrid simulator; a controlled A/B
  traced two null results to real defects, including a single-point-of-failure bus stranding
  **3,000 kW**. <https://github.com/azrabano23/BlackStart> [R3]
- **Thaakat (YC × Medplum)**: primary author, 44 of 69 commits. [R3]
- **bmwise**: price forecasting (linear, ARIMA, LSTM) plus mean-variance efficient-frontier portfolio
  optimization. <https://github.com/azrabano23/bmwise> [R3]
- **GPU / inference tooling**: `llm-roofline` (74 tests), `disagg-sim` (27 tests), `warpfield`
  (NVIDIA Warp, 10 tests). [R7] Check each repo's README before using a number.

## Mars rover: NASA L'SPACE Mission Concept Academy
Team 13, "R(Over) the Moon": Mars rover mission concept taken through MCR, SRR and PDR reviews under
a **200 kg mass cap and a $450M cost cap**. [R9] Ask Azra for her subsystem and role before
writing the bullet.
