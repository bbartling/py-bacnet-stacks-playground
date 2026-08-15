"""Lookback trajectory helpers (96 scored vs 192 all-rows)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from eplus_gym.objective import BAS_ZONE_COLS


def extract_lookback_end_zone_temps(
    all_rows: Sequence[Mapping[str, Any]],
) -> list[float]:
    look = [r for r in all_rows if r.get("lookback")]
    if not look:
        raise ValueError("no lookback rows; refusing default 70F start temps")
    last = look[-1]
    missing = [c for c in BAS_ZONE_COLS if c not in last]
    if missing:
        raise ValueError(f"lookback row missing zone columns {missing}")
    return [float(last[c]) for c in BAS_ZONE_COLS]


def write_episode_manifest(
    ep_dir: Path,
    *,
    n_rows: int,
    n_all_rows: int,
    trajectory: Path,
    trajectory_all: Path | None,
) -> dict[str, Any]:
    def _h(p: Path | None) -> str | None:
        if p is None or not Path(p).is_file():
            return None
        h = hashlib.sha256()
        with Path(p).open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    if int(n_rows) == int(n_all_rows) and int(n_all_rows) == 192:
        raise ValueError("scored artifact must not claim 192 rows as the 96-row target-day file")
    man = {
        "schema": "vibe22.episode_manifest.v1",
        "n_rows_scored": int(n_rows),
        "n_all_rows": int(n_all_rows),
        "scored_is_not_full_simulation": True,
        "trajectory_sha256": _h(trajectory),
        "trajectory_all_sha256": _h(trajectory_all),
    }
    Path(ep_dir).mkdir(parents=True, exist_ok=True)
    (Path(ep_dir) / "episode_manifest.json").write_text(
        __import__("json").dumps(man, indent=2) + "\n", encoding="utf-8"
    )
    return man
