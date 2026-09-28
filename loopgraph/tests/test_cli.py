import json

from loopgraph.cli import main
from loopgraph.ledger import Ledger, record


def test_show_front_and_claims(tmp_path, capsys):
    L = Ledger(tmp_path / "l.jsonl")
    record(L, "e", {"w": 8}, {"acc": 0.8, "kb": 2}, decided_by="grid")
    record(L, "e", {"w": 16}, {"acc": 0.9, "kb": 4}, decided_by="llm")
    record(L, "e", {"w": 32}, {"acc": 0.85, "kb": 8}, decided_by="pareto")
    assert main(["show", str(L.path), "-e", "e"]) == 0
    out = capsys.readouterr().out
    assert "3 runs, 3 admitted" in out and "llm=1" in out

    assert main(["front", str(L.path), "-e", "e", "-o", "acc,kb:min"]) == 0
    out = capsys.readouterr().out
    assert "'w': 32" not in out and "'w': 16" in out

    claims = tmp_path / "c.json"
    claims.write_text(json.dumps([
        {"id": "best", "experiment": "e", "metric": "acc", "value": 0.9, "select": "best:acc"},
        {"id": "stale", "experiment": "e", "metric": "acc", "value": 0.99},
    ]))
    assert main(["claims", str(L.path), str(claims)]) == 1
    out = capsys.readouterr().out
    assert "ok   best" in out and "FAIL stale" in out
