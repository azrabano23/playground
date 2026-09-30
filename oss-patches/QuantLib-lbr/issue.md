**Title:** Add Jäckel's "Let's Be Rational" implied volatility for the Black formula?

Hi,

QuantLib already uses Jäckel's work for the Bachelier model: `bachelierBlackFormulaImpliedVol` implements "Implied Normal Volatility" (2017), added in #2028. For the Black formula there is no equivalent. We have `blackFormulaImpliedStdDev` (NewtonSafe from an approximate guess, with the tolerance in price terms), plus Li's SOR method (`blackFormulaImpliedStdDevLiRS`) and the Chambers and Radoičić–Stefanica approximations.

Jäckel's "Let's Be Rational" (Wilmott, 2015, pp. 40–53, https://doi.org/10.1002/wilm.10395) is the usual reference method for this problem. It normalises the Black function, builds an initial guess from four rational-cubic branches, and then takes at most two third-order Householder steps. That gets the implied volatility to close to machine precision for any input, including deep out-of-the-money options, very small or very large total variance, and prices close to the bounds. The existing solvers either stop at a price tolerance, which can mean a large volatility error when vega is small, or fail to converge in those regions.

I'd like to contribute a port of it. Here is what I have in mind:

- a new free function next to the others in `blackformula.hpp`:
  ```cpp
  Real blackFormulaImpliedStdDevLetsBeRational(Option::Type optionType, Real strike, Real forward,
                                               Real blackPrice, Real discount = 1.0,
                                               Real displacement = 0.0);
  ```
  (plus the `PlainVanillaPayoff` overload), with the same input checks and displacement handling as the existing functions. It would throw for prices below intrinsic or not below the upper bound, and return 0 at intrinsic;
- the numerical kernel (normalised Black function with its asymptotic, small-t and erfcx branches, the rational-cubic guess, the Householder iteration) in a separate `ql/pricingengines/letsberational.{hpp,cpp}` under `QuantLib::detail`;
- tests in `test-suite/blackformula.cpp`, and the new files registered in CMake, Autotools and the VS projects.

Two questions before I open a PR:

1. **New function or new default?** I planned to leave `blackFormulaImpliedStdDev` alone and add a separate function, since changing the default would change results everywhere it's used (smile sections, optionlet stripping, implied std-dev quotes, etc.). If you'd rather make it the default eventually, or reach it through `blackFormulaImpliedStdDev` with an extra argument, I can do it that way.
2. **Licensing.** The kernel is a port of Jäckel's reference implementation, which says: *"Permission to use, copy, modify, and distribute this software is freely granted, provided that this notice is preserved."* I would keep that notice at the top of the ported file. The complementary error function is W. J. Cody's CALERF from netlib specfun, which the reference implementation also uses. Is that OK with you, or would you prefer a clean-room implementation from the paper?

Thanks!
