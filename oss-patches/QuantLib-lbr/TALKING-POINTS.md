# Let's Be Rational in QuantLib: study guide

These notes are for you to prepare with. Read them next to the code
(`ql/pricingengines/letsberational.cpp` and the new function at the end of the
implied-vol section of `ql/pricingengines/blackformula.cpp`). If a line in the
code doesn't make sense to you after reading this, stop and work it out before
you post anything.

---

## 1. The problem in one paragraph

Given a Black (lognormal) option price, find the total standard deviation
`s = σ√T` that reproduces it. The Black price is monotonic in `s`, so a root
always exists between intrinsic value and the upper bound (forward for calls,
strike for puts). The difficulty is numerical. Deep out of the money, the price
is exponentially small (1e-200 is a legitimate input) and vega is tiny.
Near the upper bound, all the information sits in the last few digits. The
formula `F·Φ(d1) − K·Φ(d2)` also subtracts two nearly equal numbers. Newton
on the price with a price tolerance (`blackFormulaImpliedStdDev`) stops as
soon as the *price* is within 1e-6, which can leave the *volatility* off by
100%. Section 6 shows this happening.

## 2. The math

### 2.1 Normalisation: two variables instead of five

Divide the undiscounted price by `√(FK)` and write `x = ln(F/K)`:

    b(x, s) = e^{x/2} Φ(x/s + s/2) − e^{−x/2} Φ(x/s − s/2)

Discount, forward and strike are gone. What remains is log-moneyness `x`
and total std dev `s`. Two symmetries cut the problem down further:

* **Put → call:** `b_put(x, s) = b_call(−x, s)`.
* **In the money → out of the money:** the ITM price is the intrinsic value
  plus the OTM price (put-call parity). So subtract intrinsic, flip the
  option type, and you have an OTM call with `x ≤ 0`.

After that the only problem is: OTM call, `x ≤ 0`, `0 < β < b_max = e^{x/2}`.

In the code I remove intrinsic **in price space** (`price − (F − K)`) in
the public function rather than on the normalised price. `F − K` is exact
when F and K are within a factor of 2 (Sterbenz lemma). The normalised
intrinsic `e^{x/2} − e^{−x/2}` cancels badly for small `|x|`. The kernel
still has a Taylor series for that case (`normalisedIntrinsic`) for callers
that use it directly.

### 2.2 The shape of `b(s)` and the four regions

