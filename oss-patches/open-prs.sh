#!/usr/bin/env bash
# Opens the 10 ready PRs from your forks. Needs the GitHub CLI: https://cli.github.com, then `gh auth login`.
# Run from this folder: bash open-prs.sh
set -u
cd "$(dirname "$0")"

echo "Opening pmorissette/bt (fix/rebalance-over-time-cash)"
gh pr create --repo pmorissette/bt --base master --head azrabano23:fix/rebalance-over-time-cash --title 'Keep cash reserve across RebalanceOverTime steps' --body-file pr-bodies/bt.md || echo '  -> failed, see above'
echo "Opening rsheftel/pandas_market_calendars (fix-486-cme-carter-early-close)"
gh pr create --repo rsheftel/pandas_market_calendars --base master --head azrabano23:fix-486-cme-carter-early-close --title 'CME: treat 2025-01-09 (Carter day of mourning) as an early close, not a holiday' --body-file pr-bodies/pmc-486.md || echo '  -> failed, see above'
echo "Opening rsheftel/pandas_market_calendars (fix-ice-carter-2025)"
gh pr create --repo rsheftel/pandas_market_calendars --base master --head azrabano23:fix-ice-carter-2025 --title 'ICE: keep 2025-01-09 as a trading day' --body-file pr-bodies/pmc-ice.md || echo '  -> failed, see above'
echo "Opening gerrymanoim/exchange_calendars (fix-xkrx-empty-observance)"
gh pr create --repo gerrymanoim/exchange_calendars --base master --head azrabano23:fix-xkrx-empty-observance --title 'Don'"'"'t call holiday observances with an empty index (fixes #300)' --body-file pr-bodies/xcal-300.md || echo '  -> failed, see above'
echo "Opening bashtage/linearmodels (fix-weighted-f-statistic)"
gh pr create --repo bashtage/linearmodels --base main --head azrabano23:fix-weighted-f-statistic --title 'BUG: Fix model F-statistic in weighted panel models with a constant' --body-file pr-bodies/lm-weighted-f.md || echo '  -> failed, see above'
echo "Opening bashtage/linearmodels (fix-absorbing-refit-df)"
gh pr create --repo bashtage/linearmodels --base main --head azrabano23:fix-absorbing-refit-df --title 'BUG: Stop AbsorbingLS.fit from accumulating df_model across calls' --body-file pr-bodies/lm-absorbing.md || echo '  -> failed, see above'
echo "Opening bashtage/linearmodels (fix-631-f-pooled-robust)"
gh pr create --repo bashtage/linearmodels --base main --head azrabano23:fix-631-f-pooled-robust --title 'BUG: Do not report the poolability F-test with robust/clustered covariance' --body-file pr-bodies/lm-631.md || echo '  -> failed, see above'
echo "Opening usnistgov/trec_eval (fix-form-res-rels-empty-qrels)"
gh pr create --repo usnistgov/trec_eval --base main --head azrabano23:fix-form-res-rels-empty-qrels --title 'Fix te_form_res_rels crash/stale values for topics with no non-negative judgments' --body-file pr-bodies/trec_eval.md || echo '  -> failed, see above'
echo "Opening terrierteam/pytrec_eval (fix-empty-qrels-c-state)"
gh pr create --repo terrierteam/pytrec_eval --base master --head azrabano23:fix-empty-qrels-c-state --title 'Fix garbage/stale scores for queries without judgments in the C extension' --body-file pr-bodies/pytrec_eval.md || echo '  -> failed, see above'
echo "Opening embeddings-benchmark/mteb (fix/pytrec-eval-min-version)"
gh pr create --repo embeddings-benchmark/mteb --base main --head azrabano23:fix/pytrec-eval-min-version --title 'fix: require pytrec-eval-terrier>=0.5.8' --body-file pr-bodies/mteb.md || echo '  -> failed, see above'
