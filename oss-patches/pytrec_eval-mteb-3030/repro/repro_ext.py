"""Same as repro_dummy.py but calls the C extension directly, bypassing the
Python-level empty-qrel filter added in pytrec_eval-terrier 0.5.8 (2d4d506).
This exercises the underlying C bug on any version."""
import json, math, sys
import pytrec_eval  # noqa: F401  (loads the ext)
from pytrec_eval_ext import RelevanceEvaluator as Ext

d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "dummy.json"))
ks = "1,3,5,10,20,100,1000"
ev = Ext(d["qrels"], {"map_cut." + ks, "ndcg_cut." + ks, "recall." + ks, "P." + ks})
s = ev.evaluate(d["results"])
K = [int(k) for k in ks.split(",")]
means = {k: round(sum(v[f"ndcg_cut_{k}"] for v in s.values()) / len(s), 5) for k in K}
bad = sorted({q for q, v in s.items() for m, x in v.items()
              if m.startswith("ndcg") and (x > 1 + 1e-9 or math.isnan(x))})
print(json.dumps({"n_queries": len(s), "ndcg": means, "n_queries_ndcg_gt1_or_nan": len(bad)}, sort_keys=True))
