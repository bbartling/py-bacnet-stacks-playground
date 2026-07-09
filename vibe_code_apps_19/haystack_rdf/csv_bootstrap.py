"""Bootstrap Haystack model.json from external CSV tree."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from shared.data_config import DataConfig, get_config

from .csv_discovery import HistorianBundle, discover_historian_bundles
from .model_store import ModelStore
from .ttl_service import TtlService


def _equip_type_from_folder(name: str, history_subdir: str) -> str:
    upper = name.upper()
    if upper.startswith("AHU"):
        return "AHU"
    if upper.startswith("CHILLER"):
        return "CHILLER"
    if "BOILER" in upper:
        return "BOILER"
    if upper.startswith("VAV") or "/VAV/" in history_subdir.upper() or history_subdir.upper().startswith("VAV/"):
        return "VAV"
    return "EQUIP"


def _haystack_tag(equip_type: str) -> str:
    return {
        "AHU": "ahu",
        "VAV": "vav",
        "CHILLER": "chiller",
        "BOILER": "boiler",
        "WEATHER": "weatherStation",
    }.get(equip_type, "equip")


def _read_columns(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append({k: str(v or "") for k, v in row.items()})
    return rows


def _load_vav_feeds(building_dir: Path) -> dict[str, list[str]]:
    """Map AHU id -> list of VAV ids from vav_to_ahu_simple.csv."""
    path = building_dir / "vav_to_ahu_simple.csv"
    if not path.is_file():
        return {}
    feeds: dict[str, list[str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            vav = str(row.get("vav_id") or row.get("VAV_ID") or row.get("vav") or "").strip()
            ahu = str(row.get("ahu_id") or row.get("AHU_ID") or row.get("ahu") or "").strip()
            if not vav or not ahu:
                continue
            feeds.setdefault(ahu, []).append(vav)
    return feeds


def _apply_economizer_bindings(model: dict[str, Any], econ_map: dict[str, dict[str, str | None]]) -> None:
    """Attach all FDD logical keys per historian column (supports alias roles)."""
    by_eq_col: dict[tuple[str, str], list[str]] = {}
    for eq_id, mapping in econ_map.items():
        for logical, col in mapping.items():
            if not col or logical in ("notes", "mad_cmd", "timestamp"):
                continue
            by_eq_col.setdefault((eq_id, col), [])
            if logical not in by_eq_col[(eq_id, col)]:
                by_eq_col[(eq_id, col)].append(logical)
    for pt in model.get("points") or []:
        if not isinstance(pt, dict):
            continue
        key = (str(pt.get("equipment_id") or ""), str(pt.get("column") or ""))
        roles = by_eq_col.get(key)
        if not roles:
            continue
        pt["rule_inputs"] = roles
        pt["fdd_input"] = roles[0]
        if not pt.get("point_role"):
            pt["point_role"] = roles[0]


def _load_economizer_logical_map(dashboard_root: Path) -> dict[str, dict[str, str | None]]:
    path = dashboard_root / "economizer_point_mapping.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str | None]] = {}
    for ahu_id, mapping in (data.get("ahu_mappings") or {}).items():
        if isinstance(mapping, dict):
            out[str(ahu_id)] = {str(k): (str(v) if v is not None else None) for k, v in mapping.items()}
    return out


def _append_equipment_points(
    model: dict[str, Any],
    *,
    site_id: str,
    bundle: HistorianBundle,
    econ_map: dict[str, dict[str, str | None]],
    vav_feeds: dict[str, list[str]],
    equip_type_override: str | None = None,
) -> None:
    eq_id = bundle.equipment_id
    equip_type = equip_type_override or _equip_type_from_folder(eq_id, bundle.history_subdir)
    haystack_tag = _haystack_tag(equip_type)
    entry: dict[str, Any] = {
        "id": eq_id,
        "name": eq_id.replace("_", " "),
        "site_id": site_id,
        "equipment_type": equip_type,
        "haystack_tag": haystack_tag,
        "history_subdir": bundle.history_subdir,
    }
    if equip_type == "AHU":
        entry["feeds"] = list(vav_feeds.get(eq_id, []))
    model["equipment"].append(entry)

    logical = econ_map.get(eq_id, {})
    col_to_logical = {v: k for k, v in logical.items() if v}
    for row in _read_columns(bundle.columns_path):
        col = row.get("column") or row.get("col") or ""
        if not col or col == "timestamp_utc":
            continue
        role = row.get("point_role") or col_to_logical.get(col, "")
        pt_id = f"{eq_id}__{col}"
        model["points"].append(
            {
                "id": pt_id,
                "name": row.get("point_name") or col,
                "site_id": site_id,
                "equipment_id": eq_id,
                "column": col,
                "timeseries_column": col,
                "point_role": role,
                "fdd_input": col_to_logical.get(col) or role,
                "unit": row.get("units") or "",
            }
        )


def build_model_from_csv(
    cfg: DataConfig | None = None,
    *,
    dashboard_root: Path | None = None,
) -> dict[str, Any]:
    """Walk building + weather CSV tree recursively → Haystack commissioning JSON."""
    cfg = cfg or get_config()
    building = cfg.building
    bdir = cfg.building_dir
    site_id = re.sub(r"[^A-Za-z0-9_]+", "_", building).strip("_") or "site"

    model: dict[str, Any] = {
        "version": 1,
        "sites": [{"id": site_id, "name": cfg.site_label()}],
        "equipment": [],
        "points": [],
    }

    econ_map = _load_economizer_logical_map(dashboard_root or Path(__file__).resolve().parent.parent / "fdd_app" / "backend")
    vav_feeds = _load_vav_feeds(bdir)

    for bundle in discover_historian_bundles(bdir, building_dir=bdir):
        _append_equipment_points(
            model,
            site_id=site_id,
            bundle=bundle,
            econ_map=econ_map,
            vav_feeds=vav_feeds,
        )

    for bundle in discover_historian_bundles(cfg.weather_dir):
        _append_equipment_points(
            model,
            site_id=site_id,
            bundle=bundle,
            econ_map=econ_map,
            vav_feeds=vav_feeds,
            equip_type_override="WEATHER",
        )
        model["equipment"][-1]["id"] = "WEATHER"
        model["equipment"][-1]["name"] = "Weather reference"
        model["equipment"][-1]["history_subdir"] = "../weather"
        for pt in model["points"]:
            if pt.get("equipment_id") == bundle.equipment_id:
                pt["equipment_id"] = "WEATHER"
                pt["id"] = pt["id"].replace(f"{bundle.equipment_id}__", "WEATHER__", 1)

    _apply_economizer_bindings(model, econ_map)
    return model


def bootstrap_and_sync(cfg: DataConfig | None = None, *, force: bool = False) -> Path:
    """Build model.json from CSV if missing (or force), then sync TTL."""
    cfg = cfg or get_config()
    store = ModelStore()
    if force or not store.path.is_file() or not store.load().get("equipment"):
        model = build_model_from_csv(cfg)
        store.save(model)
    ttl = TtlService(model_store=store)
    return ttl.sync()
