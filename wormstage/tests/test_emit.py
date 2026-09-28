import numpy as np
import pytest

from loopgraph.cgate import cc
from wormstage.body import Snake
from wormstage.circuit import Circuit, compile_circuit
from wormstage.emit import check, emit
from wormstage.gait import run


@pytest.mark.skipif(cc() is None, reason="no C compiler")
@pytest.mark.parametrize("label,backward", [("L1", False), ("adult", False), ("adult", True)])
def test_c_matches_reference_on_a_real_trajectory(label, backward):
    c = Circuit.for_stage(label, backward=backward)
    tr = run(c, Snake(K=40), T=8)
    k = compile_circuit(c, 11, 0.02, 1.0)
    phis = np.round(tr.phi * 1000).astype(int)
    rng = np.random.default_rng(0)
    phis = np.concatenate([phis, rng.integers(-1000, 1000, (100, 11))])
    ok, bad = check(k, phis)
    assert ok, bad


def test_emitted_source_is_integer_only():
    k = compile_circuit(Circuit.for_stage("adult"), 11, 0.02, 1.0)
    src = emit(k)["worm.c"]
    assert "float" not in src and "double" not in src and "malloc" not in src
