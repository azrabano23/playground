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
    std::printf("%-36s %6s %6s %6s %10s %10s %10s %9s %9s\n", "solver", "ok", "throw", "bad",
                "median", "p99", "max", "err>1e-6", "err>1e-3");
    std::vector<std::vector<Outcome>> outcomes(solvers.size());
    for (size_t i = 0; i < solvers.size(); ++i) {
        std::vector<double> errs;
        int ok = 0, thrown = 0, bad = 0, big6 = 0, big3 = 0;
        for (const auto& c : cases) {
            Outcome o = run(solvers[i], c);
            outcomes[i].push_back(o);
            if (!o.ok) {
                try {
                    double v = solvers[i].f(c);
                    (void)v;
                    ++bad; // returned NaN/inf
                } catch (std::exception&) {
                    ++thrown;
                }
                continue;
            }
            ++ok;
            double e = std::fabs(o.value - c.ref) / c.ref;
            errs.push_back(e);
            if (e > 1e-6)
                ++big6;
            if (e > 1e-3)
                ++big3;
        }
        std::printf("%-36s %6d %6d %6d %10.2e %10.2e %10.2e %9d %9d\n", solvers[i].name.c_str(),
                    ok, thrown, bad, percentile(errs, 0.5), percentile(errs, 0.99),
                    errs.empty() ? NAN : *std::max_element(errs.begin(), errs.end()), big6, big3);
    }

    // accuracy on the subset where every solver returns a value
    std::vector<size_t> common;
    for (size_t j = 0; j < cases.size(); ++j) {
        bool all_ok = true;
        for (auto& o : outcomes)
            all_ok = all_ok && o[j].ok;
        if (all_ok)
            common.push_back(j);
    }
    std::printf("\ncommon subset (all solvers return a value): %zu cases\n", common.size());
    std::printf("%-36s %10s %10s %10s\n", "solver", "median", "p99", "max");
    for (size_t i = 0; i < solvers.size(); ++i) {
        std::vector<double> errs;
        for (size_t j : common)
            errs.push_back(std::fabs(outcomes[i][j].value - cases[j].ref) / cases[j].ref);
        std::printf("%-36s %10.2e %10.2e %10.2e\n", solvers[i].name.c_str(),
                    percentile(errs, 0.5), percentile(errs, 0.99),
                    *std::max_element(errs.begin(), errs.end()));
    }

    // error in units of the attainable accuracy eps * conditioning
    {
        std::vector<double> ratio;
        double worst = 0;
        const Case* w = nullptr;
        for (size_t j = 0; j < cases.size(); ++j) {
            if (!outcomes[0][j].ok)
                continue;
            double e = std::fabs(outcomes[0][j].value - cases[j].ref) / cases[j].ref;
            double r = e / (QL_EPSILON * cases[j].cond);
            ratio.push_back(r);
            if (r > worst) {
                worst = r;
                w = &cases[j];
            }
        }
        std::printf("\nLetsBeRational error / (eps * conditioning): median %.2f, p99 %.2f, max "
                    "%.2f",
                    percentile(ratio, 0.5), percentile(ratio, 0.99), worst);
        if (w)
            std::printf(" (at %s x=%g s=%g)", w->type == Option::Call ? "call" : "put", w->x,
                        w->s);
        std::printf("\n");
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
