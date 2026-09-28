import numpy as np

from wormstage.brain import Brain, shuffle_chemical, signs, stage_report
from wormstage.data import load


def test_shuffle_preserves_degrees_and_weights():
    C = load("witvliet1").chemical
    S = shuffle_chemical(C, np.random.default_rng(0))
    assert np.isclose(S.sum(), C.sum())
    assert np.allclose(S.sum(0), C.sum(0))          # each pre keeps its output
    assert np.trace(S) == 0 and not np.array_equal(S, C)


def test_model_is_stable():
    b = Brain.build(load("cook2019"))
    assert np.abs(b.A).sum(1).max() < 1.0


def test_signs_follow_transmitters():
    s = load("witvliet8")
    sg = signs(s, glu_sign=-1)
    ix = s.index
    assert sg[ix["AVAL"]] == 1 and sg[ix["ASHL"]] == -1
    assert sg[ix["RMDDL"]] == 1


def test_nociception_drives_reversal_from_birth():
    """ASH -> backward command bias exceeds wiring-matched shuffles at 0 h and 45 h.

    Conditional on glutamate being excitatory (it is at ASH -> AVA, via GLR-1).
    """
    for key in ("witvliet1", "witvliet8"):
        r = stage_report(key, glu_sign=1.0, n_null=300)
        assert r["ASH_rev"] > 0 and r["ASH_p"] < 0.05
