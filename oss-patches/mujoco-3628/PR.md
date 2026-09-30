# PR drafts for google-deepmind/mujoco#3628

Post `issue-comment.md` first and wait for a maintainer reply. The PR text below assumes the maintainers accept the three-way split proposed there. If they ask for a single PR, merge the three descriptions.

Patch series, based on `main` at 0fd2088:

| file | commit | scope |
|---|---|---|
| `0001-Bracket-the-linesearch-at-constraint-zone-boundaries.patch` | PR 1, fixes #3628 | `engine_solver.c` (+103/−7), test, changelog |
| `0002-Floor-the-linesearch-gradient-tolerance-at-the-deriv.patch` | PR 2, stacked on 1 | `engine_solver.c` (+29/−5), test, changelog |
| `0003-Warn-when-a-linesearch-uses-all-ls_iterations.patch` | PR 3, stacked on 1+2, API change | new `mjWARN_LINESEARCH`, bindings, test, changelog |
| `mujoco-3628-combined.patch` | all three as one diff | |

Apply with `git am 000*.patch`. Each commit builds on its own, and its solver tests pass in double and `mjUSESINGLE` (`bench/results/solver_tests_per_commit.txt`). Before pushing, sign the Google CLA at https://cla.developers.google.com/ with the same email as the commit author.

---

## PR 1: Bracket the linesearch at constraint zone boundaries

Fixes #3628.

### Problem

With elliptic cones, `impratio=10` and `ls_iterations=20`, the Newton solver can stop at a qacc that is not the minimizer, and it does so without any signal. Restarting from that qacc takes 0 iterations, so it is a false fixed point. The issue's state gives:

- main: `niter 2`, final gradient 124, `neval [7, 20]`, max |qacc − qacc(ls 200)| = 59.2.

### Cause

The linesearch cost f(α) is convex and C¹, but its curvature jumps wherever a constraint changes zone. For an elliptic contact this happens at N = μT (top/middle) and at μN = −T (middle/bottom, i.e. stick/slip).

In the bracketed phase, `PrimalSearch` evaluates the midpoint plus one Newton candidate from each bracket end. Each Newton candidate uses the curvature on its own side of the jump, so it overshoots across it:

- In the issue's second line search, f'' is about 6e5 below α = 0.0207, 3.4e8 on the bottom-zone piece [0.0207, 0.0309] that holds the minimizer, and 1.1e8 above it.
- Both Newton candidates land near the opposite bracket end and improve it by only ~1e-9 (trace in `bench/results/ls_trace_base.txt`).
- The search therefore becomes bisection at 3 evaluations per halving, and needs 23 evaluations.

The following line search fails the same way with no improvement, so it returns α = 0, which `mj_solPrimal` reads as convergence.

### Change

- In the bracketed phase, when the bracket contains a zone boundary, evaluate the boundary closest to the bracket midpoint instead of the midpoint. `PrimalKink` computes the boundaries in closed form for each constraint:
  - the zero crossing of inequality rows
  - the ±Rf bounds of friction-loss rows
  - for elliptic cones, the roots of (V0² − μ²VV)α² + 2(U0V0 − μ²UV)α + (U0² − μ²UU) = 0 with N ≥ 0, and of (μ²V0² − VV)α² + 2(μ²U0V0 − UV)α + (μ²U0² − UU) = 0 with N ≤ 0. These use the `quad[3..7]` values already stored by `PrimalPrepare`, and the roots are computed with the numerically stable quadratic formula.

  Once both bracket ends sit on the boundaries of the piece that contains the root, the Newton candidates use the correct curvature. Inside that piece Newton is exact for quadratic pieces and converges quadratically in the elliptic middle zone. Rounding in the boundary computation only affects efficiency: any point strictly inside the bracket is a valid candidate, and the bracket invariant is kept by evaluating it.
- Do not evaluate a Newton candidate that falls outside the current bracket. f' is monotone, so such a point cannot improve on a bracket end, and it cannot pass the convergence test.

### Results

Benchmark: 40,000 contact solves of the issue's box (`bench/bench40k.c`), with elliptic cones, impratio 10 and ls 20, each compared against ls 200 from the same state. Numbers are main → patched.