Normalised vega is `b'(s) = exp(−½(x²/s² + s²/4)) / √(2π)`. Differentiating
its log:

    b''/b'  = x²/s³ − s/4
    b'''/b' = (b''/b')² − 3x²/s⁴ − 1/4

So `b''` is zero at `s_c = √(2|x|)`. That is the **inflection point**: `b`
is convex below `s_c` and concave above, and vega is largest there. Draw the
tangent at `s_c`:

* it hits `b = 0` at `s_l = s_c − b_c/v_c`
* it hits `b = b_max` at `s_h = s_c + (b_max − b_c)/v_c`

That gives four ranges of the target price β:

| region | β range | how the guess is built |
|---|---|---|
| lowest | `(0, b_l)` | rational cubic in the transformed variable `f_lower(β)`, then closed-form inversion |
| lower middle | `[b_l, b_c)` | rational cubic directly on `s(β)` |
| upper middle | `[b_c, b_h]` | rational cubic directly on `s(β)` |
| highest | `(b_h, b_max)` | rational cubic in `f_upper(β)`, then closed-form inversion |

**Why four and not one?** The inverse function `s(β)` behaves differently
at each end.

* In the middle it is smooth. Between the known points `(b_l, s_l)`,
  `(b_c, s_c)`, `(b_h, s_h)`, whose slopes `ds/dβ = 1/vega` we also know,
  interpolation is accurate. The inflection point splits it into a convex
  piece and a concave piece. A shape-preserving interpolant needs to know
  which is which, so there are two middle regions.
* As `β → 0`, `ln β ≈ −x²/(2s²)`, so `s ≈ |x|/√(−2 ln β)`. That function
  has an essential singularity at 0 and no polynomial or rational function
  fits it. The fix is to change variables to
  `f_lower = (2π|x|/√27)·Φ(−|x|/(√3·s))³`. Because `Φ(−z)³ ~ e^{−3z²/2}`
  and `z = |x|/(√3 s)`, this decays like `e^{−x²/(2s²)}`, the same as `b`.
  So `f_lower(β)` is close to linear near 0 (`f(0) = 0`, `f'(0) = 1`),
  which interpolates well, and it inverts in closed form:
  `s = |x| / (√3·Φ⁻¹((f/(2π|x|/√27))^{1/3}))`.
* As `β → b_max`, `s → ∞`. At `x = 0` exactly, `b = 1 − 2Φ(−s/2)`, so
  `f_upper = Φ(−s/2)` is exactly `(b_max − β)/2`, which is linear in β.
  For `x ≠ 0` it is still close to linear, with `f(b_max) = 0` and
  `f'(b_max) = −1/2`, and it inverts as `s = −2Φ⁻¹(f)`.

### 2.3 Why a *rational* cubic

Delbourgo–Gregory rational cubic interpolation between two points with
given values and slopes:

    y(t) = [y_r t³ + (r y_r − h d_r) t²(1−t) + (r y_l + h d_l) t(1−t)² + y_l (1−t)³]
           / [1 + (r − 3) t(1−t)]

`r` is a control parameter. `r = 3` gives the usual cubic Hermite, and
`r → ∞` tends to linear interpolation. It helps in two ways:

1. **Shape preservation.** There is a minimum `r` above which the
   interpolant stays monotone and convex (or concave) whenever the data are.
   That is `minimumRationalCubicControlParameterValue`, eqs. (3.8) and (3.18)
   of the paper. A plain cubic can overshoot, for example to a negative
   `f_lower`, which has no inverse.
2. **One more derivative for free.** Above that minimum, `r` is chosen so
   the interpolant also matches the **second derivative** at one end
   (`...ToFitSecondDerivativeAtLeftSide/RightSide`). We know `b''`
   analytically, so this is cheap and improves the guess.

The guess is then good enough that two iterations finish the job.

### 2.4 Householder(3): why two steps are enough

Householder's method of order *d* uses derivatives up to order *d* and
converges with order *d + 1*. For *d = 3*, with `ν = −g/g'` (the Newton
step), `h₂ = g''/g'` and `h₃ = g'''/g'`:

    s_{n+1} = s_n + ν · (1 + ½ h₂ ν) / (1 + ν (h₂ + h₃ ν / 6))

Take `h₃ = 0` and you get Halley. Take both zero and you get Newton. The
error goes as `e_{n+1} ≈ C·e_n⁴`, so a guess with relative error 1e-3 is
near 1e-12 after one step, and after the second step you are at the limit
of double precision.

