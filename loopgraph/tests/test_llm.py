import json
from types import SimpleNamespace

from loopgraph.agents import Objective
from loopgraph.ledger import Entry
from loopgraph.llm import LLMDecider, _schema

SPACE = {"width": [8, 16, 32], "bits": [4, 8]}


class FakeMessages:
    def __init__(self, payload, stop="end_turn"):
        self.payload = payload
        self.stop = stop
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        block = SimpleNamespace(type="text", text=json.dumps(self.payload))
        return SimpleNamespace(stop_reason=self.stop, content=[block])


def client_with(payload, stop="end_turn"):
    msgs = FakeMessages(payload, stop)
    return SimpleNamespace(beta=SimpleNamespace(messages=msgs)), msgs


def test_schema_enumerates_choices():
    s = _schema(SPACE, 2)
    item = s["properties"]["proposals"]["items"]["properties"]["params"]
    assert item["properties"]["width"]["enum"] == ["8", "16", "32"]
    assert item["additionalProperties"] is False


def test_valid_proposals_are_used_and_invalid_are_replaced():
    payload = {"proposals": [
        {"params": {"width": "16", "bits": "8"}, "hypothesis": "wider fixes the accuracy gate"},
        {"params": {"width": "12", "bits": "8"}, "hypothesis": "off-grid"},
        {"params": {"width": "8", "bits": "4"}, "hypothesis": "already run"},
    ]}
    client, msgs = client_with(payload)
    d = LLMDecider([Objective("acc")], client=client, model="test-model")
    hist = [Entry("x", {"width": 8, "bits": 4}, {"acc": 0.5})]
    out = d.propose(SPACE, hist, 3)
    assert out[0].params == {"width": 16, "bits": 8}
    assert out[0].decided_by == "llm"
    assert "wider" in out[0].rationale
    assert all(p.decided_by.startswith("llm->") for p in out[1:])
    assert len({tuple(p.params.values()) for p in out}) == 3
    kw = msgs.calls[0]
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert "8" in kw["messages"][0]["content"]


def test_refusal_and_errors_degrade_to_fallback():
    client, _ = client_with({"proposals": []}, stop="refusal")
    d = LLMDecider([Objective("acc")], client=client, model="test-model")
    out = d.propose(SPACE, [], 2)
    assert len(out) == 2 and d.last_error == "refusal"

    class Boom:
        class beta:
            class messages:
                @staticmethod
                def create(**kw):
                    raise ConnectionError("offline")

    d = LLMDecider([Objective("acc")], client=Boom, model="test-model")
    out = d.propose(SPACE, [], 2)
    assert len(out) == 2 and "offline" in d.last_error
