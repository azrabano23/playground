**Title:** OwenStateSpace: solve for medium/high altitude paths per Dubins path type (fixes #1362)

Fixes #1362.

`OwenStateSpace::getPath()` often returned `nullopt` for medium and high altitude pairs. I found two causes.

1. **Tolerance mismatch (high altitude).** `bracket_and_solve_root` used `eps_tolerance(20)`, so it stopped once the bracket was about 2e-6 wide (relative). The result was then rejected if `|radiusFun|` at the bracket midpoint was above an absolute 1e-5. With k helix turns the slope of `radiusFun` is about `2πk·tan(pitch)`, so the midpoint often failed the check even though the root was inside the bracket. In [-100,100]^3 this accounts for all 6418 high altitude failures.
2. **Discontinuities (medium and high altitude).** The root finding ran on the length of the *shortest* Dubins path. That length jumps when the optimal word changes, when a word stops existing (RSL/LSR need the turning circles at least 2r apart, and RLR/LRL need them less than 4r apart), or when a turn angle wraps around 2π. The solver would then converge onto a jump. In [-10,10]^3 this caused 266 of 333 high altitude failures and 877 of 912 medium altitude failures. The `phi < 0` retry in the medium case never succeeded in my runs.

## Change

- Every non-low path flies at max pitch, so its horizontal length has to be exactly `|dz| / tan(maxPitch)` and all solutions have the same length. The code now solves **for each Dubins word separately**. For a fixed word the length is continuous in `r` (or `phi`), except where a turn angle wraps around or the word stops existing.
- New helper `smallestRoot()`. It samples the search interval on a coarse grid and refines the first sign change with TOMS 748. It only accepts the result if the residual is actually small (`1e-8 · horizontalLength`), so a sign change caused by a jump is skipped and the search continues. It returns the end of the bracket with residual ≥ 0, so the path never exceeds the max pitch.
- **High altitude:** starts with the word of the shortest path at `rho_`. For each word, `k` is the largest number of helix turns that isn't already too long at `r = rho_`, and `r` is bounded above by `horizontalLength / (2πk)`. `k-1` is also tried, which covers a turn angle wrapping around (the jump then means one extra loop is already inside the Dubins path).
- **Medium altitude:** searches `phi` in `[0, 2π]` for both turn directions. Words that start turning in the same direction as `phi` are skipped: the extra turn just merges into their first arc, so their length never changes. The search runs on an 8-step grid first and falls back to 64 steps only if that finds nothing.
- `PathType::length()` now uses `|phi_|`. Right-turn medium paths (`phi_ < 0`) were never returned before, so this bug didn't show up.
- New overload `DubinsStateSpace::getPath(state1, state2, radius, pathType)` that returns the path of a single word. The existing API and the low altitude case are unchanged.

## Results

I sampled 100k random pairs (fixed seed), with turn radius 1 and max pitch 30° unless noted. "Gap" is the relative difference of `distance()` to a brute-force reference that uses no root finding: the Dubins words are re-implemented and `r`, `k` and `phi` are scanned densely. The median gap is 0 before and after.

| workspace | failures before | failures after | after: brute force finds a path | max gap before → after | `distance()` µs before → after |
|---|---|---|---|---|---|
| [-10,10]^3 | 1245 (1.2%) | 164 (0.16%) | 9 | 5.19 → 5e-16 | 3.1 → 3.9 |
| [-3,3]^3 | 5328 (5.3%) | 2111 (2.1%) | 73 | 2.25 → 0.45 (1 of 2000) | 3.9 → 9.3 |
| [-100,100]^3 | 6426 (6.4%) | 1 | 0 | 2.6 → 8e-16 | 1.9 → 1.8 |
| [-1000,1000]^3 | 4945 (4.9%) | 0 | 0 | 11.8 → 4e-16 | 1.3 → 1.3 |
| [-100,100]^3, 15° pitch | 17458 (17.5%) | 0 | 0 | 1.23 → 9e-16 | 2.9 → 2.1 |

- **Remaining failures.** Every remaining failure has start and goal less than 4 turn radii apart horizontally (the largest is 3.95). For almost all of them (155 of 164 in [-10,10]^3, 2038 of 2111 in [-3,3]^3) the brute force finds no path of Owen et al.'s form either. Neither "turn by phi, then a Dubins path at `rho`" nor "k helix turns, then a Dubins path at some `r ≥ rho`" can produce the required horizontal length there. Handling those pairs needs a different kind of path (e.g. an S-shaped detour), which I think is out of scope. The rest (9 and 73) are narrow windows between two jumps that the 64-step grid misses.
- **Validity checks.** Every returned path ends at the goal (checked via `interpolate()` at t → 1, max error 7.5e-9 in the largest workspace) and none exceeds the max pitch or goes below the minimum radius. Before, 21 paths in [-10,10]^3 exceeded the max pitch slightly (horizontal length short by up to ~1e-5 relative), because the midpoint of the bracket can be on the too-steep side.
- **Runtime.** The medium altitude case got slower, from ~9–10 to ~12–15 µs in [-10,10]^3, because up to 6 word/direction combinations are searched. Pairs with no solution pay for the 64-step fallback, which is why [-3,3]^3 is slower overall. High altitude cost is unchanged or lower, and low altitude is untouched. The machine was heavily loaded, so treat the timings as ±20%.
- **Geometry changes.** When both versions succeed, the lengths agree to within 1.5e-6 (the old solver tolerance). The chosen word, radius or `phi` can differ (in ~8% of pairs in [-10,10]^3), because all max-pitch solutions are equally long and the new code returns the first one it finds.

## Tests

- New `Owen_RandomPairs` in `tests/base/state_spaces.cpp`: 2000 fixed-seed pairs in [-10,10]^3. For each pair it checks that a path is found (allowed to fail only within 4 turn radii), that the path ends at the goal, that `r ≥ rho`, and that `length()` and `distance()` match a reference computed without root finding: the Dubins length if it's low altitude, otherwise `|dz| / sin(maxPitch)`, which is a lower bound for any pitch-limited path and is reached exactly at max pitch. With the old code 39 of the 2000 pairs fail and the test fails. With this change it passes.
- `ctest -R "test_state_spaces|test_state_operations|test_directed_specs"` passes.

The benchmark harness and brute-force reference are standalone (`owen_bench.cpp`). I can add them under `tests/` or `demos/` if that's useful.

## Coordination with #1470

#1470 (asymmetric climb rates) rewrites the same block of `getPath()`, so the two will conflict textually. In this version the pitch only enters the medium/high code through `horizontalLength = |dz| / tanMaxPitch_` and the high altitude condition. After rebasing onto #1470, both just become `tanPitch`. I did that rebase locally and it compiles. I'm happy to rebase whichever of the two PRs lands second.
