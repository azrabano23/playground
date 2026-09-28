import numpy as np
import pytest

from loopgraph import Graph, GraphError, node, stable_hash

CALLS = []


@node()
def data(n):
    CALLS.append("data")
    return np.arange(n)


@node()
def doubled(data):
    CALLS.append("doubled")
    return data * 2


@node()
def total(doubled, offset):
    CALLS.append("total")
    return int(doubled.sum()) + offset


def test_runs_in_dependency_order():
    g = Graph([total, doubled, data])
    r = g.run(["total"], {"n": 4, "offset": 1})
    assert r["total"] == 13
    assert [t.name for t in r.trace] == ["data", "doubled", "total"]


def test_missing_params_named():
    with pytest.raises(GraphError, match="offset"):
        Graph([data, doubled, total]).run(["total"], {"n": 3})


def test_cache_reruns_only_downstream_of_changed_param(tmp_path):
    g = Graph([data, doubled, total], cache_dir=tmp_path)
    CALLS.clear()
    g.run(["total"], {"n": 5, "offset": 0})
    assert CALLS == ["data", "doubled", "total"]
    CALLS.clear()
    r = g.run(["total"], {"n": 5, "offset": 7})
    assert CALLS == ["total"]  # data and doubled came from cache
    assert r["total"] == 27
    assert [t.cached for t in r.trace] == [True, True, False]


def test_cycle_detected():
    @node("a")
    def a(b):
        return b

    @node("b")
    def b(a):
        return a

    with pytest.raises(GraphError, match="cycle"):
        Graph([a, b]).order(["a"])


def test_levels_group_independent_nodes():
    @node()
    def left(x):
        return x + 1

    @node()
    def right(x):
        return x - 1

    @node()
    def join(left, right):
        return left * right

    g = Graph([left, right, join])
    assert [sorted(w) for w in g.levels(["join"])] == [["left", "right"], ["join"]]
    assert g.run(["join"], {"x": 3}, workers=2)["join"] == 8


def test_stable_hash_sees_array_contents():
    a = np.zeros(4, np.int8)
    b = a.copy()
    b[2] = 1
    assert stable_hash(a) == stable_hash(a.copy())
    assert stable_hash(a) != stable_hash(b)
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})
