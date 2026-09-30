# Study guide: MuJoCo #3628, line-search exhaustion with elliptic cones

## 1. The Newton method in MuJoCo's convex contact formulation

MuJoCo computes the constrained acceleration `qacc` by solving a convex optimization problem, not a complementarity problem. The primal problem that the CG and Newton solvers work on is

    minimize over a:  ½ (a − a0)ᵀ M (a − a0)  +  s(J a − aref)

- `a0 = qacc_smooth` is the unconstrained acceleration.
- The first term is the Gauss term: it penalizes deviation from unconstrained motion in the inertia metric.
- `s` is a sum of per-constraint costs. Each one is a quadratic penalty inside its "active" region, weighted by `D = 1/R`, where `R` is the regularizer set by solref/solimp.

Each constraint type has its own cost shape:

| constraint | cost |
|---|---|
| equality | always quadratic |
| inequality (joint limit, frictionless or pyramidal contact row) | quadratic when `Ja − aref < 0`, else 0 |
| friction loss | Huber: quadratic inside ±R·f, linear outside |
| elliptic contact | three zones (section 2) |

The cost is convex and continuously differentiable (C¹). That is what makes it a well-posed optimization problem.

The Newton solver (`mj_solPrimal` with `flg_Newton`, in `engine_solver.c`) works as follows:

1. Compute the gradient g and Hessian H = M + Jᵀ D_active J, plus the cone Hessian blocks for contacts in the middle zone.
2. Factor H with Cholesky. When constraint states change, the factor is updated incrementally with rank-1 updates.
3. Take the search direction d = −H⁻¹g.
4. Run an **exact line search** along d: minimize f(α) = cost(a + αd) over α.
5. Stop when the improvement, the gradient, or the Newton decrement ½gᵀH⁻¹g falls below `tolerance`.

On a quadratic piece the Newton step is exact, so α = 1 is the first guess.

**The line search (`PrimalSearch`).** f is one-dimensional, convex and C¹. f′ and f″ are computed analytically in `PrimalEval`, and every call to `PrimalEval` counts as one evaluation against `ls_iterations`.

- **Initial step.** Evaluate at 0, then take a Newton step p1 = −f′(0)/f″(0). If |f′(p1)| < gtol, stop.
- **One-sided phase.** Keep taking Newton steps while f′ keeps its sign.
- **Bracketed phase.** Once f′ changes sign, the bracket is [p1, p2]. Each iteration evaluates:
  - the midpoint `pmid`, and
  - a Newton candidate from each bracket end (`p1next`, `p2next`).

  A candidate replaces a bracket end when its f′ has the same sign and a smaller magnitude. Since f′ is monotone, that means the candidate lies between that end and the root.
- **Stopping.** Return when any candidate has |f′| < gtol. If the budget runs out, return the better bracket end if its cost is below 0. Otherwise return α = 0, which is `LSresult` 5.

The trap is in `mj_solPrimal`: `if (alpha == 0) break;`. A line search that finds no improvement ends the solve, just as a converged one would.

## 2. Elliptic vs. pyramidal cones

**Pyramidal cones.** Friction is linearized into 2(dim−1) edges of a pyramid. Each edge is an ordinary inequality row, so every piece of the cost is quadratic, f′ is piecewise linear, and Newton is exact on each piece. MuJoCo sets the pyramidal R so that its impedance matches the elliptic model.

**Elliptic cones.** There is one block of dim rows per contact. In PrimalPrepare's scaled coordinates, N = μ·(normal residual) and T = ‖scaled tangential residuals‖. The block has three zones:

| zone | condition | cost |
|---|---|---|
| top | N ≥ μT | 0 (separating, no force) |
| bottom | μN + T ≤ 0 | full quadratic over all rows (sticking: force strictly inside the cone) |
| middle | otherwise | ½·Dm·(N − μT)² (sliding: force on the cone surface) |

In the middle zone T(α) = √(quadratic in α), so this piece is smooth but not quadratic.

**impratio.** `impratio` sets R_friction = R_normal / impratio. Friction rows are therefore impratio times stiffer (D = 1/R), and the regularized cone has μ = friction·√(R1/R0) = friction/√impratio. In the repro μ = 0.316 = 1/√10.

