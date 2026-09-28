"""The connectomes, as published, by developmental stage.

`connectomes.json.gz` is a derived extract (see scripts/build_data.py) of
Witvliet et al. 2021 (eight nerve-ring connectomes, 0 h to 45 h after birth)
and Cook et al. 2019 (adult hermaphrodite, whole animal), taken from a
sha256-pinned release of OpenWorm's ConnectomeToolbox (MIT).
"""

from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

import numpy as np

# Cholinergic identities absent from the WormAtlas table bundled upstream.
# Pereira et al. 2015, eLife 4:e12432 (cholinergic reporter map).
TRANSMITTER_OVERRIDES = {c: ["Acetylcholine"] for c in ("AVA", "AVB", "AVD", "AVE", "RIB")}


@dataclass
class Stage:
    key: str
    label: str            # L1, L2, L3, adult
    hours: int | None     # after birth; None for Cook 2019
    nodes: list[str]
    chemical: np.ndarray  # [post, pre] synapse counts
    electrical: np.ndarray  # symmetric gap junction counts

    @property
    def index(self) -> dict[str, int]:
        return {n: i for i, n in enumerate(self.nodes)}

    def ids(self, names) -> list[int]:
        ix = self.index
        return [ix[n] for n in names if n in ix]


@lru_cache(maxsize=1)
def _raw() -> dict:
    p = resources.files("wormstage") / "data" / "connectomes.json.gz"
    with gzip.open(str(p), "rt") as f:
        return json.load(f)


def cell_class(name: str) -> str:
    """AVAL -> AVA, DB03 -> DB, SMDDL -> SMD, RMDVR -> RMD."""
    m = re.match(r"^([A-Z]+?)(\d+)$", name)
    if m:
        return m.group(1)
    for n in (3, 4):
        if len(name) > n and name[:n] in ("SMD", "SMB", "RMD", "RME", "SAA", "SIA", "SIB",
                                           "URA", "URY", "IL1", "IL2", "OLQ", "CEP"):
            return name[:n]
    return re.sub(r"(L|R|DL|DR|VL|VR|D|V)$", "", name)


def transmitters() -> dict[str, list[str]]:
    t = dict(_raw()["transmitters"])
    return t


def transmitter(name: str) -> list[str]:
    t = _raw()["transmitters"]
    if name in t:
        return t[name]
    return TRANSMITTER_OVERRIDES.get(cell_class(name), [])


def stage_keys() -> list[str]:
    return [s["key"] for s in _raw()["stages"]]


@lru_cache(maxsize=16)
def load(key: str) -> Stage:
    for s in _raw()["stages"]:
        if s["key"] == key:
            nodes = s["nodes"]
            ix = {n: i for i, n in enumerate(nodes)}
            C = np.zeros((len(nodes), len(nodes)))
            G = np.zeros_like(C)
            for pre, post, w in s["chemical"]:
                C[ix[post], ix[pre]] += w
            for a, b, w in s["electrical"]:
                G[ix[a], ix[b]] += w
            G = np.maximum(G, G.T)  # gap junctions are undirected
            return Stage(key, s["label"], s["hours"], nodes, C, G)
    raise KeyError(key)


def source() -> dict:
    return _raw()["source"]
