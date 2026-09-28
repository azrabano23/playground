"""Evaluate the mteb#3030 dummy file with the exact measure set MTEB uses.
Prints one line: mean ndcg_cut@k and whether any per-query ndcg > 1 or NaN."""
import json, math, sys
import pytrec_eval

path = sys.argv[1] if len(sys.argv) > 1 else "dummy.json"
d = json.load(open(path))
qrels, results = d["qrels"], d["results"]
ks = [1, 3, 5, 10, 20, 100, 1000]
j = lambda p: p + ".".join([""]) + ",".join(map(str, ks))
ev = pytrec_eval.RelevanceEvaluator(
    qrels, {"map_cut." + ",".join(map(str, ks)), "ndcg_cut." + ",".join(map(str, ks)),
            "recall." + ",".join(map(str, ks)), "P." + ",".join(map(str, ks))})
s = ev.evaluate(results)
means = {k: round(sum(v[f"ndcg_cut_{k}"] for v in s.values()) / len(s), 5) for k in ks}
bad = sorted({q for q, v in s.items() for m, x in v.items()
              if m.startswith("ndcg") and (x > 1 + 1e-9 or math.isnan(x))})
print(json.dumps({"ndcg": means, "queries_ndcg_gt1_or_nan": bad}, sort_keys=True))