MuJoCo's docs recommend elliptic cones with a large impratio to reduce slip. So the failing configuration is exactly the one users are told to use.

## 3. Why the line-search cost is piecewise smooth

Along the search direction every constraint residual is affine in α: x_i(α) = Jaref_i + α·Jv_i. f(α) is the sum of each constraint's cost evaluated along its affine path. It changes formula whenever some constraint crosses a zone boundary:

- an inequality row crosses x = 0
- a friction-loss row crosses x = ±R·f
- an elliptic contact crosses N = μT (top/middle) or μN = −T (middle/bottom)

At each crossing f and f′ are continuous, because the cost is C¹ by construction; it is a Moreau-envelope-like penalty. **f″ jumps.** For elliptic contacts the jump between the sliding and sticking zones is roughly "normal-only curvature" versus "normal plus impratio-stiff tangential curvature". In the repro it is much larger than impratio alone, because it also includes the ratio of contact curvature to Gauss curvature:

- f″ ≈ 6e5 below α = 0.0207 (middle zone plus Gauss)
- f″ ≈ 3.4e8 on [0.0207, 0.0309] (bottom zone)
- f″ ≈ 1.1e8 above 0.0309 (middle again)

Boundaries in closed form:

- **Top boundary.** N = μT with N ≥ 0. Squaring gives (V0² − μ²VV)α² + 2(U0V0 − μ²UV)α + (U0² − μ²UU) = 0.
- **Bottom boundary.** μN = −T with N ≤ 0. Squaring gives (μ²V0² − VV)α² + 2(μ²U0V0 − UV)α + (μ²U0² − UU) = 0.

Here U0 and V0 are the scaled normal residual and its rate, and UU, UV, VV are the tangential sums of squares that PrimalPrepare already stores in `quad[3..7]`. Squaring admits spurious roots on the wrong side of N = 0, so each root is filtered by the sign of N(α).

## 4. Why derivative-based refinement stalls at kinks

A Newton step from a point uses the local curvature: α⁺ = α − f′(α)/f″(α). Suppose a curvature jump by a factor r lies between the point and the root.

- **From the low-curvature side**, the step overshoots by up to a factor of r and lands far beyond the root, often outside the bracket.
- **From the high-curvature side**, the step also crosses the kink. Past the kink the true curvature is lower, so the step lands deep on the low side.

The repro trace (`bench/results/ls_trace_base.txt`, second line search) shows both effects:

- the bracket is [0.00467, 0.99873]
- the Newton step from 0.99873 (f″ = 1.1e8) goes to 0.0046720, improving the low end by ~1e-9
- the Newton step from 0.00467 (f″ = 6e5) goes to 0.998734, improving the high end by ~1e-9
- only the midpoint makes real progress

So each bracketed iteration costs 3 evaluations and halves the bracket once. Narrowing a bracket of width about 1 down to the 0.01-wide piece holding the root takes about 7 halvings, which is about 21 evaluations. Add the 2 initial evaluations and you get the observed 23. With ls = 20 the search exhausts its budget and returns the best bracket end (improvement, but not converged).

The next line search starts from a bracket of about [−0.016, 1.0] around a root inside [0.00046, 0.011]. It would need about 10 halvings, which is 30 evaluations. Every point it reaches has cost ≥ 0, so it returns α = 0 and the solver stops.

**Why the result is a fixed point.** Restarting from the returned qacc gives the same Hessian, the same direction and the same failed line search, so the solver breaks with 0 iterations. Neither the solver statistics nor the warnings show anything, and the final gradient is about 124 against a tolerance of 1e-8.

**Why the gradient-based checks do not catch it.** The zero-iteration certificate needs the gradient to be below tolerance, and it is not. But `alpha == 0` is a separate exit, and it is taken before any statistics are saved.

## 5. The fix and its trade-offs

### PR 1: zone-boundary bracketing

