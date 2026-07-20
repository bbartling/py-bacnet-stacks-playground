"""Energy-use package loader (campus bills + optional Haystack interval maps).

Aligns with vibe19 ``column_map`` spirit: points → CSV headers, CSVs never rewritten.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from wattlab.benchmarks.fuel_weather import meter_monthly_long
from wattlab.benchmarks.meters import Campus


@dataclass
class EnergyUsePackage:
    root: Path
    campus: Campus | None = None
    column_map: dict[str, Any] = field(default_factory=dict)
    meter_frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    monthly_long: pd.DataFrame = field(default_factory=pd.DataFrame)
    notes: list[str] = field(default_factory=list)
    source: str = ""

    @property
    def lat(self) -> float | None:
        return None if self.campus is None else self.campus.lat

    @property
    def lon(self) -> float | None:
        return None if self.campus is None else self.campus.lon


def _unwrap_root(path: Path) -> Path:
    if path.is_file():
        return path
    kids = [p for p in path.iterdir() if not p.name.startswith(".")]
    if len(kids) == 1 and kids[0].is_dir():
        return kids[0]
    return path


def _extract_zip(zip_path: Path) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="energy_use_"))
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)
    return _unwrap_root(dest)


def normalize_column_map(doc: dict[str, Any]) -> dict[str, Any]:
    """Minimal Haystack-style normalize (equip/points or equipment/column_roles)."""
    out = dict(doc)
    out.setdefault("version", int(doc.get("version") or 1))
    equip_in = doc.get("equip") or doc.get("equipment") or doc.get("devices") or {}
    equipment: dict[str, Any] = {}
    for eid, info in (equip_in or {}).items():
        if not isinstance(info, dict):
            continue
        points = (
            info.get("points")
            or info.get("column_roles")
            or info.get("roles")
            or {}
        )
        equipment[str(eid)] = {
            "equipment_type": str(
                info.get("equipType") or info.get("equipment_type") or "METER"
            ).upper(),
            "device": str(info.get("device") or eid),
            "column_roles": {str(k): str(v) for k, v in dict(points).items()},
        }
    out["equipment"] = equipment
    if "meters" in doc and isinstance(doc["meters"], dict):
        out["meters"] = doc["meters"]
    return out


def _load_column_map(root: Path) -> dict[str, Any]:
    candidates = [
        root / "column_map.json",
        root / "bill_column_map.json",
        *sorted(root.glob("*column_map*.json")),
    ]
    interval = root / "interval"
    if interval.is_dir():
        candidates.extend(sorted(interval.glob("*column_map*.json")))
    for path in candidates:
        if path.is_file():
            try:
                return normalize_column_map(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    return {}


def _apply_roles(df: pd.DataFrame, roles: dict[str, str]) -> pd.DataFrame:
    out = df.copy()
    for point, col in roles.items():
        if col in out.columns and point not in out.columns:
            out[point] = pd.to_numeric(out[col], errors="coerce")
    return out


def _load_interval_frames(root: Path, column_map: dict[str, Any]) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    equip = column_map.get("equipment") or {}
    search_dirs = [root, root / "interval"]
    for d in search_dirs:
        if not d.is_dir():
            continue
        for csv in d.glob("*.csv"):
            if csv.name.lower().startswith("liberty") or "summary" in csv.name.lower():
                continue
            if csv.name.lower() in {"campus.json"}:
                continue
            try:
                df = pd.read_csv(csv)
            except Exception:
                continue
            if "timestamp_utc" not in df.columns and "timestamp" not in df.columns:
                continue
            roles: dict[str, str] = {}
            for info in equip.values():
                if isinstance(info, dict):
                    roles.update(info.get("column_roles") or {})
            frames[csv.stem] = _apply_roles(df, roles)
    return frames


def load_energy_use_package(path: str | Path) -> EnergyUsePackage:
    """Load a folder or zip containing campus bills and/or Haystack meter maps."""
    p = Path(path)
    notes: list[str] = []
    cleanup: Path | None = None
    if p.is_file() and p.suffix.lower() == ".zip":
        root = _extract_zip(p)
        cleanup = root if root.parent.name.startswith("energy_use_") else root.parent
        source = str(p)
    elif p.is_dir():
        root = _unwrap_root(p)
        source = str(p)
    else:
        raise FileNotFoundError(f"Energy-use package not found: {p}")

    try:
        campus = None
        campus_path = root / "campus.json"
        if campus_path.is_file():
            campus = Campus.from_json(campus_path)
            notes.append(f"Loaded campus.json ({campus.campus_id})")
        else:
            notes.append("No campus.json — monthly campus analytics unavailable until provided")

        column_map = _load_column_map(root)
        if column_map:
            notes.append("Loaded Haystack-style column_map")

        meter_frames = _load_interval_frames(root, column_map)
        if meter_frames:
            notes.append(f"Interval meter frames: {', '.join(sorted(meter_frames))}")

        monthly = meter_monthly_long(campus) if campus is not None else pd.DataFrame()

        return EnergyUsePackage(
            root=root,
            campus=campus,
            column_map=column_map,
            meter_frames=meter_frames,
            monthly_long=monthly,
            notes=notes,
            source=source,
        )
    finally:
        # Keep extracted tree for the session; caller may copy into workspace.
        # Only auto-clean if we want — for Studio we keep temp until process ends.
        _ = cleanup
        _ = shutil  # retained for future copy helpers


__all__ = [
    "EnergyUsePackage",
    "load_energy_use_package",
    "normalize_column_map",
]