**Why it's cheap here:** `b''/b'` and `b'''/b'` are the rational expressions
in `s` from 2.2. The higher order costs a few multiplications and no extra
evaluations of Φ. That is the design idea of the paper: pay a little more
per step, take fewer steps.

**Objective functions.** The iteration does not always solve `b(s) = β`
directly:

* lowest region: `g = 1/ln b(s) − 1/ln β`. Since `ln b ≈ −x²/(2s²)`,
  `1/ln b` is close to `−2s²/x²`, a low-degree polynomial. Newton-type steps
  behave well on it even when `b` spans hundreds of orders of magnitude.
* highest region (when `β > b_max/2`): `g = ln(b_max − β) − ln(b_max − b(s))`.
  It works with the small distance to the upper bound, where the
  information is.
* middle regions: `g = b(s) − β`.

The derivative formulas for each `g` are in comments above each lambda in
the code. Be ready to derive the middle one on a whiteboard, since it is the
simplest.

In the benchmark, 611 of the 621 cases took exactly 2 iterations and 10 took
1. The test `testLetsBeRationalRoundTrip` checks that allowing more
iterations never changes the answer by more than 64 ulps.

## 3. Evaluating `b(x, s)` accurately

A solver can't beat the accuracy of the function it inverts, so this part
matters as much as the iteration. With `h = x/s` and `t = s/2`, the code
picks one of four formulas (`normalisedBlackCall`):

1. **Asymptotic expansion** (`h < −10` and `t` not too large). Each Φ is
   tiny. Writing `Φ(z) = φ(z)·Y(z)` and expanding `Y(h+t) − Y(h−t)` in
   `q = (h/r)²` needs one exponential and no subtraction of nearly equal
   numbers. I wrote the 17th-order series as a loop:
   `P_k(e) = (−1)^k·2·Σ_j C(2k+1, 2j+1) e^j`. The reference spells the same
   polynomial out as one 2000-character expression. I checked they are the
   same polynomial with exact rational arithmetic, and that the outputs are
   bit-for-bit identical on 200,000 random inputs.
2. **Small-t expansion** (`t < τ = 2·ε^{1/16} ≈ 0.21`). The two Φ terms are
   nearly equal, so it uses a Taylor series in `t` to 12th order. Its
   leading coefficient `a = 1 + h·Y(h)` cancels when `|h|` is large. The
   reference notes this, and it costs a few tens of ulps. The tests allow
   for it.
3. **Direct formula** (`h + t > 0.85`). The first term dominates, so there
   is no cancellation.
4. **erfcx formula** (everything else):
   `b = ½·e^{−(h²+t²)/2}·[erfcx(−(h+t)/√2) − erfcx(−(h−t)/√2)]`. This is one
   exponential instead of four, and the difference is between two rational
   functions. At the test point `(x, s) = (−4.5, 0.45)` the direct formula
   is off by about 1000 ulps and this one by about 12.

`erfcx(z) = e^{z²} erfc(z)` is not in the C++ standard library or in Boost.
I ported W. J. Cody's CALERF, as the reference does. That also makes the
results the same on every platform, instead of depending on each vendor's
`erfc`.

## 4. The numerical pitfalls, and where each is handled

| pitfall | where | how |
|---|---|---|
| cancellation in `FΦ(d1) − KΦ(d2)` | `normalisedBlackCall` | four evaluation branches (§3) |
| `log(F/K)` loses relative accuracy when F≈K | public function | `log1p((F−K)/K)` when F, K within a factor of 2 |
| overflow in `√(F·K)` | public function | `√F·√K` |
| cancellation in the intrinsic value | public function / `normalisedIntrinsic` | subtract in price space; Taylor series for small `|x|` |
| rational cubic gives `f ≤ 0` (round-off, `|x| > 500`) | lowest/highest guess | fall back to a quadratic through the same end conditions |
| second derivative of the upper map overflows | highest guess | skip the rational cubic, use the quadratic |
| step leaves the bracket, or oscillates | `householderIteration` | tighten `[s_left, s_right]` each step; bisect on exit or after 3 direction changes |
| step would make `s` negative | `householderIteration` | clamp `ds ≥ −s/2` |
| `b` or vega underflows in the lowest region | lowest objective | bisection step |
| price rounds to intrinsic | public function | return 0 if `price == intrinsic` or `close_enough` to a positive intrinsic (same policy as the Bachelier fix) |
| tiny OTM prices treated as zero | public function | **not** using `close_enough(price, 0)`, which degrades to an absolute 1e-28 tolerance |

## 5. Design decisions (and what I'd say if challenged)

* **New function, default unchanged.** `blackFormulaImpliedStdDev` is used
  by smile sections, optionlet stripping and implied-std-dev quotes. Swapping
  its algorithm would silently change numbers across the library and in
  users' regression tests. A new function is additive. The issue asks the
  maintainers which they prefer, and follows the Bachelier precedent
  (`bachelierBlackFormulaImpliedVol` sits next to the Choi approximation).
* **No `accuracy` / `maxIterations` arguments.** The method is designed to
  reach machine precision in two steps, and a tolerance would only let
  people make it worse. The kernel in `detail::` still takes
  `maxIterations` and reports the iteration count, which the tests and the
  benchmark use.
* **Separate `letsberational.{hpp,cpp}` in `QuantLib::detail`.** The ported
  code keeps its license notice in one place, `blackformula.cpp` stays
  readable, and the tests can check the normalised function directly.
  Registered in CMake, Autotools (including `all.hpp`) and both VS project
  files, as `AGENTS.md` asks.
* **Exceptions instead of sentinels.** The reference returns `±DBL_MAX` for
  "below intrinsic" or "above maximum". QuantLib style is `QL_REQUIRE`, as
  in the neighbouring functions.
* **`strike + displacement` must be > 0.** Otherwise a call is worth
  exactly the forward whatever the volatility, so there's no answer.
  `checkParameters` allows 0, so I added the check.
* **Reused QuantLib's inverse normal (Acklam)** instead of porting AS241.
  It is only used in the initial guess, and its ~1e-9 relative error
  disappears in the first Householder step. The benchmark and tests confirm
  two iterations still suffice everywhere.
* **Deviations from the reference, all deliberate:** the asymptotic series
  as a loop (verified identical); the three copies of the safeguarded loop
  merged into one template with the three objectives as lambdas; `log1p`
  for `x`; code behind the reference's `DENORMALIZATION_CUTOFF = 0`
  removed, since it is dead with that setting; and no `constexpr Real`,
  which breaks AAD builds (see the TrinomialTree commit).
* **Revision.** I ported revision 990 (Nov 2014) of Jäckel's reference
  code, the version published with the Wilmott paper. I got it from the
  copy in `github.com/vollib/lets_be_rational/src`, because jaeckel.org was
  unreachable from my environment. Jäckel has published later revisions.
  **Before posting, download the current `LetsBeRational.7z` from
  jaeckel.org, diff it against this port, and mention the result in the
  PR.**

## 6. Results (1326-point grid, mpmath 50-digit references)

Grid: `x = ln(F/K)` in {0, ±1e-6 … ±30} (39 values) × `s` in {1e-8 … 5}
(17 values) × {call, put}, F = 100. Each price is computed at 50 digits
and rounded to double. The reference vol is the exact root **for that
rounded price**, so solvers are compared with the true answer for the input
they actually got. 621 of the 1326 prices are usable. The rest underflow to
0 or round onto intrinsic or the upper bound.

Relative std-dev error on the 570 **well-conditioned** cases
(`cond = price/(s·vega) ≤ 1e3`):

| solver | failures | median | max | err > 1e-6 |
|---|---|---|---|---|
| Let's Be Rational | 0 | 1.5e-16 | 3.5e-14 | 0 |
| `blackFormulaImpliedStdDev` (default) | 0 thrown | 4.6e-8 | **1.0** | 149 |
| `blackFormulaImpliedStdDev` (acc 1e-12) | 0 thrown | 1.2e-13 | **1.0** | 49 |
| LiRS (default) | 84 thrown | 6.0e-9 | 2.2e-2 | 83 |

On OTM options only (366 cases), LBR's worst error is 2.5e-15. Its error
never exceeds 3·ε·cond on the well-conditioned set. The existing default
**returns 0 without throwing** on 57 well-conditioned cases. All of them
are OTM options priced below its 1e-6 *price* tolerance, where `s = 0`
already meets the tolerance. That isn't a bug in NewtonSafe. It is what a
price tolerance means, and it is the best argument for a solver that works
in volatility terms. Say it that way, and don't call the existing code
broken.

Speed at -O2, ns/call, on the 536 cases where every solver returns a value.
The machine was heavily loaded, so treat these as ratios (see
`bench/timing-runs.txt`), over three runs: LBR 580–820 ns, NewtonSafe
2000–2300 ns (default accuracy) and 3000–3800 ns (1e-12), LiRS 750–950 ns. So LBR is about 3× faster than the
default solver and a bit faster than LiRS, while being accurate to the last
few bits. Don't quote absolute nanoseconds as facts.

**Where LBR "loses":** 51 in-the-money cases are ill-conditioned: the time
value is a handful of ulps of the price, `cond` goes up to 1e14, and no
double-precision solver can do better than about ε·cond there. LBR stays
within 0.3·ε·cond on all of them except 5, where the time value is within
`close_enough` (42 ulps) of the price and LBR returns 0 by design (the
intrinsic snap). That shows up as "max error 1.0" in the all-cases table.
Be ready to explain this, and not to hide it.

## 7. Likely interview questions

**Q1. Explain Let's Be Rational in a minute.**
Normalise the Black price so it depends only on log-moneyness and total std
dev. Reduce to an OTM call. Split the price range into four regions using
the inflection point `√(2|x|)` and its tangent. Build an initial guess by
rational-cubic interpolation, in transformed variables in the two outer
regions where `s(β)` is singular. Then take at most two Householder(3)
steps, which converge with order four. The derivatives are closed-form, so
each step is cheap. The result is at machine precision for any input.

**Q2. Why not just Newton on the price?**
Vega vanishes in the wings, so Newton steps are huge or undefined and you
need bracketing. A price tolerance is not a vol tolerance: for a price of
1e-20, 1e-6 accuracy in price means nothing. The benchmark shows the default
QuantLib solver with vol errors above 1e-6 on 149 well-posed cases,
57 of them returning 0, without throwing.

**Q3. What does the inflection point have to do with anything?**
`b''/b' = x²/s³ − s/4` is zero at `s_c = √(2|x|)`, where vega peaks. It
separates the convex and concave parts of `b(s)`. A shape-preserving
interpolant needs one or the other on each segment, and the tangent at
`s_c` gives the natural breakpoints `s_l` and `s_h`.

**Q4. Why a rational cubic rather than a cubic spline?**
It preserves shape: with `r` above a computable minimum it never overshoots,
so the lower map stays positive and invertible. Its free parameter also
lets you match the second derivative at one end, which buys guess accuracy
at no cost.

**Q5. What are the transformations in the outer regions for?**
Near `β = 0`, `s(β) ~ |x|/√(−2 ln β)` has an essential singularity that no
rational function can follow. `f = c|x|·Φ(−|x|/(√3 s))³` decays like `b`
itself, so `f(β)` is nearly linear, interpolates well and inverts in closed
form. Near `b_max`, `Φ(−s/2)` plays the same role; it is exact when
`x = 0`.

**Q6. What's Householder(3), and is it worth it?**
Third-order Householder, convergence order 4. The correction factor is a
rational function of the Newton step and `g''/g'`, `g'''/g'`. It is worth it
here because those ratios are closed-form rational functions of `s`: no
extra Φ evaluations, a few more flops, and half the iterations of Halley.

