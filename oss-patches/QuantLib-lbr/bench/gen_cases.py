#!/usr/bin/env python3
"""Generate benchmark cases for Black implied-volatility solvers.

For each (option type, log-moneyness x, total std dev s) on the grid, with
forward F = 100 and discount 1:
  * K = F * exp(-x) is rounded to a double, and the Black price of that exact
    double strike is computed with mpmath at 50 significant digits;
  * the price is rounded to a double (this is what a solver sees);
  * the reference std dev is the exact (50-digit) root of
    Black(F, K, sigma) = rounded price, found by Newton iteration from s.
So the reference already accounts for the rounding of the input price, and
the relative error of a solver is measured against the true answer for the
input it actually received.

Cases whose rounded price is not usable (0, i.e. underflow; not above the
intrinsic value; not below the upper bound) are written with status 'skip'.

Output: cases.csv with hex-encoded doubles.
"""
import csv
import sys
from mpmath import mp, mpf, ncdf, npdf, log, sqrt

mp.dps = 60  # 50 significant digits plus guard digits for cancellation

F = 100.0
xs_pos = [1e-6, 1e-4, 1e-3, 1e-2, 0.05, 0.1, 0.2, 0.5, 1, 1.5, 2, 3, 5, 7.5, 10, 15, 20, 25, 30]
XS = sorted([-x for x in xs_pos] + [0.0] + xs_pos)
SS = [1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 3e-3, 0.01, 0.03, 0.1, 0.2, 0.3, 0.5, 1, 2, 3, 5]


def black(theta, f, k, s):
    d1 = log(f / k) / s + s / 2
    d2 = d1 - s
    return theta * (f * ncdf(theta * d1) - k * ncdf(theta * d2))


def vega(f, k, s):
    d1 = log(f / k) / s + s / 2
    return f * npdf(d1)


def implied(theta, f, k, p, s0):
    """Exact root of Black(sigma) = p: safeguarded Newton on the log of the
    out-of-the-money price, which is well behaved even for tiny prices."""
    intrinsic = max(theta * (f - k), 0)
    tv = p - intrinsic                     # exact in 50 digits
    otm = -theta if theta * (f - k) > 0 else theta   # out-of-the-money type
    g = lambda s: log(black(otm, f, k, s)) - log(tv)
    lo, hi = mpf(0), mpf(s0)
    while g(hi) < 0:
        lo, hi = hi, hi * 2
    s = mpf(s0) if lo < s0 <= hi else (lo + hi) / 2
    for _ in range(400):
        gs = g(s)
        if gs > 0:
            hi = s
        else:
            lo = s
        step = gs * black(otm, f, k, s) / vega(f, k, s)
        sn = s - step
        if not (lo < sn < hi):
            sn = (lo + hi) / 2
        if abs(sn - s) < s * mpf(10) ** (-30):
            return sn
        s = sn
    raise RuntimeError("no convergence for %s %s %s" % (theta, k, p))


def main(out):
    import math
    rows = []
    for theta, name in ((1, "call"), (-1, "put")):
        for x in XS:
            k = F * math.exp(-x)          # a double
            fm, km = mpf(F), mpf(k)
            for s in SS:
                pm = black(theta, fm, km, mpf(s))
                p = float(pm)             # rounded to nearest double
                intrinsic = max(theta * (F - k), 0.0)
                bound = F if theta == 1 else k
                if p <= 0.0 or p <= intrinsic or p >= bound:
                    rows.append([name, x, s, F.hex(), k.hex(), p.hex(), "nan", "skip"])
                    continue
                ref = implied(theta, fm, km, mpf(p), s)
                # conditioning of the inversion: relative price error ->
                # relative std-dev error
                cond = max(1.0, float(mpf(p) / (ref * vega(fm, km, ref))))
                rows.append([name, x, s, F.hex(), k.hex(), p.hex(), float(ref).hex(), "ok", cond])
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["type", "x", "s", "forward", "strike", "price", "ref_stddev", "status", "cond"])
        w.writerows(rows)
    print("wrote", len(rows), "cases,", sum(r[7] == "ok" for r in rows), "usable")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cases.csv")
