import json, sys, pytrec_eval
d = json.load(open("dummy.json"))
ev = pytrec_eval.RelevanceEvaluator(d["qrels"], {"ndcg_cut.1,3,10", "P.1", "recall.10"})
s = ev.evaluate(d["results"])
print(json.dumps({q: [round(v["ndcg_cut_1"],3), round(v["ndcg_cut_10"],3), round(v["P_1"],3), round(v["recall_10"],3)] for q, v in s.items()}))
