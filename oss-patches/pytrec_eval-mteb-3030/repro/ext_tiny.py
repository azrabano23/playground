import json
import pytrec_eval  # noqa
from pytrec_eval_ext import RelevanceEvaluator as Ext
qrel = {'q1': {'d1': 1, 'd2': 1}, 'q2': {}, 'q3': {'d1': 1, 'd3': 1}, 'q4': {'d2': 1}}
run = {q: {'d1': 3.0, 'd2': 2.0, 'd3': 1.0} for q in qrel}
ev = Ext(qrel, {'P.1', 'recall.10', 'ndcg_cut.1,3', 'ndcg'})
print(json.dumps(ev.evaluate(run), sort_keys=True))
