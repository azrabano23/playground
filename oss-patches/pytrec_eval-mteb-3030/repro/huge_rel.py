import json, pytrec_eval
ev = pytrec_eval.RelevanceEvaluator({'q1': {'d1': 10**12}, 'q2': {'d1': 1}}, {'ndcg', 'P.1'})
try:
    print(json.dumps(ev.evaluate({'q1': {'d1': 1.0}, 'q2': {'d1': 1.0}}), sort_keys=True))
except RuntimeError as e:
    print("RuntimeError:", e)
