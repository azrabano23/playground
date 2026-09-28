"""Regenerate src/wormstage/data/connectomes.json.gz from a pinned upstream wheel.

Source: cect 0.3.4 (OpenWorm ConnectomeToolbox, MIT), whose cache holds the
parsed matrices of Witvliet et al. 2021 (Nature 596:257, eight nerve-ring
connectomes from birth to adulthood) and Cook et al. 2019 (Nature 571:63,
adult hermaphrodite, whole animal), plus WormAtlas neurotransmitter identities.

    python scripts/build_data.py            # download, verify sha256, extract
    python scripts/build_data.py --wheel path/to/cect-0.3.4-py3-none-any.whl
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

URL = ("https://files.pythonhosted.org/packages/11/d6/2516a0843b23d1180f97928d541ae620939fde5"
       "61dfd8980b2c9c62003f9/cect-0.3.4-py3-none-any.whl")
SHA256 = "dc7431ff11b9d14ddc565246784e9b0cdbc2c96d68427eb6285429ea05d87e11"

# Witvliet et al. 2021, dataset table: developmental age in hours after birth.
STAGES = [
    ("witvliet1", "WitvlietDataReader1", "L1", 0),
    ("witvliet2", "WitvlietDataReader2", "L1", 5),
    ("witvliet3", "WitvlietDataReader3", "L1", 8),
    ("witvliet4", "WitvlietDataReader4", "L1", 16),
    ("witvliet5", "WitvlietDataReader5", "L2", 23),
    ("witvliet6", "WitvlietDataReader6", "L3", 27),
    ("witvliet7", "WitvlietDataReader7", "adult", 45),
    ("witvliet8", "WitvlietDataReader8", "adult", 45),
    ("cook2019", "Cook2019HermReader", "adult", None),
]
OUT = Path(__file__).resolve().parents[1] / "src" / "wormstage" / "data" / "connectomes.json.gz"


def fetch(path: str | None) -> bytes:
    blob = Path(path).read_bytes() if path else urllib.request.urlopen(URL, timeout=120).read()
    got = hashlib.sha256(blob).hexdigest()
    if got != SHA256:
        raise SystemExit(f"sha256 mismatch: {got}")
    return blob


def edges(matrix, nodes):
    out = []
    for i, row in enumerate(matrix):
        for j, w in enumerate(row):
            if w:
                out.append([nodes[i], nodes[j], float(w)])
    return out


def build(blob: bytes) -> dict:
    z = zipfile.ZipFile(io.BytesIO(blob))
    data = {"source": {"wheel": URL, "sha256": SHA256}, "stages": [], "transmitters": {}}
    for key, reader, label, hours in STAGES:
        d = json.loads(z.read(f"cect/cache/{reader}.json"))
        nodes = d["nodes"]
        c = d["connections"]
        data["stages"].append({
            "key": key, "label": label, "hours": hours, "nodes": nodes,
            "chemical": edges(c["Generic_CS"], nodes),
            "electrical": edges(c["Generic_GJ"], nodes),
        })
    rows = csv.reader(io.StringIO(z.read("cect/data/Modified celegans db dump.csv").decode()))
    next(rows)
    for r in rows:
        if len(r) > 2 and r[1] == "Neurotransmitter":
            data["transmitters"].setdefault(r[0].strip(), []).append(r[2].strip())
    for k in data["transmitters"]:
        data["transmitters"][k] = sorted(set(data["transmitters"][k]))
    return data


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--wheel")
    a = p.parse_args()
    data = build(fetch(a.wheel))
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(OUT, "wb", mtime=0) as f:
        f.write(raw)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes), content sha256 "
          f"{hashlib.sha256(raw).hexdigest()[:16]}")


if __name__ == "__main__":
    main()
