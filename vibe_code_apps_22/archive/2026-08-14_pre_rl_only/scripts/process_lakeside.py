#!/usr/bin/env python
"""ALC WebCTRL dump -> vibe19 openfdd_package_v1 + vibe20 meter package.

Every sensor is tagged with equip_id + ALC device_name so FDD findings can
drill down to the heat pump / plant / meter that owns zone temp, DAT, or fan.
"""
from __future__ import annotations


import sys
from pathlib import Path as _PathForLakeside

_APP = _PathForLakeside(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
from lakeside.paths import (  # noqa: E402
    BUILDING_LABEL,
    CAMPUS_ID,
    REGION_LABEL,
    app_root,
    clean_data_building_dir,
    eplus_dir,
    packages_dir,
    reports_dir,
    site_root,
    utilities_dir,
)
from lakeside.paths import BUILDING_ID as _LAKESIDE_BUILDING_ID  # noqa: E402
from lakeside.paths import SITE_REF as _LAKESIDE_SITE_REF  # noqa: E402
import json
import re
import shutil
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = site_root()
RAW = ROOT / "raw"
CLEAN = clean_data_building_dir()
PACKAGES = ROOT / "packages"
UTIL = ROOT / "utilities"
REPORTS = ROOT / "reports"
PLOTS = ROOT / "plots"

SITE_REF = "spasd_lakeside_es"
BUILDING_ID = "LAKESIDE_ES"
GRID = "5min"
TZ = "America/Chicago"

# ALC point title fragment -> (haystack role, csv column, group, sensor_kind)
POINT_MAP = {
    "zone temp": ("zone-air-temp", "zn_t", "HEAT_PUMP", "zone_temp"),
    "dat": ("discharge-air-temp", "da_t", "HEAT_PUMP", "discharge_air_temp"),
    "sup fan status": ("fan-status", "fan_s", "HEAT_PUMP", "fan_status"),
    "hp sup temp": ("leaving-water-temp", "hp_sup_t", "PLANT", "plant_supply_temp"),
    "hp ret temp": ("entering-water-temp", "hp_ret_t", "PLANT", "plant_return_temp"),
    "geo loop pres diff": ("differential-pressure", "geo_dp", "PLANT", "geo_pressure"),
    "oat sensor": ("outside-air-temp", "oa_t", "PLANT", "outside_air_temp"),
    "pump 1 s/s": ("pump-1-status", "pump1_s", "PLANT", "pump_status"),
    "pump 1 s_s": ("pump-1-status", "pump1_s", "PLANT", "pump_status"),
    "pump 2 s/s": ("pump-2-status", "pump2_s", "PLANT", "pump_status"),
    "pump 2 s_s": ("pump-2-status", "pump2_s", "PLANT", "pump_status"),
    "pump 1 vfd": ("pump-1-speed", "pump1_vfd", "PLANT", "pump_speed"),
    "pump 2 vfd": ("pump-2-speed", "pump2_vfd", "PLANT", "pump_speed"),
    "demand": ("elec-power", "kw_demand", "METER", "elec_demand_kw"),
}


@dataclass
class PointSeries:
    equip_id: str
    device_name: str  # ALC native name (e.g. "A100_Heat Pump 57")
    display_path: str  # Floor / Area / device
    floor: str
    area: str
    haystack: str
    csv_col: str
    sensor_kind: str
    group: str
    timestamps: list[pd.Timestamp] = field(default_factory=list)
    values: list[float] = field(default_factory=list)
    source: str = ""
    alc_title: str = ""


def _safe_id(text: str) -> str:
    t = re.sub(r"\s+", "_", text.strip())
    t = re.sub(r"[^A-Za-z0-9_\-]+", "", t)
    return re.sub(r"_+", "_", t).strip("_")[:80] or "UNKNOWN"


def _hp_equip_id(equip_raw: str) -> str:
    """Stable id that still encodes room + HP number for FDD drill-down."""
    raw = equip_raw.strip()
    m = re.search(r"(?i)(?:heat\s*pump|ht\s*pmp|h\s*p|hpu|hp)\s*[_\- ]*\s*(\d+)", raw)
    num = m.group(1) if m else None
    room = re.match(r"^([A-Za-z]?\d{2,4}[A-Za-z]?)", raw.replace(" ", ""))
    room_id = room.group(1) if room else None
    if not room_id:
        room_m = re.search(r"\b([A-D]\d{2,3}[A-Za-z]?)\b", raw)
        room_id = room_m.group(1) if room_m else None
    bits: list[str] = []
    if num:
        bits.append(f"HP{num}")
    if room_id:
        bits.append(room_id)
    if not bits:
        bits.append(_safe_id(raw))
    for hint in ("Cafe", "Kitchen", "IMC", "Data", "Stairs", "Corridor", "computer", "lab"):
        if re.search(hint, raw, re.I):
            bits.append(_safe_id(hint))
            break
    return _safe_id("_".join(bits))


def parse_title(title: str) -> dict[str, str]:
    parts = [p.strip() for p in title.strip().strip('"').split("/") if p.strip()]
    floor = area = equip = point = ""
    for i, p in enumerate(parts):
        if re.search(r"(?i)floor", p):
            floor = p
            if i + 1 < len(parts) and re.search(r"(?i)^area\b", parts[i + 1]):
                area = parts[i + 1]
        if re.search(r"(?i)heat\s*pump|ht\s*pmp|\bh\s*p\b|hpu|\bhp\b", p) or re.search(
            r"(?i)stairs|corridor|cafe|kitchen|computer\s*lab|data\s*room", p
        ):
            if i + 1 < len(parts):
                equip = p
        if re.search(r"(?i)ground\s*loop|outside\s*air|electric\s*meter", p):
            equip = p
    if not equip and len(parts) >= 2:
        equip = parts[-2]
    point = parts[-1]
    if len(parts) >= 2 and parts[-1].lower() == parts[-2].lower():
        point = parts[-1]
        if not equip or equip.lower() == point.lower():
            equip = parts[-3] if len(parts) >= 3 else equip
    return {
        "floor": floor or "Unknown Floor",
        "area": area or "Unknown Area",
        "equip_raw": equip or "Unknown Equip",
        "point": point,
        "title": title,
    }


def _lookup_point(point: str) -> tuple[str, str, str, str] | None:
    key = point.lower().replace("_", " ").strip()
    if key in POINT_MAP:
        return POINT_MAP[key]
    for k, v in POINT_MAP.items():
        if k in key or key in k:
            return v
    return None


def parse_alc_csv(path: Path) -> PointSeries | None:
    if "combined" in path.as_posix().lower():
        return None
    if path.stat().st_size == 0:
        return None
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    if len(lines) < 3:
        return None
    title = lines[0].strip().strip('"')
    meta = parse_title(title)
    mapped = _lookup_point(meta["point"])
    if mapped is None:
        print(f"  skip unmapped: {path.name} <- {meta['point']!r}")
        return None
    haystack, csv_col, group, sensor_kind = mapped

    df = pd.read_csv(path, skiprows=1, dtype=str)
    cols = {c.strip().strip('"').lower(): c for c in df.columns}
    date_col, val_col = cols.get("date"), cols.get("value")
    if not date_col or not val_col:
        return None

    dates = df[date_col].astype(str).str.strip().str.strip('"')
    cleaned = dates.str.replace(r"\s+(CDT|CST|EDT|EST|MDT|MST|PDT|PST)\s*$", "", regex=True)
    ts = pd.to_datetime(cleaned, format="mixed", errors="coerce")
    vals = pd.to_numeric(df[val_col].astype(str).str.strip().str.strip('"'), errors="coerce")
    mask = ts.notna() & vals.notna()
    ts, vals = ts[mask], vals[mask]
    if ts.empty:
        return None

    try:
        ts = ts.dt.tz_localize(TZ, ambiguous="infer", nonexistent="shift_forward")
    except Exception:
        ts = ts.dt.tz_localize(TZ, ambiguous="NaT", nonexistent="shift_forward")
        keep = ts.notna()
        ts, vals = ts[keep], vals[keep]
    ts = ts.dt.tz_convert("UTC")

    if group == "HEAT_PUMP":
        # Plant / meter hierarchy titles sometimes attach HP-like point names — force plant
        er = meta["equip_raw"].lower()
        if "ground loop" in er or "3 way" in er or "outside air" in er:
            equip_id = "GEO_LOOP"
            device_name = "Ground Loop Pumps and 3 Way Valve"
            group = "PLANT"
            # remap stray fan on plant if needed
            if haystack == "fan-status":
                haystack, csv_col, sensor_kind = "pump-status", "pump_s", "pump_status"
        else:
            equip_id = _hp_equip_id(meta["equip_raw"])
            device_name = meta["equip_raw"].strip()
    elif group == "PLANT":
        equip_id = "GEO_LOOP"
        device_name = "Ground Loop Pumps and 3 Way Valve"
    else:
        equip_id = "CS_ELEC_METER"
        device_name = "CS Electric Meter"

    display_path = " / ".join(
        p for p in (meta["floor"], meta["area"], device_name) if p and not p.startswith("Unknown")
    )
    if not display_path:
        display_path = device_name

    rel = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return PointSeries(
        equip_id=equip_id,
        device_name=device_name,
        display_path=display_path,
        floor=meta["floor"],
        area=meta["area"],
        haystack=haystack,
        csv_col=csv_col,
        sensor_kind=sensor_kind,
        group=group,
        timestamps=list(ts),
        values=list(vals.astype(float)),
        source=rel,
        alc_title=title,
    )


def extract_all_zips() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    zips: list[tuple[str, Path]] = []
    for z in sorted((ROOT / "HPs_1st_Floor").glob("*.zip")):
        zips.append((f"1st_{z.stem}", z))
    for z in sorted((ROOT / "HPs_2nd_Floor").glob("*.zip")):
        zips.append((f"2nd_{z.stem}", z))
    zips.append(("CentralPlant", ROOT / "CentralPlant.zip"))
    zips.append(("DemandCSV", ROOT / "DemandCSV.zip"))

    for key, zpath in zips:
        dest = RAW / key
        if dest.exists() and any(dest.rglob("*.csv")):
            print(f"extract skip (exists): {key}")
            continue
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True, exist_ok=True)
        print(f"extract {zpath.name} -> raw/{key}")
        with zipfile.ZipFile(zpath, "r") as zf:
            zf.extractall(dest)


