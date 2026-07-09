"""Export vibe19 Haystack historian → open-fdd telemetry_pivot.jsonl format.

Writes pivot rows that open-fdd edge can load into DataFusion via historian/store.rs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

import cookbook_engine as ce

_HERE = Path(__file__).resolve().parent

# vibe19 logical role → open-fdd telemetry_pivot column (when names differ)
_ROLE_TO_OPENFDD: dict[str, str] = {
    "zone_t": "zn_t",
    "vav_disch_t": "duct_t",
    "oa_h": "oa_h",
}

# Roles exported as-is (same name in both systems)
_DIRECT_ROLES = frozenset({
    "oa_t", "sat", "sat_sp", "fan_cmd", "mat", "rat", "damper_pct",
    "reheat_valve_pct", "zone_flow", "min_flow_sp", "duct_static",
    "clg_valve_pct", "htg_valve_pct", "oa_damper_pct", "chw_supply_t",
    "chw_return_t", "hw_supply_t", "hw_return_t", "wind_speed", "wind_gust",
})


def _workspace_root() -> Path:
    env = os.environ.get("OPENFDD_WORKSPACE")
    if env:
        return Path(env)
    # Default: sibling open-fdd workspace if present, else local export dir
    sibling = _HERE.parent.parent.parent / "open-fdd" / "workspace"
    if sibling.is_dir():
        return sibling
    return _HERE.parent / "backend" / ".cache" / "openfdd_export"


def historian_subdir() -> str:
    return os.environ.get("OPENFDD_HISTORIAN_SUBDIR", "vibe19_building100")


def export_dir() -> Path:
    return _workspace_root() / "data" / "historian" / historian_subdir()


def _kind_for_equipment(equipment_id: str, resolver) -> str:
    try:
        for eq in resolver.list_equipment():
            if eq["id"] == equipment_id:
                tags = (eq.get("haystack_tag") or "").lower()
                if "vav" in tags:
                    return "vav"
                if "chiller" in tags:
                    return "chiller"
                if "boiler" in tags:
                    return "boiler"
                if equipment_id == "WEATHER":
                    return "weather"
        if equipment_id in resolver.list_ahus():
            return "ahu"
    except Exception:
        pass
    if equipment_id.startswith("VAV"):
        return "vav"
    if "CHILLER" in equipment_id:
        return "chiller"
    if "BOILER" in equipment_id:
        return "boiler"
    if equipment_id == "WEATHER":
        return "weather"
    return "ahu"


def _row_from_frame(equipment_id: str, d: pd.DataFrame, resolved: dict) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if "timestamp" not in d.columns:
        return rows
    ts = pd.to_datetime(d["timestamp"])
    for i in range(len(d)):
        row: dict[str, Any] = {
            "timestamp": ts.iloc[i].isoformat(),
            "equipment_id": equipment_id,
            "source": "vibe19_export",
        }
        for role, col in resolved.items():
            if not col or col not in d.columns:
                continue
            val = d[col].iloc[i]
            if pd.isna(val):
                continue
            if role in ("fan_cmd", "fan_status", "occ_mode"):
                try:
                    row["fan_cmd"] = float(val) if role == "fan_cmd" else row.get("fan_cmd")
                except (TypeError, ValueError):
                    pass
                continue
            try:
                num = float(val)
            except (TypeError, ValueError):
                continue
            out_key = _ROLE_TO_OPENFDD.get(role, role if role in _DIRECT_ROLES else role)
            if role == "fan_cmd":
                num = num / 100.0 if num > 1.0 else num
            row[out_key] = round(num, 4)
        rows.append(row)
    return rows


def export_equipment(equipment_id: str, *, resolver=None, weather: pd.DataFrame | None = None) -> int:
    """Export one equipment's logical frame to pivot rows. Returns row count."""
    if resolver is None:
        from haystack_rdf.resolver import get_resolver
        resolver = get_resolver()
    if weather is None:
        weather = ce.load_weather(resolver)
    kind = _kind_for_equipment(equipment_id, resolver)
    try:
        d, resolved, _poll, _wx = ce.build_logical_frame(equipment_id, kind, resolver, weather)
    except Exception:
        return 0
    return len(_row_from_frame(equipment_id, d, resolved))


def export_all(*, resolver=None, equipment_ids: list[str] | None = None) -> dict[str, Any]:
    """Export all (or selected) equipment histories to open-fdd historian directory."""
    if resolver is None:
        from haystack_rdf.resolver import get_resolver
        resolver = get_resolver()

    if equipment_ids is None:
        equipment_ids = []
        try:
            equipment_ids.extend(sorted(resolver.list_ahus()))
            equipment_ids.extend(
                sorted(e["id"] for e in resolver.list_equipment(haystack_tag="vav"))
            )
            for tag in ("chiller",):
                equipment_ids.extend(sorted(e["id"] for e in resolver.list_equipment(haystack_tag=tag)))
            for eq in resolver.list_equipment():
                if "BOILER" in eq["id"].upper() and eq["id"] not in equipment_ids:
                    equipment_ids.append(eq["id"])
            if "WEATHER" not in equipment_ids:
                equipment_ids.append("WEATHER")
        except Exception:
            equipment_ids = ["AHU_1", "AHU_2", "WEATHER"]

    weather = ce.load_weather(resolver)
    all_rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for eq_id in equipment_ids:
        kind = _kind_for_equipment(eq_id, resolver)
        try:
            d, resolved, _poll, _wx = ce.build_logical_frame(eq_id, kind, resolver, weather)
            all_rows.extend(_row_from_frame(eq_id, d, resolved))
        except Exception as exc:
            errors.append(f"{eq_id}: {exc}")

    dest = export_dir()
    dest.mkdir(parents=True, exist_ok=True)
    jsonl_path = dest / "telemetry_pivot.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for row in all_rows:
            fh.write(json.dumps(row, default=str) + "\n")

    arrow_path = dest / "telemetry_pivot.arrow"
    _write_arrow(all_rows, arrow_path)

    meta = {
        "ok": True,
        "equipment_count": len(equipment_ids),
        "row_count": len(all_rows),
        "path": str(jsonl_path),
        "arrow_path": str(arrow_path) if arrow_path.is_file() else None,
        "historian_subdir": historian_subdir(),
        "data_token": ce._data_token(),
        "errors": errors,
    }
    (dest / "export_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def _write_arrow(rows: list[dict[str, Any]], path: Path) -> None:
    """Optional Arrow IPC sidecar for DuckDB / open-fdd columnar loads."""
    if not rows:
        return
    try:
        import pyarrow as pa
        import pyarrow.ipc as ipc
    except ImportError:
        return
    try:
        table = pa.Table.from_pylist(rows)
        with path.open("wb") as fh:
            with ipc.new_file(fh, table.schema) as writer:
                writer.write_table(table)
    except (OSError, ValueError, pa.ArrowInvalid):
        pass


def needs_export() -> bool:
    """True if export is missing or data_token changed."""
    dest = export_dir()
    meta_path = dest / "export_meta.json"
    jsonl_path = dest / "telemetry_pivot.jsonl"
    if not meta_path.is_file() or not jsonl_path.is_file():
        return True
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return meta.get("data_token") != ce._data_token()
    except (OSError, json.JSONDecodeError):
        return True
