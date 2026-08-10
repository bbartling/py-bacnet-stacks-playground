"""Build versioned real BAS 15-minute feature store for hybrid baseline training.

Sources (measured only — never EnergyPlus):
  - reports/master_long.parquet (5-min zn_t / oa_t)
  - utilities/demand_interval_kw.csv (5-min facility kW)
  - reports/thermal_zone_model.json (HP → 6 areas + K-12 schedule)
  - clean_data/.../weather/history_wide.csv (OAT/RH/GHI)

Fail-closed on empty zone coverage or unresolved area IDs.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

AREA_ZONE_IDS = [
    "1F_Area_A",
    "1F_Area_B",
    "1F_Area_C",
    "1F_Area_D",
    "2F_Area_A",
    "2F_Area_B",
]

ZONE_TEMP_COLS = [
    "zone_temp_1F_A_f",
    "zone_temp_1F_B_f",
    "zone_temp_1F_C_f",
    "zone_temp_1F_D_f",
    "zone_temp_2F_A_f",
    "zone_temp_2F_B_f",
]

_ZONE_TO_TEMP = dict(zip(AREA_ZONE_IDS, ZONE_TEMP_COLS))

STORE_STEM = "real_baseline_15min_v1"
TZ = "America/Chicago"
PROVENANCE = "REAL_BAS_15MIN"


def real_store_paths(site: Path) -> dict[str, Path]:
    art = site / "ml" / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    return {
        "parquet": art / f"{STORE_STEM}.parquet",
        "schema": art / f"{STORE_STEM}_schema.json",
        "manifest": art / f"{STORE_STEM}_build_manifest.json",
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_zone_equip_map(zone_json: Path) -> dict[str, str]:
    """Map equip_id → zone_id from thermal_zone_model.json. Fail closed if empty."""
    if not zone_json.is_file():
        raise FileNotFoundError(f"missing zone map {zone_json}")
    doc = json.loads(zone_json.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    unresolved_labels: list[str] = []
    for floor in doc.get("floors", []):
        for z in floor.get("thermal_zones", []):
            zid = str(z.get("zone_id", ""))
            if zid not in AREA_ZONE_IDS:
                unresolved_labels.append(zid or repr(z.get("label")))
                continue
            for hp in z.get("heat_pumps", []):
                eid = str(hp.get("equip_id", "")).strip()
                if eid:
                    mapping[eid] = zid
    if unresolved_labels:
        bad = sorted({u for u in unresolved_labels if u})
        raise ValueError(f"unresolved area IDs in zone map: {bad}")
    if not mapping:
        raise ValueError("empty zone coverage — no equip_id→zone_id mappings")
    for zid in AREA_ZONE_IDS:
        if zid not in mapping.values():
            raise ValueError(f"zone {zid} has no heat pumps in zone map")
    return mapping


def _floor_area_to_zone(floor: str, area: str) -> str | None:
    fl = str(floor).strip().lower()
    ar = str(area).strip().lower().replace(" ", "_")
    prefix = None
    if "first" in fl or fl.startswith("1"):
        prefix = "1F"
    elif "second" in fl or fl.startswith("2"):
        prefix = "2F"
    if not prefix:
        return None
    # Area A → Area_A
    if ar.startswith("area_"):
        letter = ar.split("_", 1)[-1].upper()
    elif ar.startswith("area "):
        letter = ar.split()[-1].upper()
    else:
        letter = ar.replace("area", "").strip("_").upper()
    if letter not in ("A", "B", "C", "D"):
        return None
    zid = f"{prefix}_Area_{letter}"
    return zid if zid in AREA_ZONE_IDS else None


def _occupied_from_schedule(local: pd.Series, schedule: dict[str, Any]) -> pd.Series:
    """K-12 weekday window from zone JSON (causal calendar feature)."""
    days = {d[:3].title() for d in schedule.get("occupied_days", ["Mon", "Tue", "Wed", "Thu", "Fri"])}
    start = schedule.get("occupied_start_local", "07:00")
    end = schedule.get("occupied_end_local", "16:00")
    sh, sm = [int(x) for x in str(start).split(":")[:2]]
    eh, em = [int(x) for x in str(end).split(":")[:2]]
    start_m = sh * 60 + sm
    end_m = eh * 60 + em
    dow = local.dt.day_name().str[:3]
    mins = local.dt.hour * 60 + local.dt.minute
    return ((dow.isin(days)) & (mins >= start_m) & (mins < end_m)).astype(float)


def _resample_15min_mean(s: pd.Series) -> pd.Series:
    return s.resample("15min", label="right", closed="right").mean()


def build_real_15min_store(
    site: Path,
    *,
    out_dir: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    site = Path(site)
    paths = real_store_paths(site if out_dir is None else Path(out_dir).parent.parent)
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "parquet": out_dir / f"{STORE_STEM}.parquet",
            "schema": out_dir / f"{STORE_STEM}_schema.json",
            "manifest": out_dir / f"{STORE_STEM}_build_manifest.json",
        }

    master = site / "reports" / "master_long.parquet"
    demand = site / "utilities" / "demand_interval_kw.csv"
    zone_json = site / "reports" / "thermal_zone_model.json"
    weather = site / "clean_data" / "LAKESIDE_ES" / "weather" / "history_wide.csv"
    if not weather.is_file():
        weather = site / "clean_data" / "CREEKSIDE_ES" / "weather" / "history_wide.csv"

    for p, label in (
        (master, "master_long"),
        (demand, "demand_interval"),
        (zone_json, "thermal_zone_model"),
        (weather, "weather_history_wide"),
    ):
        if not Path(p).is_file():
            raise FileNotFoundError(f"missing {label}: {p}")

    equip_map = load_zone_equip_map(zone_json)
    zone_doc = json.loads(zone_json.read_text(encoding="utf-8"))
    schedule = zone_doc.get("schedule", {})

    # --- zone temps (5-min → area mean → 15-min) ---
    import pyarrow.parquet as pq

    zn = pq.read_table(
        master,
        columns=["timestamp_utc", "csv_column", "value", "floor", "area", "equip_id"],
        filters=[("csv_column", "==", "zn_t")],
    ).to_pandas()
    zn["timestamp_utc"] = pd.to_datetime(zn["timestamp_utc"], utc=True)
    zn["value"] = pd.to_numeric(zn["value"], errors="coerce")
    zn["zone_id"] = zn["equip_id"].map(equip_map)
    # fallback floor/area when equip missing from map
    miss = zn["zone_id"].isna()
    if miss.any():
        zn.loc[miss, "zone_id"] = [
            _floor_area_to_zone(f, a) for f, a in zip(zn.loc[miss, "floor"], zn.loc[miss, "area"])
        ]
    zn = zn.dropna(subset=["zone_id", "value", "timestamp_utc"])
    if zn.empty:
        raise ValueError("empty zone coverage after equip/floor mapping")
    covered = set(zn["zone_id"].unique())
    missing_z = [z for z in AREA_ZONE_IDS if z not in covered]
    if missing_z:
        raise ValueError(f"empty zone coverage for: {missing_z}")

    # per-timestamp mean across HPs in each area, then 15-min mean
    zn_area = (
        zn.groupby(["timestamp_utc", "zone_id"], as_index=False)["value"]
        .mean()
        .pivot(index="timestamp_utc", columns="zone_id", values="value")
        .sort_index()
    )
    for zid in AREA_ZONE_IDS:
        if zid not in zn_area.columns:
            raise ValueError(f"missing zone column after pivot: {zid}")
    zn_15 = zn_area[AREA_ZONE_IDS].resample("15min", label="right", closed="right").mean()
    zn_15 = zn_15.rename(columns=_ZONE_TO_TEMP)

    # --- facility kW ---
    dem = pd.read_csv(demand)
    dem["timestamp_utc"] = pd.to_datetime(dem["timestamp_utc"], utc=True)
    dem["kw_demand"] = pd.to_numeric(dem["kw_demand"], errors="coerce")
    dem = dem.dropna(subset=["timestamp_utc", "kw_demand"]).set_index("timestamp_utc").sort_index()
    kw_15 = _resample_15min_mean(dem["kw_demand"]).to_frame("facility_kw")

    # --- weather ---
    wx = pd.read_csv(weather)
    wx["timestamp_utc"] = pd.to_datetime(wx["timestamp_utc"], utc=True)
    wx = wx.set_index("timestamp_utc").sort_index()
    oat = pd.to_numeric(wx.get("web-outside-air-temp"), errors="coerce")
    rh = pd.to_numeric(wx.get("web-outside-air-humidity"), errors="coerce")
    ghi = pd.to_numeric(wx.get("shortwave_radiation_wm2"), errors="coerce")
    wx_15 = pd.DataFrame(
        {
            "oat_f": _resample_15min_mean(oat),
            "rh_pct": _resample_15min_mean(rh),
            "ghi": _resample_15min_mean(ghi),
        }
    )

    # optional site OAT from master (causal check — prefer weather history)
    try:
        oa = pq.read_table(
            master,
            columns=["timestamp_utc", "csv_column", "value"],
            filters=[("csv_column", "==", "oa_t")],
        ).to_pandas()
        oa["timestamp_utc"] = pd.to_datetime(oa["timestamp_utc"], utc=True)
        oa["value"] = pd.to_numeric(oa["value"], errors="coerce")
        oa = oa.dropna().set_index("timestamp_utc").sort_index()
        oa_15 = _resample_15min_mean(oa["value"])
        wx_15["oat_f"] = wx_15["oat_f"].fillna(oa_15)
    except Exception:
        pass

    # --- join ---
    frame = kw_15.join(zn_15, how="inner").join(wx_15, how="left")
    frame = frame.dropna(subset=["facility_kw", *ZONE_TEMP_COLS])
    if frame.empty:
        raise ValueError("joined 15-min store is empty")

    local = frame.index.tz_convert(TZ)
    frame = frame.reset_index()
    if frame.columns[0] != "timestamp_utc":
        frame = frame.rename(columns={frame.columns[0]: "timestamp_utc"})
    frame["timestamp_local"] = pd.DatetimeIndex(local).tz_localize(None)
    loc_idx = pd.DatetimeIndex(local)
    # Canonical contract: 00:15 → step 0 … 24:00/00:00 → step 95 (prior site_date).
    from interval15 import hour_ending_from_quarter, quarter_from_interval_end_hms, site_date_for_interval_end

    steps = []
    days = []
    hes = []
    for ts in loc_idx:
        naive = ts.to_pydatetime().replace(tzinfo=None) if hasattr(ts, "to_pydatetime") else ts
        if getattr(naive, "tzinfo", None) is not None:
            naive = naive.replace(tzinfo=None)
        q = quarter_from_interval_end_hms(int(naive.hour), int(naive.minute))
        steps.append(q)
        days.append(site_date_for_interval_end(naive).isoformat())
        hes.append(hour_ending_from_quarter(q))
    frame["step_15"] = np.asarray(steps, dtype=int)
    frame["hour_ending"] = np.asarray(hes, dtype=float)
    frame["day"] = days
    frame["month"] = loc_idx.month.astype(int)
    frame["doy"] = loc_idx.dayofyear.astype(int)
    frame["dow"] = loc_idx.day_name()
    frame["is_weekend"] = (loc_idx.dayofweek >= 5).astype(float)
    frame["occupied"] = _occupied_from_schedule(pd.Series(loc_idx), schedule).to_numpy()

    # Causal lags across wall time (incl. midnight): q0 uses prior interval state,
    # not same-row targets. First 1–2 rows of the whole series may be NaN → dropped at train.
    frame = frame.sort_values("timestamp_utc").reset_index(drop=True)
    frame["facility_kw_lag1"] = frame["facility_kw"].shift(1)
    frame["facility_kw_lag2"] = frame["facility_kw"].shift(2)
    frame["oat_lag1"] = frame["oat_f"].shift(1)
    for c in ZONE_TEMP_COLS:
        frame[f"{c}_lag1"] = frame[c].shift(1)

    frame["sin_step"] = np.sin(2 * np.pi * frame["step_15"] / 96.0)
    frame["cos_step"] = np.cos(2 * np.pi * frame["step_15"] / 96.0)
    frame["hdd65"] = np.maximum(0.0, 65.0 - pd.to_numeric(frame["oat_f"], errors="coerce"))
    # cumulative night HDD from midnight local through current step (same day)
    night = frame["step_15"] < 28  # before ~07:00
    frame["hdd65_cum_night"] = (
        frame.assign(_n=np.where(night, frame["hdd65"], 0.0))
        .groupby("day", sort=False)["_n"]
        .cumsum()
    )
    # hours to occupy (K-12 07:00) — contract step 28 ≈ 07:15
    occ_step = 28
    frame["hours_to_occupy"] = np.maximum(0.0, (occ_step - frame["step_15"]) / 4.0)

    # baseline control placeholders (real store = measured operation)
    frame["strategy_id"] = "baseline"
    frame["control_regime"] = "measured_bas"
    frame["provenance"] = PROVENANCE
    for c in (
        "occ_frac_1F_A",
        "occ_frac_1F_B",
        "occ_frac_1F_C",
        "occ_frac_1F_D",
        "occ_frac_2F_A",
        "occ_frac_2F_B",
    ):
        frame[c] = frame["occupied"]
    for c in (
        "hp_on_1F_A",
        "hp_on_1F_B",
        "hp_on_1F_C",
        "hp_on_1F_D",
        "hp_on_2F_A",
        "hp_on_2F_B",
    ):
        frame[c] = 1.0
    frame["sum_occ_frac"] = frame["occupied"] * 6.0
    frame["sum_hp_on"] = 6.0
    frame["preheat_lead_h"] = 0.0
    frame["stagger_min"] = 0.0
    frame["unocc_htg_sp_f"] = 64.0
    frame["occ_htg_sp_f"] = 68.0

    # continuity: drop days with < 90 of 96 steps
    counts = frame.groupby("day")["step_15"].count()
    good_days = counts[counts >= 90].index
    frame = frame[frame["day"].isin(good_days)].reset_index(drop=True)
    if frame.empty:
        raise ValueError("no days with adequate 15-min continuity (≥90/96)")

    schema = {
        "stem": STORE_STEM,
        "resolution": "15min",
        "steps_per_day": 96,
        "provenance": PROVENANCE,
        "targets": ["facility_kw", *ZONE_TEMP_COLS],
        "area_zone_ids": AREA_ZONE_IDS,
        "timezone": TZ,
        "n_rows": int(len(frame)),
        "n_days": int(frame["day"].nunique()),
        "columns": list(frame.columns),
    }

    input_hashes = {
        "master_long.parquet": _sha256_file(master),
        "demand_interval_kw.csv": _sha256_file(demand),
        "thermal_zone_model.json": _sha256_file(zone_json),
        "weather_history_wide.csv": _sha256_file(weather),
    }
    miss_frac = {
        c: float(frame[c].isna().mean())
        for c in ["facility_kw", "oat_f", "rh_pct", "ghi", *ZONE_TEMP_COLS]
        if c in frame.columns
    }
    manifest = {
        "stem": STORE_STEM,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "site_root": str(site),
        "input_hashes": input_hashes,
        "row_count": int(len(frame)),
        "day_count": int(frame["day"].nunique()),
        "missingness": miss_frac,
        "equip_map_size": len(equip_map),
        "zone_ids": AREA_ZONE_IDS,
        "honesty": (
            "REAL_BAS only — no EnergyPlus rows. Hybrid screening baseline component A."
        ),
        "paths": {k: str(v) for k, v in paths.items()},
    }

    paths["parquet"].parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(paths["parquet"], index=False)
    paths["schema"].write_text(json.dumps(schema, indent=2), encoding="utf-8")
    paths["manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return frame, manifest
