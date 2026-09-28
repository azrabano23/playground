from wormstage.pipeline import execute


def test_ash_makes_the_adult_robot_reverse(tmp_path):
    m, keys = execute({"stage": "witvliet8", "stimulus": "ASH", "T": 20.0}, tmp_path)
    assert m["reverses"] == 1 and m["forward_bl_s"] < 0
    assert m.get("bit_exact", 1) == 1
    assert {"brain", "command", "circuit", "gait", "metrics"} <= set(keys)


def test_resting_robot_crawls_forward(tmp_path):
    m, _ = execute({"stage": "witvliet1", "T": 20.0}, tmp_path)
    assert m["reverses"] == 0 and m["forward_bl_s"] > 0 and m["undulating"] == 1
