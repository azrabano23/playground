# myoedge

Low-cost prosthetic hands read muscle signals from an armband. Every time the
user puts the armband back on, it sits slightly differently, and the hand
stops understanding them. myoedge fixes most of that with one three-second
fist, on a chip that costs a few dollars.

## Why it matters

A commercial bionic hand costs tens of thousands of dollars. 3D-printed hands
like HACKberry cost a few hundred, but this re-wearing problem makes them
frustrating in daily use. Fixing it cheaply makes the cheap hand usable.

## What we found

On recorded data from 21 people, training before the armband moved and
testing after:

| | gesture accuracy |
|---|---|
| same session, nothing moved | 95% |
| after re-wearing, standard method | **52%** |
| after re-wearing + one 3-second fist | **90%** |

- The fist fix helps 20 of 21 people.
- The decoder answers in 100 ms and fits in **456 bytes**, small enough for
  the 8-bit chip already on the hand's board.
- The generated C code matches the Python version on every decision.

## Try it

```bash
pip install -e ".[test]"
myoedge fetch        # downloads the public dataset
pytest
myoedge compare      # the table above
myoedge emit --subject 0 --aug 0.5 --vote 1 -o out/
```

## Not done yet

- The data is from people without limb loss wearing a Myo armband. Real
  users and the hand's own sensors will differ.
- Nothing has run on the chip or a hand yet; memory and delay are computed,
  not measured.

Data: Campbell et al., *J NeuroEng Rehabil* 2024. Full tables:
[results/REPORT.md](results/REPORT.md).
