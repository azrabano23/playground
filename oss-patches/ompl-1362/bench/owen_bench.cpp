// Benchmark / reproduction harness for ompl/ompl#1362
// (OwenStateSpace fails to find a path for ~25% of random state pairs).
//
// Usage: owen_bench [numPairs=100000] [numRefPairs=10000] [boundsHalfWidth=10] [seed=1] [maxPitch=pi/6]
//                   [turnRadius=1]
//
// For numPairs random state pairs (uniform over the bounds, fixed seed) it counts
// how often OwenStateSpace::getPath() returns no path (or throws), checks that each
// returned path actually ends at the goal and respects the turn-radius / pitch limits,
// and times distance() and interpolate().
//
// For the first numRefPairs pairs it also computes a brute-force reference length
// that does not use any root finding: the Dubins word lengths are re-implemented
// here, and the turn radius r (and the number of helix loops k, or the extra turn phi
// in the medium-altitude case) is scanned on a dense grid.
//
// Key fact used by the reference: if |dz| exceeds what the shortest 2D Dubins path at
// the minimum turn radius can climb at max pitch, every feasible path must have
// horizontal length >= |dz|/tan(maxPitch), so the optimum is exactly |dz|/sin(maxPitch)
// *if* some path with that horizontal length exists. The brute force checks existence.

#include <ompl/base/spaces/OwenStateSpace.h>
#include <ompl/base/ScopedState.h>
#include <ompl/util/RandomNumbers.h>
#include <ompl/util/Console.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <limits>
#include <map>
#include <string>
#include <vector>

namespace ob = ompl::base;

namespace
{
    constexpr double PI = 3.14159265358979323846;
    constexpr double TWOPI = 2. * PI;
    constexpr double INF = std::numeric_limits<double>::infinity();

    double mod2pi(double x)
    {
        x = std::fmod(x, TWOPI);
        return x < 0 ? x + TWOPI : x;
    }

    // Normalized (radius 1) length of Dubins word w = 0..5 (LSL, RSR, RSL, LSR, RLR, LRL),
    // INF if the word does not exist. Standard closed forms (Shkel & Lumelsky 2001).
    double wordLength(int w, double d, double a, double b)
    {
        double ca = std::cos(a), sa = std::sin(a), cb = std::cos(b), sb = std::sin(b);
        switch (w)
        {
            case 0:  // LSL
            {
                double p2 = 2. + d * d - 2. * (ca * cb + sa * sb - d * (sa - sb));
                if (p2 < 0)
                    return INF;
                double th = std::atan2(cb - ca, d + sa - sb);
                return mod2pi(-a + th) + std::sqrt(p2) + mod2pi(b - th);
            }
            case 1:  // RSR
            {
                double p2 = 2. + d * d - 2. * (ca * cb + sa * sb - d * (sb - sa));
                if (p2 < 0)
                    return INF;
                double th = std::atan2(ca - cb, d - sa + sb);
                return mod2pi(a - th) + std::sqrt(p2) + mod2pi(-b + th);
            }
            case 2:  // RSL
            {
                double p2 = d * d - 2. + 2. * (ca * cb + sa * sb - d * (sa + sb));
                if (p2 < 0)
                    return INF;
                double p = std::sqrt(p2);
                double th = std::atan2(ca + cb, d - sa - sb) - std::atan2(2., p);
                return mod2pi(a - th) + p + mod2pi(b - th);
            }
            case 3:  // LSR
            {
                double p2 = -2. + d * d + 2. * (ca * cb + sa * sb + d * (sa + sb));
                if (p2 < 0)
                    return INF;
                double p = std::sqrt(p2);
                double th = std::atan2(-ca - cb, d + sa + sb) - std::atan2(-2., p);
                return mod2pi(-a + th) + p + mod2pi(-b + th);
            }
            case 4:  // RLR
            {
                double tmp = .125 * (6. - d * d + 2. * (ca * cb + sa * sb + d * (sa - sb)));
                if (std::abs(tmp) >= 1.)
                    return INF;
                double p = TWOPI - std::acos(tmp);
                double th = std::atan2(ca - cb, d - sa + sb);
                double t = mod2pi(a - th + .5 * p);
                double q = mod2pi(a - b - t + p);
                return t + p + q;
            }
            default:  // LRL
            {
                double tmp = .125 * (6. - d * d + 2. * (ca * cb + sa * sb - d * (sa - sb)));
                if (std::abs(tmp) >= 1.)
                    return INF;
                double p = TWOPI - std::acos(tmp);
                double th = std::atan2(-ca + cb, d + sa - sb);
                double t = mod2pi(-a + th + .5 * p);
                double q = mod2pi(b - a - t + p);
                return t + p + q;
            }
        }
    }

