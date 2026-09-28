import numpy as np
import pytest

from wormstage.body import Snake
from wormstage.circuit import Circuit, compile_circuit, reset, tick
from wormstage.gait import measure, run


def test_stage_composition():
    l1, ad = Circuit.for_stage("L1"), Circuit.for_stage("adult")
    assert (l1.n_dorsal, l1.n_ventral) == (7, 0)      # DB only at hatching
    assert (ad.n_dorsal, ad.n_ventral) == (7, 11)     # + VB after L1
    back = Circuit.for_stage("adult", backward=True)
    assert (back.n_dorsal, back.n_ventral) == (9, 12)  # DA, VA


def test_tick_is_integer_and_bounded():
    k = compile_circuit(Circuit.for_stage("adult"), 11, 0.02, 1.0)
    st = reset(k)
    rng = np.random.default_rng(0)
    for _ in range(200):
        st, t = tick(k, st, rng.integers(-1000, 1000, 11))
        assert t.dtype == np.int64 and np.all(np.abs(t) <= 1000)
        assert set(np.unique(st.s_d)) <= {0, 1}
        assert np.all((st.m_d >= 0) & (st.m_d <= 32767))


def test_stretch_sign_turns_dorsal_neurons_on():
    """A ventral bend stretches the dorsal side, which excites dorsal B."""
    k = compile_circuit(Circuit.for_stage("L1"), 11, 0.02, 1.0)
    st = reset(k)
    st.s_d[:] = 0
    st, _ = tick(k, st, np.full(11, 300))
    assert st.s_d.all()
    st, _ = tick(k, st, np.full(11, -300))
    assert not st.s_d.any()


@pytest.mark.parametrize("label", ["L1", "adult"])
def test_both_stages_crawl_head_to_tail(label):
    m = measure(run(Circuit.for_stage(label), Snake(K=40), T=30))
    assert m["undulating"] == 1 and m["speed_bl_s"] > 0.05 and m["wave_dir"] == 1
    assert m["forward_bl_s"] > 0


@pytest.mark.parametrize("label", ["L1", "adult"])
def test_a_type_circuit_reverses(label):
    m = measure(run(Circuit.for_stage(label, backward=True), Snake(K=40), T=30))
    assert m["undulating"] == 1 and m["wave_dir"] == -1 and m["forward_bl_s"] < -0.05


def test_gait_adapts_to_the_medium():
    """Berri et al. 2009: in stiffer media the worm slows and shortens its wave."""
    water = measure(run(Circuit.for_stage("adult"), Snake(K=1.5), T=30))
    agar = measure(run(Circuit.for_stage("adult"), Snake(K=40), T=30))
    assert agar["freq_hz"] < water["freq_hz"]
    assert agar["wavelength_bl"] < water["wavelength_bl"]


def test_l1_needs_extrasynaptic_ventral_drive():
    """Lu et al. 2022: without it the juvenile circuit has no ventral bends."""
    with_drive = measure(run(Circuit.for_stage("L1"), Snake(K=40), T=30))
    without = measure(run(Circuit.for_stage("L1", ventral_tonic=0.0), Snake(K=40), T=30))
    assert with_drive["undulating"] == 1
    assert without["undulating"] == 0 and without["speed_bl_s"] < 0.01
