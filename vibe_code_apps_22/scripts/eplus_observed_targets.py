#!/usr/bin/env python
"""Build observed electric + BAS analytics targets for E+ GL14 calibration."""
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
from pathlib import Path

import pandas as pd

ROOT = site_root()
REPORTS = ROOT / "reports"
UTIL = ROOT / "utilities"
CLEAN = clean_data_building_dir()
OUT = ROOT / "eplus" / "assumptions"
EPLUS_REPORTS = ROOT / "reports" / "eplus"
TZ = "America/Chicago"

ZONE_HP = {
    "1F_Area_A": 15,
    "1F_Area_B": 10,
    "1F_Area_C": 11,
    "1F_Area_D": 10,
    "2F_Area_A": 11,
    "2F_Area_B": 10,
}
GROSS_FT2 = 91210.0
COND_FT2 = 89400.0


def _parse_kwh(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    return float(str(val).replace(",", "").replace('"', "").strip())


def monthly_kwh_from_bills() -> pd.DataFrame:
    bills = pd.read_csv(UTIL / "electricity.csv")
    bills["month"] = bills["Bill Month"].astype(str)
    bills["kwh_obs"] = bills["kWh Total"].map(_parse_kwh)
    bills["complete_month"] = ~bills["month"].eq("2026-07")  # short dump month
    return bills[["month", "kwh_obs", "complete_month"]]


def monthly_peak_from_interval() -> pd.DataFrame:
    path = UTIL / "demand_interval_kw.csv"
    df = pd.read_csv(path)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["ts_local"] = df["timestamp_utc"].dt.tz_convert(TZ)
    df["month"] = df["ts_local"].dt.to_period("M").astype(str)
    g = df.groupby("month", as_index=False).agg(
        peak_kw_obs=("kw_demand", "max"),
        mean_kw_obs=("kw_demand", "mean"),
        n_samples=("kw_demand", "count"),
    )
    return g


def zone_temp_targets() -> dict:
    path = REPORTS / "zone_temp_monthly_occ_unocc.csv"
    if not path.is_file():
        return {}
    z = pd.read_csv(path)
    # Prefer January occupied setpoints as heating-season dial-in
    jan = z[z["month"] == "2026-01"]
    by_zone = {}
    for zone_id, g in jan.groupby("zone_id"):
        occ = g[g["occupancy"] == "occupied"]["zn_t_avg_f"]
        unocc = g[g["occupancy"] == "unoccupied"]["zn_t_avg_f"]
        by_zone[zone_id] = {
            "occ_avg_f": float(occ.mean()) if len(occ) else None,
            "unocc_avg_f": float(unocc.mean()) if len(unocc) else None,
        }
    building_occ = float(jan[jan["occupancy"] == "occupied"]["zn_t_avg_f"].mean())
    building_unocc = float(jan[jan["occupancy"] == "unoccupied"]["zn_t_avg_f"].mean())
    return {
        "definition": "Mon-Fri 07:00-16:00 America/Chicago (thermal_zone_model schedule)",
        "reference_month": "2026-01",
        "building_occ_avg_f": round(building_occ, 2),
        "building_unocc_avg_f": round(building_unocc, 2),
        "recommended_heat_setpoint_occ_f": round(building_occ, 0),
        "recommended_heat_setback_unocc_f": round(building_unocc, 0),
        "by_zone": by_zone,
    }


def fan_runtime_targets() -> dict:
    path = REPORTS / "zone_avg_fan_run_hours_monthly.csv"
    if not path.is_file():
        return {}
    f = pd.read_csv(path)
    jan = f[f["month"] == "2026-01"]
    by_zone = {
        row.zone_id: {
            "avg_fan_run_hours": float(row.avg_fan_run_hours),
            "n_heat_pumps": int(row.n_heat_pumps),
        }
        for row in jan.itertuples()
    }
    return {
        "reference_month": "2026-01",
        "note": "Use relative fan hours across zones to weight HP availability; not a hard G14 gate",
        "by_zone": by_zone,
    }


def geo_loop_monthly() -> pd.DataFrame:
    hist = CLEAN / "GEO_LOOP" / "history_wide.csv"
    if not hist.is_file():
        return pd.DataFrame()
    df = pd.read_csv(hist)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["ts_local"] = df["timestamp_utc"].dt.tz_convert(TZ)
    df["month"] = df["ts_local"].dt.to_period("M").astype(str)
    cols = [c for c in ("hp_sup_t", "hp_ret_t", "geo_dp", "oa_t", "pump1_vfd", "pump2_vfd") if c in df.columns]
    agg = {c: "mean" for c in cols}
    g = df.groupby("month", as_index=False).agg(agg)
    # rename for clarity
    rename = {
        "hp_sup_t": "geo_supply_t_f_avg",
        "hp_ret_t": "geo_return_t_f_avg",
        "geo_dp": "geo_dp_avg",
        "oa_t": "geo_oat_f_avg",
        "pump1_vfd": "pump1_vfd_avg",
        "pump2_vfd": "pump2_vfd_avg",
    }
    return g.rename(columns={k: v for k, v in rename.items() if k in g.columns})


def zone_areas() -> dict:
    total_hp = sum(ZONE_HP.values())
    areas = {}
    for zid, n in ZONE_HP.items():
        areas[zid] = {
            "n_heat_pumps": n,
            "conditioned_ft2": round(COND_FT2 * n / total_hp, 1),
            "share": round(n / total_hp, 4),
        }
    return areas


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    EPLUS_REPORTS.mkdir(parents=True, exist_ok=True)

    kwh = monthly_kwh_from_bills()
    peaks = monthly_peak_from_interval()
    merged = kwh.merge(peaks, on="month", how="left")
    merged.to_csv(EPLUS_REPORTS / "observed_monthly_electric.csv", index=False)

    geo = geo_loop_monthly()
    if not geo.empty:
        geo.to_csv(EPLUS_REPORTS / "observed_geo_loop_monthly.csv", index=False)

    targets = {
        "version": 1,
        "gross_ft2": GROSS_FT2,
        "conditioned_ft2": COND_FT2,
        "zone_areas": zone_areas(),
        "zone_temp": zone_temp_targets(),
        "fan_runtime": fan_runtime_targets(),
        "electric_months": merged.to_dict(orient="records"),
        "geo_loop_months": geo.to_dict(orient="records") if not geo.empty else [],
        "mcp_knob_map": {
            "zone_temp_occ_unocc": "heating/cooling setpoints + HVAC availability schedules",
            "fan_run_hours": "zone fan availability / HP availability schedules (IDF edit)",
            "monthly_kwh": "modify_people / modify_lights / modify_electric_equipment / change_infiltration_by_mult",
            "geo_loop_temps": "compare sim condenser loop EWT/LWT to hp_ret_t / hp_sup_t; tune GLHE after air-side match",
            "demand_shape": "school occupancy schedule (07:30-14:40; Thu early dismiss)",
        },
    }
    (OUT / "bas_calibration_targets.json").write_text(
        json.dumps(targets, indent=2), encoding="utf-8"
    )
    print(f"wrote {EPLUS_REPORTS / 'observed_monthly_electric.csv'}")
    print(f"wrote {OUT / 'bas_calibration_targets.json'}")
    if not geo.empty:
        print(f"wrote {EPLUS_REPORTS / 'observed_geo_loop_monthly.csv'} rows={len(geo)}")
    zt = targets["zone_temp"]
    print(
        f"Jan BAS temps occ={zt.get('building_occ_avg_f')} "
        f"unocc={zt.get('building_unocc_avg_f')} → SP "
        f"{zt.get('recommended_heat_setpoint_occ_f')}/"
        f"{zt.get('recommended_heat_setback_unocc_f')} F"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
