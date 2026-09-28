from loopgraph.ledger import Entry
from loopgraph.report import table


def test_table():
    t = table([Entry("e", {"w": 8}, {"acc": 0.91234})], ["w"], ["acc"], ["width", "accuracy"])
    assert t.splitlines() == ["| width | accuracy |", "|---|---|", "| 8 | 0.912 |"]