**Q7. How did you verify it, and what's "conditioning" in your tests?**
Reference values come from mpmath at 50 digits, and the reference vol
inverts the *rounded* price exactly. A relative price error δ becomes a
relative vol error of about `δ·price/(s·vega)`. That factor is `cond`, and
no algorithm can beat `ε·cond`. The tests use a tolerance of `32·ε·cond`,
so they are strict where the problem is well-posed and don't demand the
impossible where it isn't. I also mutation-tested the tests: replacing
Householder with Newton or Halley, replacing the erfcx branch with the
direct formula, or using `log(F/K)` all make them fail.

**Q8. Why a new function instead of fixing `blackFormulaImpliedStdDev`?**
To avoid silently changing results in every component that calls it. The
issue asks the maintainers which way they want it, and I'm happy to wire it
in as an option.

**Q9. What about the license?**
Jäckel's notice allows use, modification and distribution provided the
notice is kept. It is reproduced verbatim at the top of `letsberational.cpp`,
along with a pointer to Cody's CALERF. The PR text flags this so the
maintainers can decide. I asked in the issue before opening the PR.

**Q10. What are the limitations, and what would you do next?**
(a) ITM prices within ~42 ulps of intrinsic return 0. That is a policy
choice matching the Bachelier function; the input carries almost no
information there. (b) The small-t branch loses a few tens of ulps at large
`|h|`, as in the reference. (c) This is the 2014 revision; I'd diff it
against Jäckel's current code. (d) Not yet tested under an AAD `Real`
type, although I avoided `constexpr Real` for that reason. (e) Possible
follow-ups: offer it as an option in `blackFormulaImpliedStdDev`, or use
it in `ImpliedStdDevQuote`.

