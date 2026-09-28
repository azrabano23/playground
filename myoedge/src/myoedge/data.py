"""Real sEMG from LibEMG's public datasets, fetched at pinned commits.

CIIL ElectrodeShift (Campbell et al., J NeuroEng Rehabil 2024): 21 subjects,
Myo armband (8 channels, 200 Hz, raw int8 counts), 5 classes. Five
repetitions are recorded, the armband is then displaced, and four more
sessions are recorded. That displacement is exactly what happens every time
a prosthesis user takes the socket off and puts it back on.

The upstream repositories carry no license file, so the data is not
redistributed here; `myoedge fetch` clones it.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parents[2] / "data"
REPOS = {
    "CIILData": ("https://github.com/LibEMG/CIILData",
                 "b7230dd253b3cd2c2603f5fdeb0c3711551ba19f"),
    "OneSubjectMyoDataset": ("https://github.com/LibEMG/OneSubjectMyoDataset",
                             "98d323eb224f3a270ce9c230b3dc9f7de5d9b637"),
}
FS = 200
CHANNELS = 8
CLASSES = ["Hand_Close", "Hand_Open", "No_Motion", "Wrist_Extension", "Wrist_Flexion"]
SETS = ["training", "trial_1", "trial_2", "trial_3", "trial_4"]


def fetch(root: Path = DATA) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, (url, rev) in REPOS.items():
        d = root / name
        if not d.exists():
            subprocess.run(["git", "clone", "--quiet", url, str(d)], check=True)
        subprocess.run(["git", "-C", str(d), "checkout", "--quiet", rev], check=True)
        got = subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"], check=True,
                             capture_output=True, text=True).stdout.strip()
        if got != rev:
            raise RuntimeError(f"{name}: expected {rev}, have {got}")


def available(root: Path = DATA) -> bool:
    return (root / "CIILData" / "ElectrodeShift").is_dir()


@dataclass
class Recording:
    emg: np.ndarray    # int8 [T, 8]
    label: int         # index into CLASSES
    rep: int
    session: str


def _class_map(folder: Path) -> dict[str, int]:
    """File -> class from the folder's own metadata (LibEMG's dict swaps 3 and 4)."""
    meta = folder / "metadata.json"
    out = {}
    if meta.exists():
        for k, v in json.loads(meta.read_text()).items():
            if isinstance(v, dict) and "class_name" in v:
                out[Path(k).name] = CLASSES.index(v["class_name"])
    return out


def load_session(folder: Path, session: str) -> list[Recording]:
    cmap = _class_map(folder)
    recs = []
    for f in sorted(folder.glob("R_*_C_*.csv")):
        r, c = map(int, re.match(r"R_(\d+)_C_(\d+)\.csv", f.name).groups())
        x = np.loadtxt(f, delimiter=",", dtype=np.int16, ndmin=2)
        recs.append(Recording(np.clip(x, -128, 127).astype(np.int8), cmap.get(f.name, c), r,
                              session))
    return recs


def electrode_shift(subject: int, root: Path = DATA) -> dict[str, list[Recording]]:
    base = root / "CIILData" / "ElectrodeShift" / f"subject{subject}"
    return {s: load_session(base / s, s) for s in SETS if (base / s).is_dir()}


def subjects(root: Path = DATA) -> list[int]:
    base = root / "CIILData" / "ElectrodeShift"
    return sorted(int(p.name[7:]) for p in base.glob("subject*"))
