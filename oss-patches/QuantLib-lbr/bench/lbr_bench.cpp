// Standalone accuracy/speed benchmark for Black implied std-dev solvers.
// Not part of the patch.  Build (from this directory) with e.g.
//
//   g++ -std=c++17 -O2 -I$QL -I$QL/build lbr_bench.cpp -L$QL/build/ql -lQuantLib \
//       -Wl,-rpath,$QL/build/ql -o lbr_bench
//   ./lbr_bench cases.csv > results.txt
//
// cases.csv comes from gen_cases.py (mpmath, 50 digits).

#include <ql/pricingengines/blackformula.hpp>
#include <ql/pricingengines/letsberational.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <functional>
#include <map>
#include <sstream>
#include <string>
#include <vector>

using namespace QuantLib;

struct Case {
    Option::Type type;
    double x, s, forward, strike, price, ref, cond;
    bool usable;
};

static double fromHex(const std::string& s) { return std::strtod(s.c_str(), nullptr); }

static std::vector<Case> readCases(const char* file) {
    std::ifstream in(file);
    std::string line;
    std::getline(in, line); // header
    std::vector<Case> cases;
    while (std::getline(in, line)) {
        std::vector<std::string> f;
        std::stringstream ss(line);
        std::string item;
        while (std::getline(ss, item, ','))
            f.push_back(item);
        Case c;
        c.type = f[0] == "call" ? Option::Call : Option::Put;
        c.x = std::stod(f[1]);
        c.s = std::stod(f[2]);
        c.forward = fromHex(f[3]);
        c.strike = fromHex(f[4]);
        c.price = fromHex(f[5]);
        c.usable = f[7] == "ok";
        c.ref = c.usable ? fromHex(f[6]) : 0.0;
        c.cond = c.usable ? std::stod(f[8]) : 0.0;
        cases.push_back(c);
    }
    return cases;
}

struct Solver {
    std::string name;
    std::function<Real(const Case&)> f;
};

struct Outcome {
    bool ok;
    double value;
};

static Outcome run(const Solver& s, const Case& c) {
    try {
        double v = s.f(c);
        return {std::isfinite(v), v};
    } catch (std::exception&) {
        return {false, 0.0};
    }
}

static double percentile(std::vector<double> v, double p) {
    if (v.empty())
        return NAN;
    std::sort(v.begin(), v.end());
    size_t i = std::min(v.size() - 1, size_t(p * (v.size() - 1) + 0.5));
    return v[i];
}

