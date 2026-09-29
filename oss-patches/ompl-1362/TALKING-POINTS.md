# ompl#1362: OwenStateSpace path failures, study guide

## 1. The problem in one paragraph

`OwenStateSpace` models a fixed-wing aircraft as a 3-D Dubins airplane: a 2-D Dubins car (turn radius ≥ ρ) plus altitude, with |pitch| ≤ θmax. `getPath()` sorts a start/goal pair into three cases:

- **Low altitude:** the shortest 2-D Dubins path is long enough to climb |dz| at pitch ≤ θmax. Use it as is.
- **Medium altitude:** the 2-D path is too short, but by less than one full circle. Add an extra turn φ at radius ρ at the start, then fly a Dubins path.
- **High altitude:** the path is short by more than a full circle. Fly k helix loops, then a Dubins path, both at a radius r ≥ ρ.

The medium and high cases are solved with a 1-D root finder: find φ or r so that the horizontal length equals |dz|/tanθmax. That root finding failed for 1–17% of random pairs, depending on the workspace (the reporter saw ~25%).

## 2. Dubins words and where they exist

A Dubins path between two poses is one of six "words" of arcs (L/R) and straights (S): **LSL, RSR, RSL, LSR, RLR, LRL**. Each has a closed form for (t, p, q), the lengths of its three segments, in units of the turn radius r. The distance is normalized, d = |Δxy| / r.

| word | exists when | as r grows (d shrinks) |
|---|---|---|
| LSL, RSR | always (tangent between two same-direction circles) | always exists |
| RSL, LSR | circle centers ≥ 2r apart (the cross tangent needs non-overlapping circles) | **disappears** above some r |
| RLR, LRL | circle centers < 4r apart (the middle circle must touch both) | **appears** above some r |

The arc angles t and q are taken `mod 2π`, i.e. in [0, 2π). When the needed arc passes through 0 it **wraps**: the length jumps by 2π (2πr in meters) and the path now contains an extra loop.

## 3. Why the shortest length is discontinuous in r (and φ)

The old code solved `f(r) = r·(L*(r) + 2πk)·tanθ − |dz| = 0`, where L*(r) = min over words. A minimum of continuous functions is continuous. But each word's length is only continuous **while that word exists and none of its angles wraps**. So L*(r) jumps up when:

- the optimal word stops existing (e.g. RSL at its 2r limit; the next best word is longer),
- the optimal word's arc wraps from 0 to 2π,
- (for φ) the pose at the end of the extra turn moves, so all of the above happen as φ varies.

`bracket_and_solve_root` / TOMS 748 only guarantee convergence to a **sign change**. A jump from negative to positive is a sign change, so the solver converges to it and the residual check rejects it.

**The second bug (the bigger one in large workspaces).** `eps_tolerance(20)` stops once the bracket is ~2⁻¹⁹ ≈ 2e-6 wide (relative), and then `|f(midpoint)| ≤ 1e-5` was required. The slope is ≈ (L + 2πk)·tanθ, so with a few loops |f(mid)| ≈ slope · 1e-6 > 1e-5 even though the root is inside the bracket. At [-100,100]^3 **all** 6418 old failures were of this kind. I showed this with `bench/classify_failures_before.cpp`, which re-runs the exact old solver call and checks whether f is continuous across the final bracket.

## 4. The fix: bracket per word

For a **fixed** word, f is continuous in r (or φ) except at the few points where an angle wraps or the word appears or disappears. So:

1. For each word, sample the search interval on a coarse grid (8 steps for r; 8 then 64 for φ).
2. At the first sign change, refine with TOMS 748 using a tight tolerance (53−3 bits).
3. **Accept only if the residual is actually small** (≤ 1e-8 · horizontal length). A jump leaves a big residual and gets rejected, and the scan moves to the next interval.
4. Return the end of the final bracket where f ≥ 0. f ≥ 0 means "horizontal length ≥ needed", so pitch ≤ θmax. The result never exceeds the pitch limit.
5. If a word doesn't exist at a sample, f returns +max. It's treated as positive, and the residual check rejects the sign change it creates.

**Why the first solution is fine.** When a path climbs at exactly θmax, its horizontal length is |dz|/tanθ, so its 3-D length is |dz|/sinθ, **the same for every solution**. That value is also a lower bound for *any* path with pitch ≤ θmax. So every root is optimal and we can return the first one. That is also why `distance()` doesn't change when a different word is chosen.

## 5. The helix and k-loop logic (high altitude)

