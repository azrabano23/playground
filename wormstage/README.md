# wormstage

Compile the *C. elegans* nervous system at each stage of its development into a controller for a
snake robot, and ask whether the robot's behaviour develops the way the worm's does.

The worm is the only animal with whole-brain wiring measured repeatedly across its life:
Witvliet et al. 2021 reconstructed the nerve ring of eight individuals from birth (0 h) to
adulthood (45 h). wormstage turns each of those connectomes, plus Cook et al. 2019's adult whole
animal, into integer C that closes a locomotion loop through a robot's own joint encoders.

```
connectome(stage) ─► nerve ring: signed graded network ─► command: forward or reverse
                                                              │
stage motor circuit (L1: DB+DD+extrasynaptic | L2+: DB/VB+DD/VD) ◄┘
      bistable B/A neurons, excited by posterior/anterior stretch, no CPG
                                   │ joint targets (mrad)
      snake robot, compliant joints, resistive-force drag ◄──┘ joint angles (encoders)
```

## Findings

From [`results/ledger.jsonl`](results/ledger.jsonl), checked by
`loopgraph claims results/ledger.jsonl results/claims.json`. Full tables are in
[REPORT.md](results/REPORT.md).

1. **The robot crawls without a rhythm generator.** Undulation comes from proprioceptive feedback alone, through the robot's own body (after Boyle, Berri & Cohen 2012). Every controller that moved the robot was also run as emitted C and matched bit for bit.

2. **Gait adapts to the medium the way the worm's does.** Going from water-like to agar-like drag (K 1.5 → 40), the adult circuit slows from 2.63 Hz to 0.97 Hz, and its wave shortens from about 1.4 to 0.76 body lengths. Berri et al. 2009 and Fang-Yen et al. 2010 report the same direction for the worm. No parameter was tuned per medium, so this comes from the compliant body pushing back on the circuit. With stiff position servos it disappears, which is why the robot uses compliant joints.

3. **The newborn motor circuit needs extrasynaptic drive.** At hatching there are no ventral B neurons. Lu et al. 2022 proposed that ventral bends come from tonic extrasynaptic excitation. On the robot:
   - Removing that drive abolishes locomotion.
   - Restoring it gives a graded return of symmetry (0.55 → 0.64 → 0.81 → 0.91 at 25/50/75/100%).

4. **Avoidance wiring is specific from birth, before its best-known synapse exists.** At 0 h there is no ASH → AVA chemical synapse; the adult has 16. Stimulating ASH still drives the backward command interneurons harder than 1,000 degree-preserving shuffles of the same stage's wiring (p = 0.014). The robot driven by the newborn brain backs away. The bias holds in 7 of 9 datasets at p < 0.05.
   - Caveats: the p-values are uncorrected across stages, and they are conditional on treating glutamate as excitatory. That is true at ASH → AVA (GLR-1) but not everywhere. With the opposite assumption the effect reverses.

5. **Four servos are enough.** Agents searched robot designs under three gates: a coherent travelling wave, symmetry ≥ 0.7, and bit-exact C. A 4-servo body crawls at 0.23 body lengths/s, and a 7-servo body at 0.50, faster than the 11-servo default.

## What is data and what is model

| | source |
|---|---|
| nerve-ring wiring, 8 stages; adult whole animal | Witvliet 2021, Cook 2019, via a sha256-pinned ConnectomeToolbox wheel (MIT) |
| transmitter identity | WormAtlas table; AVA/AVB/AVD/AVE/RIB cholinergic per Pereira 2015 |
| motor circuit per stage | literature (Mulcahy 2022, Lu 2022), **not** a stage-specific EM matrix. The four L1 datasets share one body circuit, so their resting gaits are identical |
| A-type circuit with an anterior receptive field | assumed mirror of the B type |
| neuron dynamics, gains, time constants | model parameters, not measurements |
| robot | simulated; resistive-force theory, overdamped, planar |

## Use

```bash
pip install -e ../loopgraph -e ".[test]"
pytest                               # 31 tests, offline; the extract is committed
wormstage develop                    # 9 stages, rest and ASH
wormstage ablate                     # L1 extrasynaptic drive
wormstage medium                     # drag sweep
wormstage design --budget 24         # agents search for a smaller robot
wormstage emit --stage witvliet1 -o out/
python scripts/build_data.py         # rebuild the connectome extract from the pinned wheel
```

`emit` writes `worm.[ch]`: `worm_tick(state, phi_mrad, target_mrad)`, with state in a caller-owned struct and no malloc and no floats.
