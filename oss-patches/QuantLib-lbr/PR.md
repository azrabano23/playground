**Title:** Add Jäckel's "Let's Be Rational" Black implied standard deviation

Follows up on #ISSUE (please replace with the issue number).

This adds `blackFormulaImpliedStdDevLetsBeRational`, which implements P. Jäckel, "Let's Be Rational", Wilmott (2015), pp. 40–53. It does for the Black formula what `bachelierBlackFormulaImpliedVol` (#2028) does for Bachelier: it returns the implied total standard deviation to (close to) machine precision for any admissible price, with at most two third-order Householder steps from a rational initial guess.

```cpp
Real blackFormulaImpliedStdDevLetsBeRational(Option::Type optionType, Real strike, Real forward,
                                             Real blackPrice, Real discount = 1.0,
                                             Real displacement = 0.0);
// plus the PlainVanillaPayoff overload
```

`blackFormulaImpliedStdDev` is unchanged.

### What's in it

- `ql/pricingengines/letsberational.{hpp,cpp}` (new, `QuantLib::detail`): the normalised Black function with the four evaluation branches of the reference implementation (asymptotic expansion, small-t expansion, direct formula, erfcx), normalised vega, the rational-cubic initial guess on four segments, and the safeguarded Householder(3) iteration.
- `blackformula.{hpp,cpp}`: the public function. Input checks and displacement handling follow the neighbouring functions. It returns 0 at the intrinsic value and throws below intrinsic, at or above the upper bound (forward for calls, strike for puts), and when `strike + displacement` is 0 (the price then doesn't depend on the volatility).
- The new files are registered in CMake, Autotools (including `all.hpp`) and `QuantLib.vcxproj{,.filters}`.
- Six new test cases in `test-suite/blackformula.cpp`:
  - the normalised Black function against 50-digit values in each branch;
  - a round trip on 23 log-moneyness values (|x| up to 30) × 13 standard deviations (1e-8 to 5) × call/put, with tolerance `32·ε·cond`, where `cond = price/(stdDev·vega)` is the conditioning of the inversion;
  - displaced (negative-rate) cases;
  - edge cases: at and below intrinsic, at and near the upper bound, deep OTM, tiny std devs, invalid inputs;
  - a check that the result moves with price, discount, strike, forward and displacement and agrees with put-call parity;
  - a comparison showing it is at least as accurate as `blackFormulaImpliedStdDev` wherever the latter converges.

### Differences from the reference implementation

- The inverse normal CDF in the initial guess is QuantLib's `InverseCumulativeNormal` instead of AS241. It only affects the guess, and two iterations still suffice everywhere I tried.
- `log1p((F−K)/K)` is used for the log-moneyness when F and K are within a factor of two. `log(F/K)` loses relative accuracy there, which gives relative errors of ~1e-11 for near-ATM options with tiny std devs (there's a test for it).
- The 17th-order asymptotic series is written as a loop over its binomial coefficients instead of a single 2,000-character expression. I checked that it is the same polynomial (with exact rational arithmetic) and that the results are bitwise identical on 200k random inputs.
- The three copies of the safeguarded iteration loop are one template, with the three objective functions as lambdas.
- Error signalling uses `QL_REQUIRE` instead of sentinel return values.

### Accuracy and speed

Standalone benchmark, not part of the PR. The grid has 1326 cases: x = ln(F/K) ∈ {0, ±1e-6, …, ±30} × σ√T ∈ {1e-8, …, 5} × call/put, F = 100. Prices were computed with mpmath at 50 digits and rounded to double. The reference std dev is the exact root for the *rounded* price. 621 prices are representable, i.e. they don't underflow and don't round onto intrinsic or the upper bound. Relative error in the std dev:

| 570 well-conditioned cases (cond ≤ 1e3) | fail | median | max | err > 1e-6 |
|---|---|---|---|---|
| `blackFormulaImpliedStdDevLetsBeRational` | 0 | 1.5e-16 | 3.5e-14 | 0 |
| `blackFormulaImpliedStdDev` (default accuracy) | 0 | 4.6e-8 | 1.0 | 149 |
| `blackFormulaImpliedStdDev` (accuracy 1e-12) | 0 | 1.2e-13 | 1.0 | 49 |
| `blackFormulaImpliedStdDevLiRS` (default) | 84 | 6.0e-9 | 2.2e-2 | 83 |

The existing function's max error of 1.0 isn't a bug. Its tolerance is on the price, so it returns 0 for OTM options priced below 1e-6 (or 1e-12). On the 51 ill-conditioned cases (deep ITM, where the time value is a few ulps of the price), no double-precision method can do better than roughly ε·cond. There the new function stays within that bound except for 5 cases whose time value is within `close_enough` of intrinsic, where it returns 0 (the same policy as the Bachelier function).

Timing, g++ -O2, on the 536 cases where all four return a value: LBR 730 ns/call, NewtonSafe 2100 (3600 at 1e-12), LiRS 990. The machine was busy while I measured, so treat these as ratios rather than absolute numbers. 611 of the 621 inversions took exactly two Householder steps and the other 10 took one.

### License note

`letsberational.cpp` is a port of Jäckel's reference implementation (revision 990, the code published with the paper). It keeps his notice verbatim, as the notice requires:

> Copyright © 2013-2014 Peter Jäckel. Permission to use, copy, modify, and distribute this software is freely granted, provided that this notice is preserved. [warranty disclaimer]

The complementary error functions are a port of W. J. Cody's CALERF from netlib specfun, which the reference also uses. Please let me know if you'd rather handle the attribution differently.
