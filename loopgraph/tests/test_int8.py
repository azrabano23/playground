import numpy as np
import pytest

from loopgraph.cgate import bit_exact_mlp, cc, object_size
from loopgraph.int8 import emit_c, float_forward, quantize_mlp

needs_cc = pytest.mark.skipif(cc() is None, reason="no C compiler")


def random_mlp(dims, seed=0):
    rng = np.random.default_rng(seed)
    return [(rng.normal(0, 1 / np.sqrt(i), (o, i)), rng.normal(0, 0.1, o))
            for i, o in zip(dims[:-1], dims[1:])]


def test_int8_tracks_float():
    rng = np.random.default_rng(1)
    W = random_mlp([12, 32, 32, 5])
    X = rng.normal(size=(2000, 12))
    q = quantize_mlp(W, X[:500])
    yf = float_forward(W, X[500:])
    yq = q.forward(X[500:])
    r = np.corrcoef(yf.ravel(), yq.ravel())[0, 1]
    assert r > 0.99
    # argmax agreement is what a classifier cares about
    assert np.mean(yf.argmax(1) == yq.argmax(1)) > 0.95


def test_param_accounting():
    q = quantize_mlp(random_mlp([10, 20, 3]), np.ones((4, 10)))
    assert q.param_bytes == (10 * 20 + 20 * 3) + 4 * (20 + 3) * 2
    assert q.macs == 10 * 20 + 20 * 3
    assert q.dims == [10, 20, 3]


def test_emitted_c_has_no_floats_in_forward():
    q = quantize_mlp(random_mlp([6, 8, 2]), np.ones((4, 6)))
    src = emit_c(q, "tiny")["tiny.c"]
    assert "float" not in src and "double" not in src and "malloc" not in src


@needs_cc
def test_c_is_bit_exact_with_reference():
    rng = np.random.default_rng(2)
    W = random_mlp([16, 48, 24, 7], seed=3)
    X = rng.normal(size=(600, 16))
    q = quantize_mlp(W, X)
    rep = bit_exact_mlp(q, q.quantize_input(X), "policy")
    assert rep.ok, rep
    # saturating inputs exercise the clamps
    edge = rng.choice(np.array([-128, 127, 0], np.int8), size=(64, 16))
    assert bit_exact_mlp(q, edge, "policy").ok


@needs_cc
def test_object_size_reports_rodata():
    q = quantize_mlp(random_mlp([32, 64, 4]), np.ones((4, 32)))
    try:
        s = object_size(emit_c(q, "sz"), "sz.c")
    except Exception as e:  # binutils missing
        pytest.skip(str(e))
    const = sum(v for k, v in s.items() if k.startswith((".rodata", ".data", ".text")))
    assert const >= q.param_bytes