| metric | double | single |
|---|---|---|
| solves with \|Δqacc\| > 1 | 478 → 0 | 20 → 0 |
| false fixed points | 590 → 0 | 20 → 0 |
| mean evaluations per line search | 6.15 → 5.29 | 11.67 → 10.26 |

In single precision the remaining exhaustion is noise-chasing, which PR 2 addresses. The issue's state now takes `neval [7, 10, 2]` for every ls ≥ 20.

What does not change:
- Pyramidal cones: identical statistics.
- Default settings (elliptic, impratio 1): mean evaluations 4.18 → 4.17, max 20 → 14.
- Step time on `humanoid`, `22_humanoids` and `boxpile`: within the noise of a shared VM (±5%). Evaluations per line search are equal or lower. See `bench/results/stepbench_summary.txt`.

### Tests

- New `SolverTest.EllipticLineSearchCrossesConeBoundary`: the issue's state with ls 20 must match ls 200 (tolerance 1e-6 in double, 1e-1 in float), and every line search must use fewer than 20 evaluations. It fails on main in both precisions: in double qacc is off by up to 59 and neval hits 20; in single neval reaches 22. It passes after the change in both precisions.
- `ctest --test-dir build/test/engine` passes in double and `mjUSESINGLE`, except 3 plugin-registration tests that fail identically on unpatched main in my partial build.

### Trade-offs

- `PrimalKink` is O(nefc) and runs only in the bracketed phase. It is cheaper than a `PrimalEval` (no matrix products).
- Worst case, many clustered boundaries away from the root, is one evaluation per boundary rather than per halving. On the benchmarks the max evaluations went down in every configuration (e.g. 22_humanoids elliptic 29 → 23). If you prefer a guaranteed bisection rate, I can snap only to boundaries inside the middle half of the bracket.

---

## PR 2: Floor the linesearch gradient tolerance at the derivative's rounding noise

Stacked on PR 1.

### Problem

The linesearch accepts a point when |f'(α)| < gtol, with gtol = tolerance·ls_tolerance·‖d‖/scale. f' is a sum of terms that are much larger than f' itself. When gtol is below the rounding error of that sum, the sign of f' near the root is noise, and the search runs until `ls_iterations` is spent. This happens in two cases:

- `tolerance=0`: on main, 89% of Newton line searches on the test humanoid use all 50 evaluations, with a mean of 45.3 evaluations.
- `mjUSESINGLE` with the default tolerance: on main, 14,201 of 116,829 line searches on the box benchmark exhaust ls 50.

### Change

`PrimalPrepare` accumulates the magnitudes of the terms of f':

- `LSnoise[0] = |v·Ma| + |v·qfrc_smooth| + Σ|quad[1]|`
- `LSnoise[1] = 2·(quadGauss[2] + Σ quad[2])`

The tolerance used at α becomes max(gtol, ε·(LSnoise[0] + |α|·LSnoise[1])), where ε is `DBL_EPSILON` or `FLT_EPSILON`. With the default tolerance in double, the floor never activates: trajectories are bitwise identical with and without it.

### Results (main → patched)

| case | mean evaluations | line searches using all evaluations |
|---|---|---|
| humanoid, Newton, tolerance 0, double | 45.3 → 2.0 | 17,109 → 0 |
| same, CG | 45.4 → 2.3 | 17,556 → 0 |
| box, single, elliptic, impratio 1, ls 50 | 14.38 → 3.60 | 14,201 → 0 |
| box, single, elliptic, impratio 10, ls 20 (vs PR 1 alone) | 10.26 → 4.40 | 18,020 → 131 |

In single precision, deviations from the ls 200 reference stay at float noise (max 6.7e-4 on qacc of O(1e3)). Full tables are in `bench/results/lscount.txt` and `bench/results/bench40k.txt`.

### Tests

- New `SolverTest.LineSearchStopsAtRoundingNoise`: the test humanoid with Newton and `tolerance=0`, for both cones, over 50 steps; no line search may reach `ls_iterations`. It fails on main (thousands of exhausted line searches in both precisions) and passes after the change.
- The existing `NewtonDecrementTermination` and `ZeroToleranceDisablesTermination` tests, which use `tolerance=0` references, still pass.

