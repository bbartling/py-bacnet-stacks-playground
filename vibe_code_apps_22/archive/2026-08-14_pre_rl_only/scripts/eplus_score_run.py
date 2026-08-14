#!/usr/bin/env python
"""Score an EnergyPlus run dir vs observed monthly kWh (GL14) + BAS geo notes."""
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
APP = app_root()
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = site_root()
OBS_DEFAULT = ROOT / "reports" / "eplus" / "observed_monthly_electric.csv"
OBS = Path(os.environ["EPLUS_OBS_CSV"]) if os.environ.get("EPLUS_OBS_CSV") else OBS_DEFAULT
TARGETS = ROOT / "eplus" / "assumptions" / "bas_calibration_targets.json"
sys.path.insert(0, str(APP / "scripts"))
from eplus_gl14 import gl14_distance, nmbe_cvrmse, pass_fail  # noqa: E402

HEAT_COP = 3.5
COOL_COP = 4.5


def _cops() -> tuple[float, float]:
    ledger = ROOT / "eplus" / "assumptions" / "ledger.json"
    if ledger.is_file():
        d = json.loads(ledger.read_text(encoding="utf-8"))
        return float(d.get("heat_cop_proxy", HEAT_COP)), float(d.get("cool_cop_proxy", COOL_COP))
    return HEAT_COP, COOL_COP


def _month_from_stamp(stamp: str) -> str | None:
    stamp = str(stamp).strip()
    # "08/31  24:00:00" or "August" or ISO
    m = re.match(r"^(\d{1,2})/", stamp)
    if m:
        mm = int(m.group(1))
        year = "2025" if mm >= 8 else "2026"
        return f"{year}-{mm:02d}"
    months = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }
    low = stamp.lower()
    for name, num in months.items():
        if low.startswith(name):
            year = "2025" if int(num) >= 8 else "2026"
            return f"{year}-{num}"
    try:
        ts = pd.to_datetime(stamp)
        return ts.strftime("%Y-%m")
    except Exception:
        return None


def parse_eplus_monthly_meters(sim_dir: Path) -> pd.DataFrame:
    heat_cop, cool_cop = _cops()
    path = None
    for cand in [sim_dir / "eplusmtr.csv", *sim_dir.glob("*Meter.csv"), sim_dir / "eplusout.csv"]:
        if cand.is_file():
            path = cand
            break
    if path is None:
        return pd.DataFrame(columns=["month", "kwh_sim"])

    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    date_col = df.columns[0]
    def col_has(*parts):
        for c in df.columns:
            if all(p.lower() in c.lower() for p in parts):
                return c
        return None

    elec_m = col_has("Electricity:Facility", "Monthly")
    # E+ 25.x: DistrictHeatingWater; older IDFs: DistrictHeating
    dh_m = col_has("DistrictHeatingWater", "Monthly") or col_has("DistrictHeating", "Monthly")
    dc_m = col_has("DistrictCooling", "Monthly")
    if not elec_m:
        return pd.DataFrame(columns=["month", "kwh_sim"])

    rows = []
    for _, r in df.iterrows():
        val = r.get(elec_m)
        if pd.isna(val) or float(val) == 0.0:
            # keep July partial even if small — skip pure empties
            if pd.isna(val):
                continue
        month = _month_from_stamp(r[date_col])
        if not month:
            continue
        # monthly rows typically stamped day 28-31 hour 24
        stamp = str(r[date_col])
        if "24:00" not in stamp and not re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
            stamp,
            re.I,
        ):
            # skip hourly rows that happen to have NaN monthly
            if pd.isna(val) or float(val) == 0:
                continue
            # only accept if monthly column is populated on end-of-month
            if not re.search(r"/(28|29|30|31)\s", stamp):
                continue

        kwh_site = float(val) / 3_600_000.0
        dh = float(r[dh_m]) if dh_m and pd.notna(r.get(dh_m)) else 0.0
        dc = float(r[dc_m]) if dc_m and pd.notna(r.get(dc_m)) else 0.0
        kwh_hvac = (dh / 3_600_000.0) / heat_cop + (dc / 3_600_000.0) / cool_cop
        rows.append(
            {
                "month": month,
                "kwh_sim": kwh_site + kwh_hvac,
                "kwh_facility": kwh_site,
                "kwh_hvac_proxy": kwh_hvac,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["month", "kwh_sim"])
    out = pd.DataFrame(rows)
    # Prefer last row per month (end-of-month stamp)
    return out.groupby("month", as_index=False).last()


def score_run(sim_dir: Path, iter_id: str | None = None) -> dict:
    obs = pd.read_csv(OBS)
    obs = obs[obs["complete_month"] == True]  # noqa: E712
    sim = parse_eplus_monthly_meters(Path(sim_dir))
    m = obs.merge(sim, on="month", how="inner")
    stats = nmbe_cvrmse(m["kwh_obs"].tolist(), m["kwh_sim"].tolist()) if len(m) else {
        "n": 0, "nmbe_pct": float("nan"), "cvrmse_pct": float("nan"), "mean_obs": float("nan")
    }
    status = pass_fail(stats)
    monthly = []
    for _, r in m.iterrows():
        err = (r["kwh_sim"] - r["kwh_obs"]) / r["kwh_obs"] * 100.0 if r["kwh_obs"] else float("nan")
        monthly.append(
            {
                "month": r["month"],
                "kwh_obs": round(float(r["kwh_obs"]), 1),
                "kwh_sim": round(float(r["kwh_sim"]), 1),
                "pct_error": round(float(err), 2),
                "peak_kw_obs": float(r["peak_kw_obs"]) if "peak_kw_obs" in r and pd.notna(r["peak_kw_obs"]) else None,
            }
        )
    geo_note = None
    if TARGETS.is_file():
        t = json.loads(TARGETS.read_text(encoding="utf-8"))
        geo = t.get("geo_loop_months") or []
        jan = next((g for g in geo if g.get("month") == "2026-01"), None)
        zt = t.get("zone_temp") or {}
        if jan or zt:
            geo_note = {
                "bas_jan_supply_f": (jan or {}).get("geo_supply_t_f_avg"),
                "bas_jan_return_f": (jan or {}).get("geo_return_t_f_avg"),
                "bas_jan_zn_t_occ_f": zt.get("building_occ_avg_f"),
                "bas_jan_zn_t_unocc_f": zt.get("building_unocc_avg_f"),
                "compare": "IdealLoads seed — geo loop temps for GLHE phase; zn_t used for SP",
            }
    hc, cc = _cops()
    scorecard = {
        "iter": iter_id,
        "sim_dir": str(sim_dir),
        "gl14": stats,
        "gl14_status": status,
        "gl14_distance": gl14_distance(stats),
        "monthly": monthly,
        "geo_loop_and_zone_bas": geo_note,
        "heat_cop_proxy": hc,
        "cool_cop_proxy": cc,
    }
    (Path(sim_dir) / "scorecard.json").write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    return scorecard


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("sim_dir")
    p.add_argument("--iter", default=None)
    args = p.parse_args()
    sc = score_run(Path(args.sim_dir), args.iter)
    print(json.dumps({k: sc[k] for k in ("gl14", "gl14_status", "gl14_distance", "monthly")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
