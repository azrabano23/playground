# wormstage

The worm *C. elegans* is the only animal whose full brain wiring has been
mapped at several ages, from birth to adult. wormstage turns each of those
wiring maps into the controller for a snake robot, and asks: does the robot
"grow up" the way the worm does?

## Why it matters

Neuroscience has these maps but few ways to test what the wiring actually
*does* in a body. A robot is a cheap, repeatable body. Each age of the worm
becomes a small C program that runs on a microcontroller.

## What we found

In a simulated snake robot:

- **It crawls with no built-in rhythm.** The wave comes from the body's own
  feedback, as the worm is thought to do it.
- **It changes gait with the surface, like the worm.** Moving from water-like
  to gel-like drag, it slows from 2.63 to 0.97 beats per second. Nothing was
  tuned for this.
- **The newborn circuit needs an extra signal to crawl.** Take it away and
  the robot stops; add it back and crawling returns step by step. This tests
  a 2022 hypothesis about how newborn worms move.
- **The escape reflex is wired correctly from birth**, even before its best-
  known connection exists (p = 0.014 vs 1,000 shuffled wirings). This assumes
  a particular signal is excitatory; with the opposite assumption it flips.
- **Four motors are enough** to crawl.

## Try it

```bash
pip install -e ".[test]"
pytest
wormstage develop                   # every age, rest and escape
wormstage emit --stage witvliet1 -o out/
```

## Not done yet

- The brain wiring is real data (Witvliet 2021, Cook 2019). The body circuit
  per age comes from papers, not measured wiring, and neuron settings are
  model choices.
- The robot is simulated. No physical build yet.

Full tables: [results/REPORT.md](results/REPORT.md).
