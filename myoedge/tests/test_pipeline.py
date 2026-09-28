import numpy as np

from myoedge.pipeline import evaluate_subject, voted
from tests.conftest import real


def test_vote_is_a_trailing_mode():
    p = np.array([0, 1, 1, 0, 2, 2, 2])
    assert list(voted(p, 1)) == list(p)
    assert list(voted(p, 3)) == [0, 0, 1, 1, 0, 2, 2]


@real
def test_recalibration_beats_baseline_on_a_shifted_subject():
    base = evaluate_subject(5, 40, 3, "lda", 0.0, 0)["acc"]
    cal = evaluate_subject(5, 40, 3, "lda", 0.0, 1)["acc"]
    assert cal > base + 0.3
