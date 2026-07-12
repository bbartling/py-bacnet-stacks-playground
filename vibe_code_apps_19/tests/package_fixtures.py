"""Helpers so package fixtures satisfy required per-CSV Haystack sidecars."""

from __future__ import annotations

import json
from pathlib import Path


def minimal_sidecar_json(*, equip_type: str = "ahu", points: dict[str, str] | None = None) -> str:
    pts = points or {"fan-status": "fan_status", "outside-air-temp": "oa_t"}
    return json.dumps({"equipType": equip_type, "points": pts})


def ensure_sidecar_files(files: dict[str, str | bytes]) -> dict[str, str | bytes]:
    """Add ``column_map.json`` next to each non-weather history_wide.csv if missing."""
    out = dict(files)
    for name in list(files):
        norm = name.replace("\\", "/")
        if not norm.endswith("history_wide.csv"):
            continue
        if "/weather/" in f"/{norm}" or norm.startswith("weather/"):
            continue
        folder = norm.rsplit("/", 1)[0]
        candidates = (
            f"{folder}/column_map.json",
            f"{folder}/history_wide.json",
            f"{folder}/history_wide.column_map.json",
        )
        if any(c in out for c in candidates):
            continue
        eq = folder.rsplit("/", 1)[-1]
        etype = "vav" if eq.upper().startswith("VAV") else "ahu"
        points = (
            {"zone-air-temp": "zone_t"}
            if etype == "vav"
            else {"fan-status": "fan_status", "outside-air-temp": "oa_t", "discharge-air-temp": "sat"}
        )
        # Prefer columns that commonly exist in fixtures
        out[f"{folder}/column_map.json"] = minimal_sidecar_json(equip_type=etype, points=points)
    return out


def write_equip_sidecar(eq_dir: Path, *, equip_type: str = "ahu", points: dict[str, str] | None = None) -> Path:
    path = eq_dir / "column_map.json"
    path.write_text(minimal_sidecar_json(equip_type=equip_type, points=points), encoding="utf-8")
    return path