- H(r) = r·(L_w(r) + 2πk). For each word, k = ⌊(H*/ρ − L_w(ρ)) / 2π⌋, the most loops that still leave f(ρ) ≤ 0. More loops would need r < ρ. Fewer loops give a larger r.
- **Upper bound:** H(r) ≥ 2πkr, so r ≤ H*/(2πk). The search interval is finite.
- **Wraps:** if an arc of the word wraps from 0 to 2π as r grows, the Dubins path gains a loop and f jumps up by 2πr. The same geometric path is then described by k−1 helix loops. So each word also tries k−1, including k−1 = 0, where the "loop" lives inside the Dubins path. That fixed real cases, e.g. an LSL path where the only root was on the k−1 branch.
- Try the word that is shortest at ρ first. It usually has the root near r ≈ ρ (the old behaviour when it worked).

## 6. Medium altitude

- φ ∈ [0, 2π] in both directions. At φ = 0, f < 0 (that's why we're in the medium case). At φ = 2π the pose is back at the start and f ≥ 0 by the case condition. So for a continuous word there has to be a root.
- **Skip words that start turning the same way as φ.** Turning left by φ and then flying LSx just shortens the first L arc by φ, so the total is constant until it wraps. Such a word can never have a genuine root. That leaves 3 words per direction.
- The coarse (8) grid finds almost everything. The fine (64) pass is for roots in narrow windows between two jumps, and it costs extra only when the coarse pass fails.
- `PathType::length()` used `phi_` with its sign. Right turns (φ < 0) were never returned by the old code, so the bug was hidden. Now it uses |φ|.

## 7. Verification against brute force

`bench/owen_bench.cpp`:

- **Re-implements** the six Dubins words (no OMPL internals), so the reference doesn't depend on the code under test.
- **Reference:** low altitude: shortest Dubins length. Otherwise: does *any* (word, k, r) on a 3000-point log grid in r, or (word, direction, φ) on a 4000-point grid, give a genuine root? The same continuity check is refined with bisection. If yes, the optimum is |dz|/sinθ.
- **Bound on k** in the brute force: any path feasible at radius r ≥ ρ is feasible at ρ, so its horizontal length is ≥ L*(ρ). That gives k ≤ (H − L*(ρ))/(2πρ).
- **Independent geometric checks:** `interpolate()` at t → 1 must reach the goal (x, y, z, yaw), radius ≥ ρ, and pitch ≤ θmax.
- **Every failure is classified:** does the brute force find a path (then it's a miss) or not (then it's infeasible)?
- **Behaviour diff:** paths from before and after are dumped (`OWEN_DUMP=file`) and compared. Lengths agree to 1.5e-6 (the old tolerance), and ~8% of pairs get a different but equally long geometry.

## 8. Results (100k pairs, ρ = 1, θmax = 30° unless noted)

| workspace | fail before | fail after | after, brute force finds a path | max rel. gap before → after |
|---|---|---|---|---|
| [-10,10]^3 | 1245 | 164 | 9 | 5.19 → 5e-16 |
| [-3,3]^3 | 5328 | 2111 | 73 | 2.25 → 0.45 |
| [-100,100]^3 | 6426 | 1 | 0 | 2.6 → 8e-16 |
| [-1000,1000]^3 | 4945 | 0 | 0 | 11.8 → 4e-16 |
| [-100,100]^3, 15° | 17458 | 0 | 0 | 1.23 → 9e-16 |

The median gap is 0 both before and after (most pairs are low altitude or were already solved).

**Remaining failures.** All of them have horizontal distance < 4ρ (max 3.95). Most are **infeasible for Owen's path families**: from nearly aligned, close poses, "turn φ + Dubins at ρ" and "loops + Dubins at r ≥ ρ" cannot produce every horizontal length between L* and L* + 2πρ. The rest are narrow root windows that the 64-step grid misses (9 / 100k at [-10,10], 73 / 100k at [-3,3]). Real fixed-wing workspaces are many turn radii across, which matches the rows where the failure count is 0.

**Runtime** (distance(), noisy shared machine): [-10,10]: 3.1 → 3.9 µs; medium case ~9.8 → 15 µs. [-100,100]: 1.9 → 1.8. 15°: 2.9 → 2.1. Low altitude unchanged. Infeasible pairs cost the most (they run the 64-step fallback), which is why [-3,3] went 3.9 → 9.3 µs.

## 9. Trade-offs and decisions