- In the bracketed phase, replace the midpoint with the zone boundary strictly inside (lo, hi) that is nearest to the midpoint (`PrimalKink`). If the bracket contains no boundary, use the midpoint as before.
  - Evaluating a boundary always moves a bracket end onto it, because f′ is monotone. A boundary is therefore never evaluated twice, and the bracket quickly shrinks to the smooth piece that contains the root.
  - Inside that piece, Newton from the ends uses the correct curvature. It is exact on quadratic pieces (pyramidal, inequality, friction loss, bottom and top zones) and converges quadratically on the middle zone.
  - In the repro the search evaluates 0.030926 and then 0.020678, which are exactly the two bottom-zone boundaries, and Newton then lands on the root 0.0224053 with f′ = 0. That is 10 evaluations instead of 23 (`ls_trace_fix.txt`).
- Skip evaluating a Newton candidate that lies outside the current bracket, and reuse the bracket end instead. Because f′ is monotone, a point outside [lo, hi] has |f′| at least as large as the nearer end. It can neither replace an end nor pass the convergence test, so evaluating it is a provably wasted evaluation.

**Why nearest to the midpoint, and not the "next kink" from each end as Genesis does?**

- If boundaries are dense, the nearest one is close to the midpoint, so the search behaves like bisection. If they are sparse, it isolates the smooth piece in a few evaluations.
- I also tried clamping each end's Newton step to its next kink. On the 40k benchmark that gave more exhausted line searches than nearest-to-midpoint (215 vs 132 in that iteration of the experiment, with mean evaluations 5.58 vs 5.41). Combining both gave no gain.
- I also tried a secant (regula falsi) step when the bracket holds no kink. It gave no gain either.

**Trade-offs:**

