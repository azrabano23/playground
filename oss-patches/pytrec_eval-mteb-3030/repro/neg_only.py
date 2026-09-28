import json, pytrec_eval
qrel = {'q1': {'d1': 1}, 'q2': {'d1': -2, 'd2': -2}, 'q3': {'d2': 1}}
run = {q: {'d1': 2.0, 'd2': 1.0} for q in qrel}
print(json.dumps(pytrec_eval.RelevanceEvaluator(qrel, {'ndcg', 'P.1'}).evaluate(run), sort_keys=True))