def gather_points() -> list[PointSeries]:
    points: list[PointSeries] = []
    for csv in sorted(RAW.rglob("*.csv")):
        if "combined" in csv.as_posix().lower():
            continue
        ps = parse_alc_csv(csv)
        if ps:
            points.append(ps)
    return points


def merge_same_point(points: list[PointSeries]) -> list[PointSeries]:
    buckets: dict[tuple[str, str], PointSeries] = {}
    for p in points:
        key = (p.equip_id, p.haystack)
        if key not in buckets:
            buckets[key] = p
            continue
        b = buckets[key]
        b.timestamps.extend(p.timestamps)
        b.values.extend(p.values)
        b.source += f";{p.source}"
    out = []
    for p in buckets.values():
        df = pd.DataFrame({"timestamp_utc": p.timestamps, "v": p.values})
        df = df.dropna().sort_values("timestamp_utc").drop_duplicates("timestamp_utc", keep="last")
        p.timestamps = list(df["timestamp_utc"])
        p.values = list(df["v"])
        out.append(p)
    return out


def build_equip_frames(
    points: list[PointSeries],
) -> tuple[
    dict[str, pd.DataFrame],
    dict[str, dict[str, Any]],
    pd.DataFrame,
    pd.DataFrame,
    list[dict[str, Any]],
]:
    by_equip: dict[str, list[PointSeries]] = defaultdict(list)
    for p in points:
        by_equip[p.equip_id].append(p)

    frames: dict[str, pd.DataFrame] = {}
    meta: dict[str, dict[str, Any]] = {}
    catalog_rows: list[dict[str, Any]] = []
    zero_zone_rows: list[dict[str, Any]] = []

    for equip_id, pts in sorted(by_equip.items()):
        series_map: dict[str, pd.Series] = {}
        roles: dict[str, str] = {}
        kinds: dict[str, str] = {}
        group = pts[0].group
        device_name = pts[0].device_name
        display_path = pts[0].display_path
        floor = pts[0].floor
        area = pts[0].area

        for p in pts:
            s = pd.Series(p.values, index=pd.DatetimeIndex(p.timestamps, name="timestamp_utc"))
            s = s[~s.index.duplicated(keep="last")].sort_index()
            series_map[p.csv_col] = s
            roles[p.haystack] = p.csv_col
            kinds[p.csv_col] = p.sensor_kind
            catalog_rows.append(
                {
                    "equip_id": equip_id,
                    "device_name": p.device_name,
                    "display_path": p.display_path,
                    "floor": p.floor,
                    "area": p.area,
                    "equipment_type": group,
                    "haystack_point": p.haystack,
                    "csv_column": p.csv_col,
                    "sensor_kind": p.sensor_kind,
                    "alc_title": p.alc_title,
                    "source_files": p.source,
                    "n_raw_samples": len(p.values),
                }
            )
            # Capture zone-temp zeros from RAW samples (pre-grid) with device id
            if p.haystack == "zone-air-temp":
                for ts, val in zip(p.timestamps, p.values, strict=False):
                    if val == 0:
                        zero_zone_rows.append(
                            {
                                "timestamp_utc": ts,
                                "equip_id": equip_id,
                                "device_name": p.device_name,
                                "display_path": p.display_path,
                                "floor": p.floor,
                                "area": p.area,
                                "haystack_point": p.haystack,
                                "csv_column": p.csv_col,
                                "value": val,
                            }
                        )

        if not series_map:
            continue
        start = min(s.index.min() for s in series_map.values())
        end = max(s.index.max() for s in series_map.values())
        grid = pd.date_range(start.floor(GRID), end.ceil(GRID), freq=GRID, tz="UTC", name="timestamp_utc")
        wide = pd.DataFrame(index=grid)
        for col, s in series_map.items():
            if col in {"fan_s", "pump1_s", "pump2_s"}:
                wide[col] = s.reindex(grid).ffill().bfill()
            elif col.endswith("_vfd") or col == "kw_demand":
                wide[col] = s.reindex(grid).ffill(limit=12).bfill(limit=2)
            else:
                wide[col] = (
                    s.reindex(grid)
                    .interpolate(method="time", limit=6)
                    .ffill(limit=3)
                    .bfill(limit=3)
                )
        wide = wide.reset_index()
        frames[equip_id] = wide
        etype = {"HEAT_PUMP": "HEAT_PUMP", "PLANT": "PLANT", "METER": "METER"}[group]
        hs_type = {"HEAT_PUMP": "heatPump", "PLANT": "chwPlant", "METER": "meter"}[group]
        meta[equip_id] = {
            "equipment_type": etype,
            "equipType": hs_type,
            "device": device_name,
            "display_path": display_path,
            "floor": floor,
            "area": area,
            "group": group,
            "column_roles": roles,
            "sensor_kinds": kinds,
        }

    # Master long = melted 5-min frames (one row per equip x sensor x timestep)
    # with device_name on every row for FDD drill-down
    long_parts: list[pd.DataFrame] = []
    for equip_id, df in frames.items():
        m = meta[equip_id]
        melted = df.melt(id_vars=["timestamp_utc"], var_name="csv_column", value_name="value")
        melted = melted.dropna(subset=["value"])
        melted["equip_id"] = equip_id
        melted["device_name"] = m["device"]
        melted["display_path"] = m["display_path"]
        melted["floor"] = m["floor"]
        melted["area"] = m["area"]
        melted["group"] = m["group"]
        inv = {col: hs for hs, col in m["column_roles"].items()}
        melted["haystack_point"] = melted["csv_column"].map(inv)
        melted["sensor_kind"] = melted["csv_column"].map(m["sensor_kinds"])
        long_parts.append(melted)

    long_df = pd.concat(long_parts, ignore_index=True) if long_parts else pd.DataFrame()
    if not long_df.empty:
        long_df = long_df.sort_values(["equip_id", "csv_column", "timestamp_utc"]).reset_index(drop=True)

    catalog = pd.DataFrame(catalog_rows).sort_values(["equip_id", "sensor_kind"]).reset_index(drop=True)
    # stash zero rows on catalog attrs via return tuple extension - use reports write from main
    catalog.attrs["zero_zone_rows"] = zero_zone_rows
    return frames, meta, long_df, catalog, zero_zone_rows