- **Worst-case count.** If many boundaries cluster away from the root, the search can take one evaluation per boundary instead of one per halving, so the worst case is O(#kinks + log(width/tol)) instead of O(log). A middle-half safeguard (snap only to boundaries inside [lo + w/4, hi − w/4]) would guarantee the bisection rate, but in the repro it would delay the kink by about 4 halvings. I left it as an option for review. Measured: max evaluations went down in every configuration.
- **Cost per bracketed iteration.** `PrimalKink` is O(nefc), with 2 square roots per elliptic contact and no matrix products. It runs only in the bracketed phase; most line searches finish in the Newton phase with 2–3 evaluations.

### PR 2: tolerance floor

- f′ = Σ terms, where the terms are much larger than their sum near the root. The rounding error is about ε·Σ|terms|; the worst-case bound is n·ε·Σ|terms| and typical error is smaller.
- When gtol falls below that, the sign of f′ is noise and the bracket cannot converge, so the search burns the whole budget. This happens with `tolerance = 0` (the documented way to disable early termination), and in float32 with the default tolerance.
- Floor: max(gtol, ε·(LSnoise[0] + |α|·LSnoise[1])), with the magnitudes accumulated in `PrimalPrepare`.
  - In double with the default tolerance it never activates: gtol is about 5e-6, while ε·Σ|terms| is about 2e-8 for terms around 1e8. Trajectories are bitwise identical.
  - It is cheap: two sums in a loop that already exists.
- Trade-off: with tolerance 0 the line search stops at noise level instead of at "no bracket update possible". The outer loop still runs until no improvement is possible.

### PR 3: warning (API change)

- New `mjWARN_LINESEARCH`. It is raised in the serial part of `fwdConstraint` by scanning `d->solver` stats for neval ≥ ls_iterations. Islands can be solved on a thread pool, so calling `mj_warning` inside a solve would be a data race on `d->warning`.
- The failed line search with α = 0 used to be invisible, because it broke out of the loop before `saveStats`. It is now recorded as an iteration with improvement 0. This changes `niter` by +1 in exactly that failure case.
- Trade-offs:
  - It is an ABI change: `mjNWARNING` goes from 7 to 8, so `mjData` changes size.
  - "Used all" also counts a line search that converged exactly on its last evaluation.
  - It must land after PR 2, or tolerance-0 and float32 users would see it constantly.

## 6. Precision concerns

- **Boundary roots** use the numerically stable quadratic formula: q = −(b + sign(b)·√disc), with roots q/a and c/q. This avoids the cancellation of −b + √disc. There are guards for a ≈ 0 (linear case, using `mjMINVAL`), disc < 0 (no root), and strict interior (lo < x < hi), so a bracket end is never re-evaluated.
- **Correctness does not depend on root accuracy.** A boundary is only a candidate point. The bracket invariant (opposite signs of f′ at the ends) is maintained by evaluating f′, not by trusting the root. In float32 an inaccurate root costs efficiency, never correctness. The same holds for sign filtering near N = 0.
- **ε is chosen by precision:** `DBL_EPSILON` or `FLT_EPSILON` through `#ifdef mjUSESINGLE`. This follows the precedent of `engine_collision_gjk.c` and `engine_util_solve.c`.
- **float32 before the fix** exhausted budgets massively: 29,498 of 133,261 line searches at ls 20, and 14,201 of 116,829 at the default ls 50 with impratio 1. After the fix: 131 and 0.
- **Tests** use `MjTol` / `MjNear(double_tol, float_tol)`, calibrated with `MJTOL_SCALE=0`: at ls 20 the patched solve matches the ls 200 reference with a residual of exactly 0 in double.

## 7. Results (key numbers)

**40k solves, elliptic, impratio 10, ls 20** (`bench/results/bench40k.txt`):

| | main f64 | patched f64 | main f32 | patched f32 |
|---|---|---|---|---|
| \|Δqacc\| > 1 | 478 (max 708) | 0 (max 2.4e-7) | 20 (max 148) | 0 (max 6.7e-4) |
| false fixed points | 590 | 0 | 20 | 0 |
| mean / max evaluations | 6.15 / 22 | 5.29 / 22 | 11.67 / 22 | 4.40 / 22 |
| used whole budget | 5,208 | 334 (0 ended the solve) | 29,498 | 131 |

Other results:

- **The issue's exact state.** The evaluation counts go from [7, 20] (wrong answer, off by 59) to [7, 10, 2] (converged) at every ls ≥ 20. In float32 they go from [12, 22, 2] to [6, 7, 2].
- **Pyramidal cones in double:** identical statistics.
- **Default settings in double:** mean evaluations 4.18 → 4.17 and max 20 → 14. In float, mean evaluations 14.38 → 3.60.
- **tolerance = 0, test humanoid, Newton:** mean evaluations 45.3 → 2.0, and exhausted line searches 17,109 → 0.
- **Step time** on humanoid, 22_humanoids and boxpile, in double and single, pyramidal and elliptic, impratio 1 and 10: the paired median ratio patched/main is 0.91–1.03 on a loaded shared VM (load average about 21 on 4 cores), so it is noise-limited at about ±5%. There is no evidence of regression. The largest gains are in float32 with elliptic cones, where evaluations per line search drop by about 3.6×.
- **Tests:** 3 new solver tests. Each fails on main and passes when patched, in both precisions. The engine suite has 985 tests in each precision; all pass except 3 plugin-registration tests that fail identically on main in my partial build.

## 8. Likely interview questions

**1. Why is MuJoCo's contact problem convex, and what does Newton actually iterate on?**
MuJoCo replaces complementarity with a regularized optimization over accelerations: the Gauss term plus convex penalties on constraint residuals, which is a primal form of a soft-constraint dual. Newton iterates on qacc. The Hessian is M + JᵀDJ over the active rows, plus the cone blocks. Each step solves with a Cholesky factor that is updated by rank-1 changes when constraint states flip, followed by an exact 1-D line search.

**2. The cost is C¹. Why isn't Newton in 1-D enough?**
Newton's convergence theory needs f″ to be Lipschitz near the root. Here f″ jumps at zone boundaries. A Newton step from the wrong side of a jump uses a curvature that is off by the jump ratio (hundreds here), so it overshoots across the kink. Safeguarded Newton then falls back to bisection. In this implementation that costs 3 evaluations per halving, because both Newton candidates are still evaluated.

**3. Walk me through why a single contact needs 23 evaluations.**
2 initial evaluations, then about 7 bracketed iterations × 3 (midpoint plus two nearly useless Newton candidates) to shrink the bracket from width 1 to the 0.01-wide bottom-zone piece that holds the root. Then Newton hits the root.

**4. Why does a budget overrun become a wrong answer rather than just a slower one?**
If the budget runs out and neither bracket end has negative cost, `PrimalSearch` returns α = 0. `mj_solPrimal` treats α = 0 as "no improvement possible" and stops. That exit is shared with genuine convergence and records no statistics. The restart is deterministic, so the same failure happens again: a false fixed point.

**5. Why is evaluating the kink the right move?**
The kinks partition the bracket into smooth pieces, and on a smooth piece Newton is exact or quadratically convergent. Evaluating the kinks isolates the piece that contains the root. Each kink evaluation either lands a bracket end on the kink or converges. Rounding in the kink computation cannot break correctness, because the bracket is maintained by f′ values.

**6. Can your change be slower than before?**
In theory yes: with many boundaries clustered away from the root, you pay one evaluation per boundary. In practice, max evaluations dropped in every configuration I measured, and the mean dropped or stayed flat. `PrimalKink` costs less than one evaluation and only runs in the bracketed phase. If reviewers want a hard guarantee, snapping only inside the middle half of the bracket gives the bisection rate back.

**7. How do you know skipping out-of-bracket Newton candidates is safe?**
f is convex, so f′ is monotone. A point outside [lo, hi] beyond hi has f′ ≥ f′(hi) > 0, so it can neither replace hi (which needs a smaller positive f′) nor satisfy |f′| < gtol (hi already fails that). The symmetric argument holds below lo. Skipping only removes evaluations that could not change the result.

**8. Why eps·Σ|terms| for the floor? Isn't that arbitrary?**
It is the first-order rounding scale of a floating-point sum. The rigorous worst-case bound is about n·ε·Σ|x_i|, and typical errors are smaller. Below this value the computed sign of f′ carries no information. In double with the default tolerance the floor is 2–3 orders of magnitude below gtol and never activates (trajectories are bitwise identical). It only matters when the requested tolerance is physically unresolvable: tolerance 0 or float32.

**9. What did you verify for single precision specifically?**
- Built with `-DmjUSESINGLE` and ran the whole engine suite.
- Each new test fails on main and passes when patched, in float as well.
- The benchmark in float: false fixed points 20 → 0, budget exhaustion 29,498 → 131, and evaluations per line search 11.7 → 4.4.
- Tolerances go through `MjTol`/`MjNear`.
- The boundary math is written so that float error affects efficiency only.

**10. Why three PRs, and why ask first?**
- CONTRIBUTING asks contributors to get in touch before non-trivial changes and to keep PRs small.
- PR 1 fixes the reported bug with no API change.
- PR 2 is a separable precision and efficiency improvement.
- PR 3 is an API/ABI change (a new warning and a larger `mjData`) and a change to what `niter` reports. Those are design decisions the maintainers should make. It also depends on PR 2, or it would fire constantly for tolerance-0 and float users.

**11. Why is the warning raised in `fwdConstraint` and not inside the solver?**
Islands can be solved in parallel through `mju_dispatch`, and `d->warning` is shared, so calling `mj_warning` inside the solver would race. Each island writes only its own `mjSolverStat` slots, so reading them after the dispatch is race-free.

**12. How is this different from Genesis PR #3382 and MJX PR #3619?**
- Genesis takes the next kink from the current point instead of the midpoint and adds the same kind of noise floor. It is the precedent the issue cites. I tried a "next kink" variant; nearest-to-midpoint measured slightly better here.
- MJX #3619 changes the JAX line search's acceptance test to be sign-independent. It touches different code and addresses a different failure: rejecting converged candidates.
- The C change here does not touch MJX or Warp. Whether to port it is a maintainer question.

## 9. Honest limitations

- In double at impratio 10, ls 20, 334 of about 130k line searches still use the full budget. These are slow convergence in strongly curved middle-zone pieces, not kinks. All of them still return an improvement, and the outer Newton loop converges; there are 0 wrong answers.
- The benchmark uses my own protocol: random drops, kicks every 50 steps, and a reference trajectory at ls 200. The issue's exact 40k protocol was not published. On main my protocol yields 478 bad solves; the issue reports 28.
- I did not test Menagerie's G1 humanoid, which the issue reports 16/20k failures on. It is not in the repo, and I did not fetch Menagerie.
- Timings come from a heavily loaded shared VM. They are adequate to rule out large regressions, not small ones.
- Python, WASM and Unity bindings were updated by hand for PR 3 but not built or tested.
