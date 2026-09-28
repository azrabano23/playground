from loopgraph.agents import (Campaign, Committee, GridDecider, Objective, ParetoDecider,
                              RandomDecider, pareto_front, validate)
from loopgraph.ledger import Entry, Ledger, at_least

SPACE = {"width": [4, 8, 16, 32, 64], "bits": [4, 8]}


def fake_model(p):
    # accuracy saturates with width and drops at 4 bits; size grows with both
    acc = 1 - 1 / p["width"] - (0.08 if p["bits"] == 4 else 0)
    kb = p["width"] * p["bits"] / 8
    return {"acc": acc, "kb": kb}


def test_validate_coerces_text_values():
    assert validate({"width": "16", "bits": 8.0}, SPACE) == {"width": 16, "bits": 8}
    assert validate({"width": 17, "bits": 8}, SPACE) is None
    assert validate({"width": 16}, SPACE) is None


def test_grid_is_exhaustive_then_stops(tmp_path):
    L = Ledger(tmp_path / "l.jsonl")
    made = Campaign("g", SPACE, fake_model, L, GridDecider(), budget=100).run()
    assert len(made) == 10
    assert len({tuple(e.params.values()) for e in made}) == 10


def test_pareto_front():
    es = [Entry("x", {"i": i}, m) for i, m in enumerate(
        [{"acc": 0.9, "kb": 10}, {"acc": 0.8, "kb": 5}, {"acc": 0.7, "kb": 8}, {"acc": 0.95, "kb": 40}])]
    front = pareto_front(es, [Objective("acc"), Objective("kb", maximize=False)])
    assert sorted(e.params["i"] for e in front) == [0, 1, 3]


def test_pareto_agent_never_repeats_and_records_rationale(tmp_path):
    L = Ledger(tmp_path / "l.jsonl")
    agent = ParetoDecider([Objective("acc"), Objective("kb", False)], seed=1)
    made = Campaign("p", SPACE, fake_model, L, agent, budget=8, batch=2).run()
    keys = [tuple(e.params.values()) for e in made]
    assert len(keys) == len(set(keys)) == 8
    assert all(e.rationale for e in made)
    assert any("frontier" in e.rationale for e in made[2:])


def test_gates_mark_but_keep_rejected_runs(tmp_path):
    L = Ledger(tmp_path / "l.jsonl")
    Campaign("gate", SPACE, fake_model, L, GridDecider(), gates=[at_least("acc", 0.9)],
             budget=10).run()
    es = L.entries("gate")
    assert len(es) == 10
    assert {e.admitted for e in es} == {True, False}


def test_committee_attributes_each_run(tmp_path):
    L = Ledger(tmp_path / "l.jsonl")
    c = Committee([GridDecider(), RandomDecider(3)])
    made = Campaign("c", SPACE, fake_model, L, c, budget=6, batch=3).run()
    assert {e.decided_by for e in made} == {"grid", "random"}
    assert len({tuple(e.params.values()) for e in made}) == 6
