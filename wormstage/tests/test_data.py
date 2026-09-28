import numpy as np

from wormstage.data import cell_class, load, source, stage_keys, transmitter


def test_all_stages_present_in_developmental_order():
    keys = stage_keys()
    assert keys[:8] == [f"witvliet{i}" for i in range(1, 9)] and keys[8] == "cook2019"
    hours = [load(k).hours for k in keys[:8]]
    assert hours == sorted(hours)
    assert [load(k).label for k in keys[:8]] == ["L1"] * 4 + ["L2", "L3", "adult", "adult"]


def test_synapse_counts_grow_with_age():
    """Witvliet et al.: the nerve ring gains synapses as the animal grows."""
    counts = [load(f"witvliet{i}").chemical.sum() for i in range(1, 9)]
    assert counts[0] < counts[3] < counts[6]
    assert counts[-1] > 5 * counts[0]


def test_orientation_is_post_by_pre():
    s = load("cook2019")
    ix = s.index
    # ASH -> AVA is a well-described chemical synapse; the reverse is absent
    assert s.chemical[ix["AVAL"], ix["ASHL"]] > 0
    assert s.chemical[ix["ASHL"], ix["AVAL"]] == 0
    assert np.array_equal(s.electrical, s.electrical.T)


def test_ash_ava_synapse_is_absent_at_birth():
    s0, s8 = load("witvliet1"), load("witvliet8")
    f = lambda s: s.chemical[s.index["AVAL"], s.index["ASHL"]]
    assert f(s0) == 0 and f(s8) > 0


def test_classes_and_transmitters():
    assert [cell_class(n) for n in ("AVAL", "DB03", "SMDDL", "RMDVR", "DB1")] == \
        ["AVA", "DB", "SMD", "RMD", "DB"]
    assert transmitter("AVAL") == ["Acetylcholine"]  # override, cited in data.py
    assert transmitter("DD1") == ["GABA"]
    assert len(source()["sha256"]) == 64
