import numpy as np

from myoedge.adapt import STEPS_PER_CHANNEL, estimate_shift, pattern, rotate
from tests.conftest import real


def fist(rng, n=600):
    gain = np.array([90, 60, 20, 5, 5, 10, 30, 70])  # a spatial activity profile
    return np.clip(rng.normal(0, 1, (n, 8)) * gain / 3, -128, 127).astype(np.int8)


def test_whole_channel_rotation_is_a_roll():
    x = np.arange(16, dtype=np.int8).reshape(2, 8)
    assert np.array_equal(rotate(x, STEPS_PER_CHANNEL), np.roll(x, -1, axis=1))
    assert np.array_equal(rotate(x, 0), x)


def test_shift_is_recovered():
    rng = np.random.default_rng(0)
    base = fist(rng)
    ref = pattern(base)
    for true in (-6, -2, 0, 3, 8):
        worn = rotate(fist(rng), true)
        assert abs(estimate_shift(ref, worn) - true) <= 1


@real
def test_real_data_shape():
    from myoedge.data import electrode_shift
    d = electrode_shift(0)
    assert set(d) == {"training", "trial_1", "trial_2", "trial_3", "trial_4"}
    assert {r.label for r in d["training"]} == {0, 1, 2, 3, 4}
    assert d["training"][0].emg.dtype == np.int8 and d["training"][0].emg.shape[1] == 8