- **Per-word grid scan vs. smarter unwrapping.** I could track angle wraps explicitly (unwrap t and q by continuity), but that needs Dubins internals and more code. The grid plus residual check is simple, local, and easy to verify.
- **First solution vs. "best" solution.** Every solution has the same length, so the first one is taken, starting with the word that is shortest at ρ, for speed. Picking the smallest r or |φ| is possible but costs more evaluations.
- **New public overload** `DubinsStateSpace::getPath(s1, s2, r, pathType)`. It's additive, reuses the existing closed-form word functions, and returns length = max when the word doesn't exist (the same convention the internals use).
- **Tolerance direction.** Returning the f ≥ 0 end means the path is at most 1e-8 relative too long, but never too steep.
- **Known cosmetic quirk.** A high-altitude solution with k = 0 reports `category()` as LOW_ALTITUDE, because the category is inferred from (phi, numTurns). Interpolation is correct because it uses the stored radius. This could be a follow-up.
- **#1470** changes the same block (asymmetric climb/descent pitch). My code only uses the pitch through `horizontalLength = |dz|/tanMaxPitch_` and the case condition, so the rebase is two identifier changes (`tanMaxPitch_` → `tanPitch`). I did it locally (`ompl-1362-on-pr1470.diff`) and it compiles.

## 10. Likely interview questions

1. **Why did the root finder fail?**
   Two reasons. (a) It ran on the shortest Dubins length, which is discontinuous in r and φ (word switches, words appearing or disappearing, angle wraps), so the solver converged to a jump. (b) In the high altitude case the solver tolerance (2⁻¹⁹ relative in r) was inconsistent with the absolute 1e-5 residual check at the midpoint. That alone caused all failures in large workspaces.

2. **Why is the per-word length continuous, and when isn't it?**
   The closed forms for t, p, q are smooth in (d, α, β), which are smooth in r (and φ). The only breaks are the `mod 2π` on t and q, and the existence conditions: RSL/LSR need centers ≥ 2r apart, RLR/LRL need them < 4r apart.

3. **How do you avoid converging to a jump?**
   The sign change is refined, then the residual is checked. A jump leaves a residual of order 2πr·tanθ, far above 1e-8·H, so it's rejected and the scan continues with the next interval.

4. **Why is any root good enough? Doesn't the choice of word matter?**
   At max pitch the horizontal length is fixed at |dz|/tanθ, so every solution has 3-D length |dz|/sinθ. That is also a lower bound for any pitch-limited path, so all roots are optimal. The word only changes the shape, not the cost.

5. **How is k chosen, and why also k−1?**
   k is the most loops that still fit at r = ρ, which gives the smallest radius. When an arc wraps from 0 to 2π, the Dubins part gains a loop, so the same path needs one fewer helix loop. k−1 covers that, including k−1 = 0.

6. **Why skip same-direction words in the medium case?**
   Turning left by φ and then flying an L-first word just eats into that word's first arc, so the total length stays constant until it wraps. Such a word never has a genuine root.

7. **How did you know the brute force was right?**
   It shares no code with the fix (the words are re-implemented) and uses dense grids plus bisection with a continuity check. Every returned path is also checked geometrically: `interpolate()` reaches the goal, and radius and pitch are within limits. The reference optimum |dz|/sinθ is a provable lower bound.

8. **What still fails, and why not fix it?**
   Pairs less than 4 turn radii apart where no Owen-type path exists. The brute force confirms it for ~95% of the remaining failures. Fixing those needs a new path family (e.g. S-turn detours), which is a model change, not a bug fix. The rest are narrow windows that a finer grid would catch at extra cost.

9. **What did it cost in performance?**
   Medium altitude `distance()` is ~1.5× slower (up to 6 word/direction searches). High altitude is the same or faster. Low altitude is untouched. Pairs with no solution pay for the 64-step fallback. Overall it's within ±30% in realistic workspaces, and faster where the old code used to fail.

10. **How does this interact with #1470?**
    Both rewrite `getPath()`'s medium/high block. My version isolates the pitch in one quantity (`horizontalLength`), so rebasing is mechanical. I'll rebase whichever lands second.

## 11. Commands

```
cmake -DOMPL_BUILD_PYBINDINGS=OFF -DOMPL_BUILD_DEMOS=OFF -DCMAKE_BUILD_TYPE=Release ..
make ompl test_state_spaces test_state_operations test_directed_specs
ctest -R "test_state_spaces|test_state_operations|test_directed_specs" --output-on-failure
./tests/test_state_spaces --run_test=Owen_RandomPairs
bench/run_bench.sh   # builds owen_bench against the before/after libompl and writes the matrix
```