    struct SE2
    {
        double x, y, yaw;
    };

    // Horizontal (metric) length of word w at radius r, INF if it does not exist.
    double wordLengthAt(int w, const SE2 &s1, const SE2 &s2, double r)
    {
        double dx = s2.x - s1.x, dy = s2.y - s1.y, d = std::hypot(dx, dy) / r, th = std::atan2(dy, dx);
        if (d < 1e-6 && std::abs(mod2pi(s1.yaw - s2.yaw)) < 1e-6)
            return 0.;
        return r * wordLength(w, d, mod2pi(s1.yaw - th), mod2pi(s2.yaw - th));
    }

    double dubinsMin(const SE2 &s1, const SE2 &s2, double r)
    {
        double m = INF;
        for (int w = 0; w < 6; ++w)
            m = std::min(m, wordLengthAt(w, s1, s2, r));
        return m;
    }

    // Find a sign change of a function that may have jumps; accept only brackets across
    // which f is continuous (verified by bisection shrinking the jump). Returns true if a
    // genuine root was found in [a, b].
    template <typename F>
    bool genuineRoot(F f, double a, double b, double fa, double fb, double tol)
    {
        for (int i = 0; i < 80; ++i)
        {
            double m = .5 * (a + b), fm = f(m);
            if (!std::isfinite(fm))
                return false;
            if ((fa <= 0) == (fm <= 0))
                a = m, fa = fm;
            else
                b = m, fb = fm;
        }
        return std::min(std::abs(fa), std::abs(fb)) < tol;
    }

    enum class RefKind
    {
        LOW,
        MEDIUM,
        HIGH,
        INFEASIBLE
    };

    struct Ref
    {
        RefKind kind;
        double length;
    };

    // Brute-force reference. No root finder, just dense scans.
    Ref bruteForce(const SE2 &s1, const SE2 &s2, double dz, double rho, double tanP)
    {
        double len0 = dubinsMin(s1, s2, rho);
        double adz = std::abs(dz);
        if (adz <= len0 * tanP)
            return {RefKind::LOW, std::hypot(len0, dz)};
        const double H = adz / tanP;  // required horizontal length
        const double optimum = std::hypot(H, dz);
        const double tol = 1e-6 * std::max(1., H);

        if (adz <= (len0 + TWOPI * rho) * tanP)
        {
            // Medium altitude: extra turn phi at radius rho, then a Dubins path at rho.
            auto h = [&](double phi)
            {
                double ang = s1.yaw + phi, rr = phi > 0 ? rho : -rho;
                SE2 zi{s1.x + rr * (std::sin(ang) - std::sin(s1.yaw)), s1.y + rr * (-std::cos(ang) + std::cos(s1.yaw)),
                       ang};
                return std::abs(phi) * rho + dubinsMin(zi, s2, rho) - H;
            };
            const int N = 4000;
            for (int sgn : {1, -1})
            {
                double pa = 0., fa = h(0.);
                for (int i = 1; i <= N; ++i)
                {
                    double pb = sgn * TWOPI * i / N, fb = h(pb);
                    if ((fa <= 0) != (fb <= 0) && genuineRoot(h, pa, pb, fa, fb, tol))
                        return {RefKind::MEDIUM, optimum};
                    pa = pb, fa = fb;
                }
            }
            // fall through: also try the high-altitude family
        }

        // High altitude: k full helix loops + Dubins word w at radius r >= rho.
        const int J = (int)std::floor(H / (TWOPI * rho));
        const int N = 3000;
        const double rMax = std::max(1000. * rho, 10. * H);
        for (int j = J; j >= 0; --j)
            for (int w = 0; w < 6; ++w)
            {
                auto g = [&](double r) { return wordLengthAt(w, s1, s2, r) + TWOPI * j * r - H; };
                double ra = rho, fa = g(ra);
                for (int i = 1; i <= N; ++i)
                {
                    double rb = rho * std::pow(rMax / rho, double(i) / N), fb = g(rb);
                    if (std::isfinite(fa) && std::isfinite(fb) && (fa <= 0) != (fb <= 0) &&
                        genuineRoot(g, ra, rb, fa, fb, tol))
                        return {RefKind::HIGH, optimum};
                    ra = rb, fa = fb;
                }
            }
        return {RefKind::INFEASIBLE, INF};
    }

