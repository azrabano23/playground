import json

import numpy as np

from loopgraph.ledger import Claim, Ledger, at_least, at_most, load_claims, record, verify_claims


def test_record_and_read_back(tmp_path):
    L = Ledger(tmp_path / "ledger.jsonl")
    e = record(L, "exp", {"h": 8}, {"acc": np.float32(0.9), "kb": 12},
               gates=[at_least("acc", 0.8), at_most("kb", 16)])
    assert e.admitted
    [back] = L.entries("exp")
    assert back.metrics["acc"] == float(np.float32(0.9))
    assert back.gates == {"acc>=0.8": True, "kb<=16": True}


def test_failed_gate_is_recorded_not_dropped(tmp_path):
    L = Ledger(tmp_path / "l.jsonl")
    record(L, "exp", {"h": 4}, {"acc": 0.5}, gates=[at_least("acc", 0.8)])
    record(L, "exp", {"h": 8}, {"acc": 0.85}, gates=[at_least("acc", 0.8)])
    assert len(L.entries("exp")) == 2
    assert L.best("exp", "acc").params == {"h": 8}
    # a missing metric fails its gate rather than raising
    e = record(L, "exp", {}, {}, gates=[at_least("acc", 0.8)])
    assert not e.admitted


def test_claims_catch_drift(tmp_path):
    L = Ledger(tmp_path / "l.jsonl")
    record(L, "exp", {}, {"acc": 0.91})
    ok, = verify_claims(L, [Claim("c1", "exp", "acc", 0.91, tol=0.005)])
    assert ok[1]
    stale, = verify_claims(L, [Claim("c2", "exp", "acc", 0.95, tol=0.005)])
    assert not stale[1] and stale[2] == 0.91
    missing, = verify_claims(L, [Claim("c3", "nope", "acc", 1.0)])
    assert not missing[1]


def test_load_claims(tmp_path):
    p = tmp_path / "claims.json"
    p.write_text(json.dumps([{"id": "a", "experiment": "e", "metric": "m", "value": 1.0}]))
    [c] = load_claims(p)
    assert c.select == "latest"