**Q11. Why subtract intrinsic in price space rather than on `b`?**
`F − K` is exact when the two are within a factor of two, while
`e^{x/2} − e^{−x/2}` cancels for small `x`. Doing it before normalising
keeps every digit of the time value, and the time value is the only thing
that carries volatility information for an ITM option.

## 8. How it was built and tested (so you can reproduce it)

* Configure: `cmake .. -G Ninja -DQL_BUILD_EXAMPLES=OFF -DQL_BUILD_BENCHMARK=OFF -DCMAKE_UNITY_BUILD=ON -DCMAKE_UNITY_BUILD_BATCH_SIZE=24 -DCMAKE_CXX_FLAGS="-O0 -g0"`.
  The machine was shared and short on memory, hence `-O0` and the unity
  build. Then `ninja ql_test_suite`. The test binary is
  `test-suite/quantlib-test-suite`.
* With batch size 24, one unity batch (`models/marketmodels/callability`,
  which is unrelated to this change) fails to compile because of an existing
  `CashFlow` typedef clash. I compiled those 24 files separately for the
  local build. CI uses the default batch size, and the new file doesn't
  change the batches before `pricingengines/`. I also compiled all of
  `ql/pricingengines/*.cpp` as one translation unit in both orders (the way
  Autotools does unity builds) to check the new anonymous-namespace helpers
  don't clash.
* `./quantlib-test-suite --run_test=QuantLibTests/BlackFormulaTests`
  runs 18 cases, 6 of them new, all passing. They also pass at -O3, and the
  new code compiles without warnings under g++ and clang++ with
  `-Wall -Wextra -Wshadow`.
* Before posting, run `./autogen.sh && ./configure && ./tools/check_filelists.sh`
  if you can. I registered the files by hand in all three build systems but
  didn't run that script.