def write_vibe19(
    frames: dict[str, pd.DataFrame],
    meta: dict[str, dict[str, Any]],
    catalog: pd.DataFrame,
) -> Path:
    if CLEAN.exists():
        shutil.rmtree(CLEAN)
    CLEAN.mkdir(parents=True)

    # Root Haystack map: device name is first-class for FDD UI / agent drill-down
    root_map: dict[str, Any] = {
        "version": 1,
        "building": BUILDING_ID,
        "siteRef": SITE_REF,
        "notes": (
            "equip keys are stable IDs (HP57_A100). "
            "device = ALC WebCTRL equipment name. "
            "display_path = Floor / Area / device for FDD drill-down."
        ),
        "equipment": {},
    }
    for eid, m in meta.items():
        root_map["equipment"][eid] = {
            "equipment_type": m["equipment_type"],
            "equipType": m["equipType"],
            "device": m["device"],
            "display_path": m["display_path"],
            "floor": m["floor"],
            "area": m["area"],
            "column_roles": m["column_roles"],
            "sensor_kinds": m["sensor_kinds"],
        }

    manifest = {
        "schema_version": "openfdd_package_v1",
        "building_id": BUILDING_ID,
        "grid_minutes": 5,
        "timezone": "UTC",
        "notes": "Lakeside ES ALC WebCTRL -> 5-min wide frames; see sensor_catalog.csv for device drill-down",
    }
    (CLEAN / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (CLEAN / "column_map.json").write_text(json.dumps(root_map, indent=2), encoding="utf-8")
    (CLEAN / "session_config.json").write_text(
        json.dumps(
            {
                "schema_version": "openfdd_session_v1",
                "unit_system": "imperial",
                "prefer_web_oat": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    catalog.to_csv(CLEAN / "sensor_catalog.csv", index=False)

    inventory = []
    for eid, df in sorted(frames.items()):
        ed = CLEAN / eid
        ed.mkdir(parents=True)
        out = df.copy()
        out["timestamp_utc"] = pd.to_datetime(out["timestamp_utc"], utc=True).dt.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        out.to_csv(ed / "history_wide.csv", index=False)
        m = meta[eid]
        side = {
            "equipType": m["equipType"],
            "device": m["device"],
            "display_path": m["display_path"],
            "floor": m["floor"],
            "area": m["area"],
            "points": m["column_roles"],
            "sensor_kinds": m["sensor_kinds"],
        }
        (ed / "history_wide.json").write_text(json.dumps(side, indent=2), encoding="utf-8")
        (ed / "column_map.json").write_text(
            json.dumps(
                {
                    "equipment_type": m["equipment_type"],
                    "equipType": m["equipType"],
                    "device": m["device"],
                    "display_path": m["display_path"],
                    "column_roles": m["column_roles"],
                    "sensor_kinds": m["sensor_kinds"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        # columns.csv: join key for analytics -> human device name
        cols = pd.DataFrame(
            [
                {
                    "column": col,
                    "point_role": hs,
                    "point_name": col,
                    "sensor_kind": m["sensor_kinds"].get(col, ""),
                    "equip_id": eid,
                    "device_name": m["device"],
                    "display_path": m["display_path"],
                    "units": "degF"
                    if "temp" in hs or hs.endswith("-temp")
                    else ("kW" if col == "kw_demand" else ""),
                }
                for hs, col in m["column_roles"].items()
            ]
        )
        cols.to_csv(ed / "columns.csv", index=False)
        inventory.append(
            {
                "equip_id": eid,
                "device_name": m["device"],
                "display_path": m["display_path"],
                "type": m["equipment_type"],
                "floor": m["floor"],
                "area": m["area"],
                "points": list(m["column_roles"].keys()),
                "sensor_kinds": list(m["sensor_kinds"].values()),
                "rows": len(df),
            }
        )

    (CLEAN / "equipment_inventory.json").write_text(
        json.dumps(inventory, indent=2), encoding="utf-8"
    )
    # Flat lookup: FDD equip_id + haystack -> device name
    lookup = catalog[
        ["equip_id", "device_name", "display_path", "haystack_point", "csv_column", "sensor_kind"]
    ].drop_duplicates()
    lookup.to_csv(CLEAN / "fdd_device_lookup.csv", index=False)
    return CLEAN


def build_zip(clean_root: Path) -> Path:
    PACKAGES.mkdir(parents=True, exist_ok=True)
    out = PACKAGES / f"{BUILDING_ID}_hvac_openfdd_package_v1.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in clean_root.rglob("*"):
            if f.is_file():
                arc = f"{BUILDING_ID}/{f.relative_to(clean_root).as_posix()}"
                zf.write(f, arcname=arc)
    print(f"wrote {out}")
    return out


def write_vibe20_from_demand(frames: dict[str, pd.DataFrame]) -> None:
    UTIL.mkdir(parents=True, exist_ok=True)
    meter = frames.get("CS_ELEC_METER")
    if meter is None or "kw_demand" not in meter.columns:
        print("warn: no demand meter for vibe20")
        return
    df = meter.copy()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.set_index("timestamp_utc").sort_index()
    df["kwh"] = df["kw_demand"] * (5.0 / 60.0)
    monthly = df["kwh"].resample("MS").sum().dropna()
    rows = [
        {"Bill Month": idx.strftime("%Y-%m"), "kWh Total": f"{val:,.2f}"}
        for idx, val in monthly.items()
        if val > 0
    ]
    pd.DataFrame(rows).to_csv(UTIL / "electricity.csv", index=False)
    campus = {
        "campus_id": "lakeside_es",
        "label": "Lakeside Elementary School",
        "siteRef": SITE_REF,
        "provenance": "alc_demand_integrated",
        "notes": (
            "Monthly kWh from integrating 5-min demand (kW * dt). "
            "Not billing-grade. floor_area_ft2 PLACEHOLDER. No gas in dump."
        ),
        "lat": 43.1839,
        "lon": -89.2137,
        "location": {"city": "southern Wisconsin", "climate_zone": "6A"},
        "buildings": [
            {
                "building_id": "lakeside_main",
                "label": "Lakeside Elementary School",
                "floor_area_ft2": 80000,
                "property_type": "k12_school",
                "notes": "PLACEHOLDER sf",
            }
        ],
        "meters": [
            {
                "meter_id": "elec_demand_integrated",
                "fuel": "electricity",
                "unit": "kwh",
                "file": "electricity.csv",
                "serves": ["lakeside_main"],
                "bill_columns": {"month": "Bill Month", "usage": "kWh Total"},
            }
        ],
    }
    (UTIL / "campus.json").write_text(json.dumps(campus, indent=2) + "\n", encoding="utf-8")
    (UTIL / "column_map.json").write_text(
        json.dumps(
            {
                "version": 1,
                "siteRef": SITE_REF,
                "meters": {
                    "elec_demand_integrated": {
                        "equipment_type": "METER",
                        "device": "CS Electric Meter",
                        "fuel": "electricity",
                        "unit": "kwh",
                        "file": "electricity.csv",
                        "column_roles": {
                            "month": "Bill Month",
                            "usage": "kWh Total",
                            "elec-energy": "kWh Total",
                        },
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    shutil.copy2(CLEAN / "CS_ELEC_METER" / "history_wide.csv", UTIL / "demand_interval_kw.csv")
    print(f"wrote vibe20 utilities ({len(rows)} months)")


def write_zero_zone_report(zero_rows: list[dict[str, Any]]) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "zone_temp_zero_rows.csv"
    z = pd.DataFrame(zero_rows)
    z.to_csv(out, index=False)
    print(f"zone_temp==0 rows: {len(z)} -> {out}")
    if not z.empty:
        summary = (
            z.groupby(["equip_id", "device_name", "display_path"], as_index=False)
            .agg(
                zero_rows=("value", "size"),
                first_ts=("timestamp_utc", "min"),
                last_ts=("timestamp_utc", "max"),
            )
            .sort_values("zero_rows", ascending=False)
        )
        summary.to_csv(REPORTS / "zone_temp_zero_by_equip.csv", index=False)
    return out


def write_master(long_df: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    # Prefer parquet for full long (includes device_name on every row)
    try:
        long_df.to_parquet(REPORTS / "master_long.parquet", index=False)
        print(f"master long parquet: {len(long_df):,} rows")
    except Exception as exc:
        print(f"long parquet failed ({exc})")
    # Always write a readable sample + full csv if small enough
    long_df.head(20000).to_csv(REPORTS / "master_long_sample.csv", index=False)
    if len(long_df) <= 3_000_000:
        long_df.to_csv(REPORTS / "master_long.csv", index=False)
        print(f"master long csv: {len(long_df):,} rows")
    else:
        print(f"master long csv skipped (too large: {len(long_df):,}); use parquet")

    pieces = []
    for eid, df in frames.items():
        d = df.copy()
        d["timestamp_utc"] = pd.to_datetime(d["timestamp_utc"], utc=True)
        d = d.set_index("timestamp_utc").add_prefix(f"{eid}__")
        pieces.append(d)
    if not pieces:
        return
    master = pd.concat(pieces, axis=1, join="outer").sort_index()
    try:
        master.to_parquet(REPORTS / "master_wide.parquet")
        print(f"master wide parquet: {master.shape}")
    except Exception as exc:
        print(f"wide parquet failed ({exc}); writing csv")
        master.reset_index().to_csv(REPORTS / "master_wide.csv", index=False)


def plot_sensors(frames: dict[str, pd.DataFrame], meta: dict[str, dict[str, Any]]) -> None:
    if PLOTS.exists():
        shutil.rmtree(PLOTS)
    PLOTS.mkdir(parents=True)
    n = 0
    for eid, df in sorted(frames.items()):
        cols = [c for c in df.columns if c != "timestamp_utc"]
        if not cols:
            continue
        ts = pd.to_datetime(df["timestamp_utc"], utc=True)
        fig, axes = plt.subplots(len(cols), 1, figsize=(11, 2.2 * len(cols)), sharex=True)
        if len(cols) == 1:
            axes = [axes]
        for ax, col in zip(axes, cols, strict=True):
            ax.plot(ts, df[col], lw=0.6)
            kind = meta[eid]["sensor_kinds"].get(col, col)
            ax.set_ylabel(f"{col}\n({kind})")
            ax.grid(True, alpha=0.3)
        fig.suptitle(f"{eid} | {meta[eid]['device']} | {meta[eid]['display_path']}", fontsize=10)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(PLOTS / f"{eid}.png", dpi=110)
        plt.close(fig)
        n += 1
    print(f"plots: {n} -> {PLOTS}")


def validate_vibe19_zip(zip_path: Path) -> None:
    v19 = Path(r"C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_19")
    if not v19.is_dir():
        print("vibe19 not found - skip validate")
        return
    import sys

    sys.path.insert(0, str(v19))
    from app.package_io import load_package_zip

    result = load_package_zip(zip_path.read_bytes())
    print(
        f"vibe19 validate: equip={len(result.frames)} "
        f"building={result.manifest.building_id} "
        f"map_issues={len(getattr(result, 'column_map_issues', []) or [])}"
    )


def validate_vibe20() -> None:
    """Optional local check via cloned Campus (no wattlab import)."""
    if not (UTIL / "campus.json").is_file():
        return
    from eplus_gym_app.campus_fuel import Campus

    c = Campus.from_json(UTIL / "campus.json")
    print(
        f"campus validate: meters={len(c.meters)} fuels={c.fuel_kinds()} "
        f"months={len(c.meters[0].bills) if c.meters else 0}"
    )


def main() -> int:
    print(f"ROOT={ROOT}")
    extract_all_zips()
    print("parsing ALC CSVs...")
    points = gather_points()
    print(f"raw point files parsed: {len(points)}")
    points = merge_same_point(points)
    print(f"unique equip+point series: {len(points)}")
    frames, meta, long_df, catalog, zero_zone = build_equip_frames(points)
    print(f"equipment folders: {len(frames)}")
    by_type: dict[str, int] = defaultdict(int)
    for m in meta.values():
        by_type[m["equipment_type"]] += 1
    print("by type:", dict(by_type))
    print(f"sensor catalog rows: {len(catalog)}")

    write_vibe19(frames, meta, catalog)
    REPORTS.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(REPORTS / "sensor_catalog.csv", index=False)
    write_zero_zone_report(zero_zone)
    write_master(long_df, frames)
    plot_sensors(frames, meta)
    write_vibe20_from_demand(frames)
    zpath = build_zip(CLEAN)
    validate_vibe19_zip(zpath)
    validate_vibe20()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
