"""Locate airboxlab/rllib-energyplus without installing Ray/Pearl."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_VIBE22 = Path(__file__).resolve().parents[1]
_REPO = Path(__file__).resolve().parents[2]


def rleplus_roots() -> list[Path]:
    env = os.environ.get("RLEPLUS_ROOT", "").strip()
    cands = []
    if env:
        cands.append(Path(env))
    cands.extend(
        [
            _VIBE22 / "third_party" / "rllib-energyplus",
            _REPO / "third_party" / "rllib-energyplus",
            Path.home() / "Documents" / "rllib-energyplus",
        ]
    )
    return cands


def find_rleplus_root() -> Path:
    for root in rleplus_roots():
        if (root / "rleplus" / "env" / "energyplus.py").is_file():
            return root.resolve()
    raise FileNotFoundError(
        "rllib-energyplus not found. Clone https://github.com/airboxlab/rllib-energyplus "
        "to third_party/rllib-energyplus or set RLEPLUS_ROOT. Do not pip-install Ray/Pearl."
    )


def ensure_rleplus() -> Path:
    root = find_rleplus_root()
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)
    return root