    SE2 toSE2(const ob::OwenStateSpace::StateType *s)
    {
        return {(*s)[0], (*s)[1], s->yaw()};
    }

    double percentile(std::vector<double> v, double p)
    {
        if (v.empty())
            return NAN;
        std::sort(v.begin(), v.end());
        return v[std::min(v.size() - 1, (size_t)(p * (v.size() - 1) + .5))];
    }
}  // namespace

int main(int argc, char **argv)
{
    int numPairs = argc > 1 ? std::stoi(argv[1]) : 100000;
    int numRef = argc > 2 ? std::stoi(argv[2]) : 10000;
    double half = argc > 3 ? std::stod(argv[3]) : 10.;
    unsigned seed = argc > 4 ? std::stoul(argv[4]) : 1u;

    ompl::msg::setLogLevel(ompl::msg::LOG_NONE);
    ompl::RNG::setSeed(seed);

    const double maxPitch = argc > 5 ? std::stod(argv[5]) : PI / 6.;
    const double rho = argc > 6 ? std::stod(argv[6]) : 1.;
    auto space = std::make_shared<ob::OwenStateSpace>(rho, maxPitch);
    ob::RealVectorBounds bounds(3);
    bounds.setLow(-half);
    bounds.setHigh(half);
    space->setBounds(bounds);
    space->setup();
    const double tanP = std::tan(maxPitch);

    auto sampler = space->allocDefaultStateSampler();
    std::vector<ob::State *> from(numPairs), to(numPairs);
    for (int i = 0; i < numPairs; ++i)
    {
        from[i] = space->allocState();
        to[i] = space->allocState();
        sampler->sampleUniform(from[i]);
        sampler->sampleUniform(to[i]);
    }

    // --- correctness sweep --------------------------------------------------------
    int fails = 0, throws = 0, badEndpoint = 0, badConstraint = 0;
    std::map<char, int> catCount, catFail;
    double maxEndErr = 0.;
    ob::State *tmp = space->allocState();
    for (int i = 0; i < numPairs; ++i)
    {
        auto *s1 = from[i]->as<ob::OwenStateSpace::StateType>();
        auto *s2 = to[i]->as<ob::OwenStateSpace::StateType>();
        double dz = (*s2)[2] - (*s1)[2];
        double len0 = dubinsMin(toSE2(s1), toSE2(s2), rho);
        // category the input *should* fall in (same thresholds as OwenStateSpace)
        char cat = std::abs(dz) <= len0 * tanP ? 'L' : (std::abs(dz) <= (len0 + TWOPI * rho) * tanP ? 'M' : 'H');
        catCount[cat]++;
        std::optional<ob::OwenStateSpace::PathType> path;
        try
        {
            path = space->getPath(from[i], to[i]);
        }
        catch (...)
        {
            ++throws;
            ++fails;
            catFail[cat]++;
            continue;
        }
        if (!path)
        {
            ++fails;
            catFail[cat]++;
            continue;
        }
        // Does the returned path really end at the goal?
        space->interpolate(from[i], to[i], 1. - 1e-12, *path, tmp);
        auto *e = tmp->as<ob::OwenStateSpace::StateType>();
        double err = std::hypot(std::hypot((*e)[0] - (*s2)[0], (*e)[1] - (*s2)[1]), (*e)[2] - (*s2)[2]) +
                     std::abs(std::remainder(e->yaw() - s2->yaw(), TWOPI));
        maxEndErr = std::max(maxEndErr, err);
        if (err > 1e-5)
            ++badEndpoint;
        // turn radius and pitch limits
        double hlen = path->turnRadius_ * (path->path_.length() + TWOPI * path->numTurns_ + std::abs(path->phi_));
        if (path->turnRadius_ < rho * (1 - 1e-9) || std::abs(dz) > hlen * tanP * (1 + 1e-6) + 1e-9)
            ++badConstraint;
    }

    std::printf("pairs=%d bounds=[-%g,%g]^3 rho=%g maxPitch=%g seed=%u\n", numPairs, half, half, rho, maxPitch,
                seed);
    std::printf("failures (no path or exception): %d  (%.3f%%), exceptions: %d\n", fails, 100. * fails / numPairs,
                throws);
    for (auto &c : catCount)
        std::printf("  category %c: %6d pairs, %6d failures (%.2f%%)\n", c.first, c.second, catFail[c.first],
                    100. * catFail[c.first] / c.second);
    std::printf("returned paths with endpoint error > 1e-5: %d (max error %.3g)\n", badEndpoint, maxEndErr);
    std::printf("returned paths violating radius/pitch limits: %d\n", badConstraint);

    // --- gap vs brute-force reference -------------------------------------------
    int nRef = std::min(numRef, numPairs), refInfeasible = 0, refNonLow = 0;
    std::vector<double> gaps, gapsNonLow;
    for (int i = 0; i < nRef; ++i)
    {
        auto *s1 = from[i]->as<ob::OwenStateSpace::StateType>();
        auto *s2 = to[i]->as<ob::OwenStateSpace::StateType>();
        double dz = (*s2)[2] - (*s1)[2];
        Ref ref = bruteForce(toSE2(s1), toSE2(s2), dz, rho, tanP);
        if (ref.kind == RefKind::INFEASIBLE)
        {
            ++refInfeasible;
            continue;
        }
        double d;
        try
        {
            d = space->distance(from[i], to[i]);
        }
        catch (...)
        {
            d = space->getMaximumExtent();
        }
        double gap = std::abs(d - ref.length) / ref.length;
        gaps.push_back(gap);
        if (ref.kind != RefKind::LOW)
        {
            ++refNonLow;
            gapsNonLow.push_back(gap);
        }
    }
    std::printf("reference: %d pairs (%d non-low-altitude, %d with no feasible path found by brute force)\n", nRef,
                refNonLow, refInfeasible);
    std::printf("relative gap |distance - ref|/ref, all:      max %.3g  median %.3g  p99 %.3g  >1e-6: %ld\n",
                percentile(gaps, 1.), percentile(gaps, .5), percentile(gaps, .99),
                (long)std::count_if(gaps.begin(), gaps.end(), [](double g) { return g > 1e-6; }));
    std::printf("relative gap |distance - ref|/ref, non-low:  max %.3g  median %.3g  p99 %.3g  >1e-6: %ld\n",
                percentile(gapsNonLow, 1.), percentile(gapsNonLow, .5), percentile(gapsNonLow, .99),
                (long)std::count_if(gapsNonLow.begin(), gapsNonLow.end(), [](double g) { return g > 1e-6; }));

    // --- timing ---------------------------------------------------------------------
    using clk = std::chrono::steady_clock;
    volatile double sink = 0.;
    auto t0 = clk::now();
    for (int i = 0; i < numPairs; ++i)
        try
        {
            sink = sink + space->distance(from[i], to[i]);
        }
        catch (...)
        {
        }
    auto t1 = clk::now();
    for (int i = 0; i < numPairs; ++i)
        try
        {
            space->interpolate(from[i], to[i], .5, tmp);
        }
        catch (...)
        {
        }
    auto t2 = clk::now();
    std::printf("distance():    %.2f us/call\n", std::chrono::duration<double, std::micro>(t1 - t0).count() / numPairs);
    std::printf("interpolate(): %.2f us/call\n", std::chrono::duration<double, std::micro>(t2 - t1).count() / numPairs);

    space->freeState(tmp);
    for (int i = 0; i < numPairs; ++i)
    {
        space->freeState(from[i]);
        space->freeState(to[i]);
    }
    return 0;
}
