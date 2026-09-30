I'd like to take a look at this one, if nobody else is on it.

I reproduced it with random state pairs (turn radius 1, max pitch 30°). The failure rate depends a lot on the workspace size and pitch: I get about 1% in [-10,10]^3, 6% in [-100,100]^3, and 17% in [-100,100]^3 with a 15° max pitch, so the 25% you're seeing is plausible for your setup. There seem to be two separate problems:

1. **Tolerance mismatch (high altitude).** `bracket_and_solve_root` stops once the bracket is 2^-19 wide (relative), but the result is then checked against an absolute residual of 1e-5 at the bracket midpoint. With a few helix turns `radiusFun` is steep enough that the midpoint fails the check even though the root is inside the bracket. For larger workspaces this causes almost all of the failures.
2. **Discontinuities (medium and high altitude).** This is the one the code comment mentions. The root finding runs on the length of the *shortest* Dubins path, which jumps when the optimal word changes or a word stops existing (e.g. RSL/LSR once the circles overlap), so the solver can converge onto a jump. In the medium altitude case the `phi < 0` retry also never succeeds.

What I'm planning:

- Solve per Dubins word. For a fixed word the length is continuous in `r` (or `phi`), except where a turn angle wraps around 2π or the word stops existing. I'd sample the search interval coarsely, refine the first sign change with TOMS 748, and only accept a bracket whose residual is actually small, so jumps get skipped.
- Use a tight solver tolerance and return the end of the bracket that doesn't exceed the max pitch.
- In the high altitude case, bound `r` by `|dz| / (tan(pitch) * 2πk)`, and also try `k-1` for the case where a turn angle wraps around.
- Keep the low altitude case and the public API as they are. The only addition is a `DubinsStateSpace::getPath(s1, s2, radius, pathType)` overload for a single word.
- Add a regression test with a fixed seed, and check the results against a brute-force scan over `r`/`phi`/`k`.

One thing I found while doing this: for some pairs where start and goal are less than about 4 turn radii apart horizontally, there is no path of Owen et al.'s form at all, so those will still return `nullopt`. I'll include the numbers.

I'll also keep the change easy to rebase onto #1470. After that PR, the pitch only enters through `horizontalLength = |dz| / tanPitch`.
