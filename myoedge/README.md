# myoedge

EMG gesture control for low-cost prosthetic hands that keeps working after the armband is taken off
and put back on, compiled to integer C for the 8-bit microcontroller already on the hand's board.

A commercial myoelectric hand costs tens of thousands of dollars. Open 3D-printed hands such as
HACKberry cost a few hundred, but their pattern-recognition control has a known failure: every
time the user dons the socket, the electrodes land a little differently, and a classifier trained
yesterday stops working today. myoedge measures that failure on real data and fixes most of it
with one three-second fist, in under a kilobyte.

## Results

Measured on 21 subjects from the CIIL ElectrodeShift dataset (Campbell et al., *J NeuroEng
Rehabil* 2024; Myo armband, 8 channels, 200 Hz). Every classifier was trained before the armband
was displaced and tested after. All numbers are from
[`results/ledger.jsonl`](results/ledger.jsonl), checked by
`loopgraph claims results/ledger.jsonl results/claims.json`, and go through the int8 decoder
that runs on the device. The full tables are in [REPORT.md](results/REPORT.md).

| | mean accuracy | 10th-percentile subject |
|---|---|---|
| no shift (same session) | 0.950 | |
| after shift, standard LDA | **0.524** | 0.367 |
| + rotation augmentation (no user action) | 0.809 | |
| + one-fist recalibration | 0.897 | |
| agent-found design: aug 0.5 ch + recalibration, 200 ms window, no vote | **0.904** | 0.722 |

- **Shift costs almost half the accuracy.** Chance is 0.2.
- **One held fist recovers almost all of it.** It helps 20 of 21 subjects, with a median gain of 36 points.
- **The best design is fast.** Its 100 ms decision delay is inside the optimal 100–125 ms range reported by Farrell & Weir 2007, far under the 300 ms usually cited as acceptable.
- **It fits an ATmega32U4:** 456 bytes of weights and 531 bytes of RAM.
- **What the planners found:** a committee of planning agents searched window, vote, classifier, augmentation and recalibration over 24 designs, optimising the 10th-percentile subject (the user served worst) against delay. Gates: under 300 ms delay, fits the ATmega32U4, bit-exact C. The agents found that a small MLP gains nothing over LDA here, and that majority voting buys a little worst-case accuracy at a large delay cost.

### How recalibration works

The Myo is a ring, so a donning error is mostly a rotation around the forearm.

- **At training time:** the per-channel activity of the user's fist is stored as eight numbers.
- **After donning:** the user holds a fist for three seconds, and the device accumulates the same eight numbers.
- **The search:** it tries fractional rotations in quarter-channel steps and keeps the one whose pattern best matches the stored fist.
- **On the chip:** the search compares normalised correlations by cross-multiplication, with no square roots or division. It needs eight counters of RAM and no sample buffer.

The result is a quarter-channel rotation applied to every incoming sample. The C implementation is checked bit for bit against the reference.

## What is real and what is not

- **Real:**
  - The EMG is recorded data from 21 people, cloned at a pinned commit.
  - The accuracy numbers come from the integer decoder.
  - The emitted C (feature extraction, classifier, vote, servo drive and calibration) matches the numpy reference on every decision.
- **Not measured:**
  - Delay is derived: half a window plus half the vote span, excluding compute.
  - Memory figures count the emitted arrays and buffers; they come from no AVR toolchain.
  - Nothing has run on an ATmega or a hand.
- **Limits:**
  - The dataset is able-bodied subjects wearing a Myo. Residual-limb EMG and a HACKberry's own sensor front end will differ.
  - The five classes map to open, close and hold on a three-servo hand; the wrist classes hold, because HACKberry has no wrist actuator.
  - The upstream data repositories carry no license file, so the data is fetched, not redistributed.

## Use

```bash
pip install -e ../loopgraph -e ".[test]"
myoedge fetch               # clone LibEMG data at pinned commits
pytest                      # 16 tests; real-data tests skip without the fetch
myoedge compare             # the table above
myoedge within              # the no-shift ceiling
myoedge campaign --budget 24
myoedge emit --subject 0 --aug 0.5 --vote 1 -o out/
```

`emit` writes `myo.[ch]`, `myo_net.[ch]` and `calibration_ref.h`. `firmware/hand.c` runs the decoder at 200 Hz, drives three servos, and recalibrates when a button is held during a fist.