### Trade-off

With `tolerance=0`, a line search now stops once |f'| reaches noise level instead of running until the bracket cannot shrink. The outer loop still runs until no improvement is possible, so "tolerance 0 disables early termination" still holds for the solver iterations.

---

## PR 3: Warn when a linesearch uses all ls_iterations

Stacked on PRs 1 and 2. **API change**, so it needs the maintainers' decision.

### Change

- New `mjWARN_LINESEARCH` in `mjtWarning` (`mjNWARNING` 7 → 8). Updated alongside it:
  - `references.h`
  - the Python introspection enums
  - the generated WASM bindings
  - the Unity bindings (enum plus the `warning7` field)
  - the warning text: "Linesearch used all N ls_iterations, the constraint solution may be inaccurate. Increase ls_iterations."; `info` is `ls_iterations`.
- After the constraint solve, `fwdConstraint` scans the recorded per-island `mjSolverStat` entries and warns once if any `neval >= ls_iterations`. This check runs in the serial part because islands can be solved in parallel through `mju_dispatch`, and calling `mj_warning` from inside a solve would race.
- A line search that runs out of evaluations without improvement is the only case that ends the solve silently. It is now saved as an iteration with `improvement = 0` and its `neval`. Before, `mj_solPrimal` broke out of the loop before `saveStats`, so the failure was invisible in `mjData.solver`.

### Semantics

- "Used all" means neval ≥ ls_iterations. It also fires for a line search that converged exactly on its last allowed evaluation; in that case raising the budget is still the right advice.
- This PR should land after PR 2. Without the floor, `tolerance=0` or single-precision runs would trigger the warning constantly.
- With PRs 1 and 2 applied, the warning never fires in the box benchmark at ls 50, nor on humanoid, 22_humanoids or boxpile at default settings. At impratio 10 with ls 20 it fires on 334 of 129,905 line searches (double). In all of those cases the line search still returned an improvement.

### Tests

- New `SolverTest.LineSearchExhaustedWarning`: the issue's state with ls 5 must record a final iteration with improvement 0 and neval ≥ 5, and raise the warning exactly once with `lastinfo == 5`. With ls 50 there is no warning. It uses `mock_warning_handler.ExpectWarnings`.
- The whole engine suite passes in both precisions. The fixture fails any test that emits an unexpected warning, so this also shows the warning does not fire in any existing engine test.

### Not run

Python `bindings_test.py` (it checks `len(warnings) == mjNWARNING`, which is derived automatically), WASM tests, and the Unity build.

---

## Reproducing the evidence

All paths are relative to `bench/`.

```sh
# build (both precisions)
cmake -S mujoco -B build -DCMAKE_BUILD_TYPE=Release -DMUJOCO_BUILD_TESTS=ON \
      -DMUJOCO_BUILD_SIMULATE=OFF -DMUJOCO_BUILD_EXAMPLES=OFF -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=OFF
cmake -S mujoco -B build-single ... -DCMAKE_C_FLAGS=-DmjUSESINGLE -DCMAKE_CXX_FLAGS=-DmjUSESINGLE
cmake --build build --target mujoco engine_solver_test
(cd build && ctest -R '^SolverTest')

# benchmarks (compile against each libmujoco; add -DmjUSESINGLE for single builds)
cc -O2 repro.c    -I mujoco/include -L build/lib -lmujoco -lm -o repro       # the issue's script, in C
cc -O2 bench40k.c -I mujoco/include -L build/lib -lmujoco -lm -o bench40k    # 40k-solve protocol
./bench40k elliptic 10 20 40000
cc -O2 stepbench.c ... ; ./run_stepbench.sh <dir with stepbench_{base,fix}-{double,single}> mujoco 15
python3 summarize_stepbench.py results/stepbench_raw.txt
cc -O2 lscount.c ... ; ./lscount mujoco/test/engine/testdata/solver/humanoid.xml 0 1 2
```

Note: IPO/LTO is disabled because GCC LTO objects did not link with `lld` on this machine. Build and link the base and patched libraries against the headers of their own revision, since PR 3 changes the size of `mjData`.
