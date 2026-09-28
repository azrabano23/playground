import numpy as np

from myoedge.features import ilog2_q4, td, windows


def test_ilog2_is_monotone_and_exact_at_powers():
    v = np.arange(1, 5000)
    q = ilog2_q4(v)
    assert np.all(np.diff(q) >= 0)
    assert list(ilog2_q4(np.array([1, 2, 4, 1024]))) == [0, 16, 32, 160]
    # linear fraction (<= 0.086) plus flooring to 1/16 (< 0.0625)
    assert np.all(np.abs(q / 16 - np.log2(v)) < 0.15)


def test_td_features_by_hand():
    w = np.array([[1, 0], [-2, 0], [3, 0], [3, 0]], np.int8)
    f = td(w, zc_thr=1, ssc_thr=1, log=False)
    assert f[0] == 9 and f[2] == 3 + 5 + 0          # MAV-sum, WL of channel 0
    assert f[4] == 2 and f[6] == 1                  # two sign changes, one slope turn
    assert f[1] == f[3] == f[5] == f[7] == 0        # silent channel


def test_windows():
    x = np.arange(20)[:, None].repeat(8, 1).astype(np.int8)
    w = windows(x, 8, 4)
    assert w.shape == (4, 8, 8) and w[1, 0, 0] == 4