int main(int argc, char** argv) {
    const char* file = argc > 1 ? argv[1] : "cases.csv";
    std::vector<Case> all = readCases(file);
    std::vector<Case> cases;
    for (const auto& c : all)
        if (c.usable)
            cases.push_back(c);

    std::vector<Solver> solvers = {
        {"LetsBeRational",
         [](const Case& c) {
             return blackFormulaImpliedStdDevLetsBeRational(c.type, c.strike, c.forward, c.price);
         }},
        {"ImpliedStdDev (default, acc 1e-6)",
         [](const Case& c) {
             return blackFormulaImpliedStdDev(c.type, c.strike, c.forward, c.price);
         }},
        {"ImpliedStdDev (acc 1e-12)",
         [](const Case& c) {
             return blackFormulaImpliedStdDev(c.type, c.strike, c.forward, c.price, 1.0, 0.0,
                                              Null<Real>(), 1e-12, 100);
         }},
        {"LiRS (default, acc 1e-6)",
         [](const Case& c) {
             return blackFormulaImpliedStdDevLiRS(c.type, c.strike, c.forward, c.price);
         }},
    };

    std::printf("cases on grid: %zu, usable (price representable and inside bounds): %zu\n\n",
                all.size(), cases.size());

    // ---- accuracy ---------------------------------------------------------
    // The attainable relative accuracy of any double-precision solver is
    // about eps * cond, cond = price / (stdDev * vega). We split the cases
    // into well-conditioned (cond <= 1e3) and ill-conditioned ones; for the
    // latter only the error in units of eps * cond is meaningful.
    std::vector<std::vector<Outcome>> outcomes(solvers.size());
    std::vector<int> thrown(solvers.size(), 0);
    for (size_t i = 0; i < solvers.size(); ++i) {
        for (const auto& c : cases) {
            Outcome o;
            try {
                double v = solvers[i].f(c);
                o = {std::isfinite(v), v};
            } catch (std::exception&) {
                o = {false, 0.0};
                ++thrown[i];
            }
            outcomes[i].push_back(o);
        }
    }
    auto report = [&](const char* title, const std::function<bool(const Case&)>& in) {
        size_t n = 0;
        for (const auto& c : cases)
            n += in(c);
        std::printf("%s: %zu cases\n", title, n);
        std::printf("%-36s %6s %6s %10s %10s %10s %9s %9s %12s\n", "solver", "ok", "fail",
                    "median", "p99", "max", "err>1e-9", "err>1e-6", "max/(eps*c)");
        for (size_t i = 0; i < solvers.size(); ++i) {
            std::vector<double> errs;
            int ok = 0, fail = 0, big9 = 0, big6 = 0;
            double worstNorm = 0;
            for (size_t j = 0; j < cases.size(); ++j) {
                if (!in(cases[j]))
                    continue;
                if (!outcomes[i][j].ok) {
                    ++fail;
                    continue;
                }
                ++ok;
                double e = std::fabs(outcomes[i][j].value - cases[j].ref) / cases[j].ref;
                errs.push_back(e);
                big9 += e > 1e-9;
                big6 += e > 1e-6;
                worstNorm = std::max(worstNorm, e / (QL_EPSILON * cases[j].cond));
            }
            std::printf("%-36s %6d %6d %10.2e %10.2e %10.2e %9d %9d %12.3g\n",
                        solvers[i].name.c_str(), ok, fail, percentile(errs, 0.5),
                        percentile(errs, 0.99),
                        errs.empty() ? NAN : *std::max_element(errs.begin(), errs.end()), big9,
                        big6, worstNorm);
        }
        std::printf("\n");
    };
    report("all usable cases", [](const Case&) { return true; });
    report("well-conditioned (cond <= 1e3)", [](const Case& c) { return c.cond <= 1e3; });
    report("out-of-the-money options only",
           [](const Case& c) { return (c.type == Option::Call) ? c.x <= 0 : c.x >= 0; });
    report("ill-conditioned (cond > 1e3; only max/(eps*c) is meaningful)",
           [](const Case& c) { return c.cond > 1e3; });

    std::vector<size_t> common;
    for (size_t j = 0; j < cases.size(); ++j) {
        bool all_ok = true;
        for (auto& o : outcomes)
            all_ok = all_ok && o[j].ok;
        if (all_ok)
            common.push_back(j);
    }

    {
        double worst = 0;
        const Case* w = nullptr;
        for (size_t j = 0; j < cases.size(); ++j) {
            if (!outcomes[0][j].ok)
                continue;
            double r = std::fabs(outcomes[0][j].value - cases[j].ref) / cases[j].ref /
                       (QL_EPSILON * cases[j].cond);
            if (r > worst) {
                worst = r;
                w = &cases[j];
            }
        }
        if (w)
            std::printf("LetsBeRational worst error/(eps*cond) %.3g at %s x=%g s=%g cond=%.3g\n",
                        worst, w->type == Option::Call ? "call" : "put", w->x, w->s, w->cond);
    }

    // ---- iterations (normalised level, as the public function calls it) ---
    {
        std::map<Size, int> hist;
        for (const auto& c : cases) {
            Real f = c.forward, k = c.strike, x = std::log(f / k);
            Real theta = c.type == Option::Call ? 1.0 : -1.0;
            Real intrinsic = std::max(theta * (f - k), 0.0);
            Real tv = c.price;
            Option::Type t = c.type;
            if (theta * x > 0) {
                tv = c.price - intrinsic;
                t = Option::Type(-c.type);
            }
            Size it = 0;
            detail::normalisedImpliedStdDevLetsBeRational(tv / (std::sqrt(f) * std::sqrt(k)), x,
                                                          t, 2, &it);
            hist[it]++;
        }
        std::printf("\nLetsBeRational Householder iterations:");
        for (auto& h : hist)
            std::printf("  %zu: %d", h.first, h.second);
        std::printf("\n");
    }

    // ---- timing --------------------------------------------------------------
    std::printf("\ntiming on the common subset (%zu cases), ns per call, best of 5 runs\n",
                common.size());
    const int reps = 200;
    volatile double sink = 0;
    for (auto& s : solvers) {
        double best = 1e300;
        for (int run = 0; run < 5; ++run) {
            auto t0 = std::chrono::steady_clock::now();
            for (int r = 0; r < reps; ++r)
                for (size_t j : common)
                    sink = sink + s.f(cases[j]);
            auto t1 = std::chrono::steady_clock::now();
            double ns = std::chrono::duration<double, std::nano>(t1 - t0).count() /
                        (double(reps) * common.size());
            best = std::min(best, ns);
        }
        std::printf("%-36s %8.0f\n", s.name.c_str(), best);
    }
    {
        double best = 1e300;
        for (int run = 0; run < 5; ++run) {
            auto t0 = std::chrono::steady_clock::now();
            for (int r = 0; r < reps; ++r)
                for (const auto& c : cases)
                    sink = sink + solvers[0].f(c);
            auto t1 = std::chrono::steady_clock::now();
            best = std::min(best, std::chrono::duration<double, std::nano>(t1 - t0).count() /
                                      (double(reps) * cases.size()));
        }
        std::printf("%-36s %8.0f  (all %zu usable cases)\n", "LetsBeRational", best,
                    cases.size());
    }
    return 0;
}
