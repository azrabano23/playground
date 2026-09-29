import pytrec_eval
qrel = {'q1': {'d1': 1, 'd2': 1}}
ev = pytrec_eval.RelevanceEvaluator(qrel, {'num_rel', 'num_ret', 'recall.10'})
try:
    print("first  call, empty ranking:", ev.evaluate({'q1': {}}))
except RuntimeError as e:
    print("first  call, empty ranking: RuntimeError", e)
print("normal call               :", ev.evaluate({'q1': {'d1': 1.0}}))
try:
    print("third  call, empty ranking:", ev.evaluate({'q1': {}}))
except RuntimeError as e:
    print("third  call, empty ranking: RuntimeError", e)
