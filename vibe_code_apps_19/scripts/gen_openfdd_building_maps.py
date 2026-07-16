"""Generate openfdd_package_v1 JSON maps for BUILDING_100 and BUILDING_50.

- Writes per-equipment column_map.json + root column_map.json + session_config.json
- Nests weather/ inside each building (aligned to AHU timestamp grid)
- Validates with load_package_from_dir

Usage (from vibe_code_apps_19):
  python scripts/gen_openfdd_building_maps.py
  python scripts/gen_openfdd_building_maps.py --buildings BUILDING_100
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent_api import make_session_config
from app.column_map_json import (
    COOKBOOK_TO_HAYSTACK_POINT,
    build_column_map_from_equipment_frames,
    column_map_to_role_map,
)
from app.data_loader import discover_equipment
from app.package_io import PackageManifest, SessionConfig, load_package_from_dir
from app.site_model import equipment_type_from_id

DEFAULT_SRC = Path(
    r"C:\Users\ben\OneDrive\Desktop\testing\tadco_openfdd_sidecar"
    r"\workspace\imports\hvac_systems_CLEANED"
)


def _hs_equip_type(eq_id: str, cookbook_type: str) -> str:
    et = (cookbook_type or "").lower()
    if "CHILLER" in eq_id.upper():
        return "chwPlant"
    if "BOILER" in eq_id.upper():
        return "boiler"
    return {
        "ahu": "ahu",
        "vav": "vav",
        "chiller": "chwPlant",
        "boiler": "boiler",
        "heatpump": "heatPump",
        "pump": "pump",
    }.get(et, et or "unknown")


def _reference_timestamps(bldg: Path) -> pd.Series:
    for cand in (bldg / "AHU_1" / "history_wide.csv", bldg / "AHU_2" / "history_wide.csv"):
        if cand.is_file():
            return pd.read_csv(cand, usecols=["timestamp_utc"])["timestamp_utc"]
    raise FileNotFoundError(f"No AHU history_wide.csv under {bldg}")


def nest_weather_aligned(src_weather: Path, bldg: Path) -> dict:
    """Copy weather into building and reindex to exact AHU timestamp grid."""
    src_csv = src_weather / "history_wide.csv"
    if not src_csv.is_file():
        raise FileNotFoundError(src_csv)

    dest = bldg / "weather"
    dest.mkdir(parents=True, exist_ok=True)

    ref_ts = _reference_timestamps(bldg)
    wx = pd.read_csv(src_csv)
    if "timestamp_utc" not in wx.columns:
        raise ValueError(f"weather missing timestamp_utc: {src_csv}")

    # Exact string match first (CLEANED grids already aligned)
    if list(wx["timestamp_utc"]) == list(ref_ts):
        aligned = wx.copy()
        mode = "exact_match"
    else:
        ref = pd.to_datetime(ref_ts, utc=True)
        w = wx.copy()
        w["timestamp_utc"] = pd.to_datetime(w["timestamp_utc"], utc=True)
        w = w.drop_duplicates("timestamp_utc").set_index("timestamp_utc").sort_index()
        value_cols = [c for c in w.columns]
        for c in value_cols:
            w[c] = pd.to_numeric(w[c], errors="coerce")
        combined = w.reindex(w.index.union(ref)).sort_index()
        for c in value_cols:
            combined[c] = combined[c].interpolate(method="time", limit_direction="both")
        aligned = combined.reindex(ref).reset_index()
        aligned["timestamp_utc"] = (
            aligned["timestamp_utc"]
            .dt.strftime("%Y-%m-%d %H:%M:%S%z")
            .str.replace(r"(\+\d{2})(\d{2})$", r"\1:\2", regex=True)
        )
        mode = "reindexed"

    out_csv = dest / "history_wide.csv"
    aligned.to_csv(out_csv, index=False)

    src_cols = src_weather / "columns.csv"
    if src_cols.is_file():
        shutil.copy2(src_cols, dest / "columns.csv")

    ts = pd.to_datetime(aligned["timestamp_utc"], utc=True)
    report = {
        "mode": mode,
        "rows": len(aligned),
        "earliest_utc": str(ts.iloc[0]),
        "latest_utc": str(ts.iloc[-1]),
        "nan_cells": int(aligned.drop(columns=["timestamp_utc"]).isna().sum().sum()),
        "timestamps_match_ahu": list(aligned["timestamp_utc"]) == list(ref_ts),
    }
    (dest / "manifest.json").write_text(
        json.dumps(
            {
                "location_id": "WX_SITE_01",
                "coordinates_redacted": True,
                "aligned_to_building": True,
                "interval_minutes": 5,
                "validation": report,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def process_building(src: Path, building_id: str) -> None:
    bldg = src / building_id
    wx = src / "weather"
    assert bldg.is_dir(), bldg
    assert wx.is_dir(), wx

    print(f"\n=== {building_id} ===")

    old_manifest: dict = {}
    mp = bldg / "manifest.json"
    if mp.is_file():
        old_manifest = json.loads(mp.read_text(encoding="utf-8"))
        bak = bldg / "manifest.sidecar_backup.json"
        if not bak.is_file():
            bak.write_text(json.dumps(old_manifest, indent=2) + "\n", encoding="utf-8")
            print("backed up manifest ->", bak.name)

    wx_report = nest_weather_aligned(wx, bldg)
    print(
        f"weather nested: rows={wx_report['rows']} mode={wx_report['mode']} "
        f"match_ahu={wx_report['timestamps_match_ahu']} nan={wx_report['nan_cells']}"
    )
    print(f"  {wx_report['earliest_utc']} -> {wx_report['latest_utc']}")

    manifest = {
        "schema_version": "openfdd_package_v1",
        "building_id": building_id,
        "grid_minutes": int(old_manifest.get("grid_minutes", 5)),
        "timezone": "UTC",
        "notes": (
            f"TADCO {building_id} cleaned historian + nested weather. "
            f"site_id={old_manifest.get('site_id', '')}"
        ),
        "site_id": old_manifest.get("site_id", "COMMERCIAL_SITE_A"),
        "weather": "weather/history_wide.csv",
        "weather_location_id": old_manifest.get("weather_location_id", "WX_SITE_01"),
    }
    PackageManifest.model_validate(manifest)
    mp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("wrote", mp)

    equip = discover_equipment(bldg)
    print(f"equipment discovered: {len(equip)}")
    frames: dict[str, pd.DataFrame] = {}
    for eq in equip:
        hist = Path(eq["history_path"])
        cols_path = eq.get("columns_path")
        header = pd.read_csv(hist, nrows=0)
        df = pd.DataFrame(columns=list(header.columns))
        df.attrs["equipment_id"] = eq["equipment_id"]
        df.attrs["columns_path"] = str(cols_path) if cols_path else None
        df.attrs["equipment_type"] = equipment_type_from_id(eq["equipment_id"])
        frames[eq["equipment_id"]] = df

    pkg_map = build_column_map_from_equipment_frames(
        frames,
        building_id=building_id,
        site_ref=str(old_manifest.get("site_id") or "COMMERCIAL_SITE_A"),
        generated_by="heuristic_columns_csv",
    )

    written = 0
    empty: list[str] = []
    for eq in equip:
        eq_id = eq["equipment_id"]
        block = (pkg_map.get("equipment") or {}).get(eq_id) or {}
        roles = dict(block.get("column_roles") or {})
        if not roles:
            empty.append(eq_id)
        points = {
            COOKBOOK_TO_HAYSTACK_POINT.get(role, role.replace("_", "-")): col
            for role, col in sorted(roles.items())
        }
        cookbook_type = str(block.get("equipment_type") or equipment_type_from_id(eq_id))
        payload = {
            "equipType": _hs_equip_type(eq_id, cookbook_type),
            "device": eq_id,
            "equipment_type": cookbook_type,
            "points": points,
            "column_roles": roles,
            "generated_by": "heuristic_columns_csv",
            "notes": "Auto from columns.csv + header heuristics; refine in UI if needed.",
        }
        out = Path(eq["folder"]) / "column_map.json"
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        written += 1
    print(f"wrote {written} column_map.json sidecars; empty_roles={len(empty)}")
    if empty:
        print("  empty:", ", ".join(empty[:12]), ("..." if len(empty) > 12 else ""))

    root_cm = bldg / "column_map.json"
    root_cm.write_text(json.dumps(pkg_map, indent=2) + "\n", encoding="utf-8")
    print("wrote", root_cm.name)

    role_map = column_map_to_role_map(pkg_map)
    session = make_session_config(
        role_map,
        {},
        unit_system="imperial",
        prefer_web_oat=True,
        chw_leave_max_f=48.0,
        include_ahu_chw_valve=False,
    )
    SessionConfig.model_validate(session)
    scp = bldg / "session_config.json"
    scp.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
    print("wrote", scp.name, "equip in role_map:", len(role_map))

    result = load_package_from_dir(bldg)
    print(
        f"validate OK: frames={len(result.frames)} weather={result.weather is not None} "
        f"session={result.session_config is not None}"
    )

    for k in ("AHU_1", "AHU_2", "CHILLER_2", "BOILERS_PUMPS"):
        roles = role_map.get(k, {})
        preview = {
            r: roles.get(r)
            for r in (
                "discharge-air-temp",
                "outside-air-temp",
                "fan-status",
                "mixed-air-temp",
                "return-air-temp",
                "cooling-valve",
                "chilled-water-supply-temp",
                "hot-water-supply-temp",
                "duct-static-pressure",
            )
            if roles.get(r)
        }
        if preview:
            print(f"  {k} -> {preview}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument(
        "--buildings",
        nargs="*",
        default=["BUILDING_100", "BUILDING_50"],
    )
    args = parser.parse_args()

    for bid in args.buildings:
        process_building(args.src, bid)

    print("\nAll buildings done.")


if __name__ == "__main__":
    main()
