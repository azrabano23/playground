import numpy as np
import pytest

from loopgraph.cgate import cc
from myoedge.data import Recording
from myoedge.deploy import SERVO_CLOSED, SERVO_OPEN, Model, check_c, run_stream
from myoedge.features import featurize
from myoedge.model import fit_lda, standardise


def synthetic(rng, n=400):
    """Five classes with distinct spatial activity profiles."""
    prof = np.array([[90, 60, 20, 5, 5, 10, 30, 70], [5, 10, 40, 90, 70, 30, 5, 5],
                     [2, 2, 2, 2, 2, 2, 2, 2], [40, 5, 5, 40, 5, 5, 40, 5],
                     [5, 40, 40, 5, 40, 40, 5, 5]])
    recs = []
    for c, g in enumerate(prof):
        for r in range(3):
            x = np.clip(rng.normal(0, 1, (n, 8)) * g / 3, -128, 127).astype(np.int8)
            recs.append(Recording(x, c, r, "training"))
    return recs


@pytest.fixture(scope="module")
def model():
    rng = np.random.default_rng(0)
    recs = synthetic(rng)
    X, y = featurize(recs, 40, 8)
    mu, sd = standardise(X)
    return Model.build(fit_lda((X - mu) / sd, y), mu, sd, X, 40, 8, 3), recs


def test_int8_classifier_separates_synthetic_classes(model):
    m, recs = model
    X, y = featurize(recs, 40, 8)
    assert np.mean(m.classify(X) == y) > 0.95


def test_stream_closes_and_opens_the_hand(model):
    m, recs = model
    fist = np.concatenate([r.emg for r in recs if r.label == 0])
    out = run_stream(m, fist)
    assert out[-1, 0] == 0 and np.array_equal(out[-1, 1:], SERVO_CLOSED)
    opn = np.concatenate([r.emg for r in recs if r.label == 1])
    out = run_stream(m, np.concatenate([fist, opn]))
    assert np.array_equal(out[-1, 1:], SERVO_OPEN)


def test_budget_fits_an_atmega32u4(model):
    m, _ = model
    assert m.flash_bytes < 28 * 1024 and m.ram_bytes < 2048
    assert m.latency_ms == 1000 * (20 + 8) / 200


@pytest.mark.skipif(cc() is None, reason="no C compiler")
@pytest.mark.parametrize("shift", [0, -3, 5])
def test_c_decoder_is_bit_exact(model, shift):
    m, recs = model
    m.shift = shift
    emg = np.concatenate([r.emg[:200] for r in recs])
    ok, bad, n = check_c(m, emg)
    m.shift = 0
    assert ok and n > 50, (bad, n)
