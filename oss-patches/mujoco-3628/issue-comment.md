Thanks for the detailed report and the minimal repro. I reproduced it on current `main` (0fd2088, 3.14.1 dev, Linux x86-64, float64): `ls_iterations=20` gives `niter 2`, final gradient 124, `neval [7, 20]`, and 59.2 max |qacc - qacc(ls 200)|. Restarting from that qacc gives `niter 0`. I traced the line search and have a prototype fix. Before opening anything, I'd like to check whether you want it and how you'd like it split.

**Root cause.** The line-search cost f(α) is convex and C¹. Its second derivative jumps wherever a constraint changes zone. For an elliptic cone that happens at the top/middle boundary (N = μT) and at the middle/bottom (stick/slip) boundary (μN = −T). In the issue's second line search there is a single contact, and f'' goes from about 6e5 below α ≈ 0.0207, to 3.4e8 on the bottom-zone piece [0.0207, 0.0309], to 1.1e8 above it. The minimizer, α = 0.0224, sits on that narrow piece.

The bracketed phase of `PrimalSearch` makes one midpoint evaluation plus one Newton candidate from each bracket end. Each Newton step uses the curvature on its own side of the jump, so both steps overshoot across the jump:

- from α ≈ 1 the step lands at 0.0047
- from 0.0047 it lands at ≈ 0.9987

Each candidate improves its bracket end by only about 1e-9. So the search becomes bisection at 3 evaluations per halving, and it needs 23 evaluations. The next line search is similar (the minimizer is inside [0.00046, 0.011] and the first bracket is [−0.016, 1.0]). Every point it evaluates has cost ≥ 0, so it returns α = 0 (`LSresult` 5). `mj_solPrimal` then treats "no improvement" as convergence. Restarting from that qacc repeats the same failed line search, which is why it is a fixed point.

This also answers your second question: yes, the budget goes on crossing cone boundaries. Here the curvature ratio across the boundary is several hundred, not just impratio.

**Prototype.** Three commits, each with a test that fails before and passes after, in both double and `mjUSESINGLE`:

1. **Zone-boundary bracketing.** In the bracketed phase, evaluate the zone boundary ("kink") closest to the bracket midpoint instead of the midpoint itself, when the bracket contains one. The boundaries have closed forms per constraint:
   - inequality zero crossing
   - friction-loss ±Rf
   - the roots of the two elliptic-cone boundary quadratics, filtered by the sign of N

   The commit also stops evaluating Newton candidates that fall outside the bracket. Because f' is monotone, such a point can never replace a bracket end. There is no API change (+103/−7 in `engine_solver.c`, plus a test).
2. **Tolerance floor.** Floor the line-search gradient tolerance at the rounding noise of f', computed as eps·Σ|terms|. In double with the default tolerance it never activates (trajectories are bitwise identical). It matters for `tolerance=0`, where most line searches currently exhaust `ls_iterations`, and for single precision.
3. **Warning.** Add `mjWARN_LINESEARCH`, raised after the solve when a line search used all `ls_iterations`. A line search that ends the solve without improvement is recorded as an iteration with improvement 0 in `mjData.solver`, so the failure shows up in the statistics. The check reads the per-island stats in the serial part of `fwdConstraint`, because islands can be solved in parallel. This is an API change: a new enum value and `mjNWARNING` 7→8.

**Numbers.** The benchmark is 40,000 contact solves of your free box with random drops and velocity kicks. Each solve is compared against `ls_iterations=200` from the same state.

| elliptic, impratio 10, ls 20 | main (f64) | patched (f64) | main (f32) | patched (f32) |
|---|---|---|---|---|
| solves with \|Δqacc\| > 1 | 478 (max 708) | 0 (max 2.4e-7) | 20 (max 148) | 0 (max 6.7e-4) |
| false fixed points (restart → 0 iterations) | 590 | 0 | 20 | 0 |
| mean / max evaluations per line search | 6.15 / 22 | 5.29 / 22 | 11.67 / 22 | 4.40 / 22 |
| line searches that used the whole budget | 5208 | 334 (none ended the solve) | 29498 | 131 |

Your exact state now takes `neval [7, 10, 2]` for every `ls_iterations ≥ 20`.

Nothing else changed where it shouldn't:
- Pyramidal cones in double give identical statistics.
- With default settings in double, the mean evaluations are unchanged. The max drops (20→14 for elliptic, impratio 1).
- On `humanoid`, `22_humanoids` and `boxpile` (pyramidal and elliptic, impratio 1 and 10), step time is within noise. My machine is a loaded VM, so the paired median ratios fall between 0.91 and 1.03. Mean evaluations per line search are unchanged or lower, apart from +0.01 on humanoid-pyramidal, where the chaotic trajectory diverges at rounding level. Max evaluations never go up.

The engine test suite passes in double and single, apart from 3 plugin-registration tests that also fail without the patch in my partial build.

**Questions:**
1. Would you accept (1) as a standalone PR for this issue?
2. Should (2) and (3) be separate follow-ups, or folded in, or not wanted at all?
3. For (3): do you want a new `mjtWarning`, or would you rather surface this another way (e.g. only in `mjSolverStat`)? Also, is recording the failed line search as an iteration acceptable?
4. Are there constraints on the line search I should respect? For example, keeping MJX/Warp parity (#3619 touches the MJX line search) or keeping the midpoint for some cases.

I'm happy to adjust the approach. For example, I could snap to a kink only inside the middle half of the bracket, or use the Genesis-style "next kink from each end" (Genesis-Embodied-AI/genesis-world#3382). I tried a version of the latter (clamping each end's Newton step at the next kink), and it was slightly worse on this benchmark than nearest-to-midpoint.
