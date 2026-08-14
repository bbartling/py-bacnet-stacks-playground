"""Ingest client utility electric bills → clean monthly series for GL14 / vibe20.

Writes:
  utilities/utility_bills_raw.csv          (full history as provided)
  utilities/electricity_utility.csv        (Bill Month, kWh Total — billing-grade)
  utilities/electricity_utility_demand.csv (month, kWh, demand_kw, billed_demand_kw, cost_usd)
  reports/eplus/observed_monthly_utility.csv  (GL14 obs for AMY overlap months)
  utilities/campus_utility.json            (vibe20-style campus pointing at utility file)
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
import csv
import json
from pathlib import Path

ROOT = site_root()

# Client-provided rows overlapping / near the BAS demand window + recent history.
# Account CS 351075 (recent) and legacy E1075. Demand window AMY: 2025-08 → 2026-07.
# Utility GL14 months: 2025-08 … 2026-05 (Jun/Jul 2026 not yet on CS account dump).
BILLS: list[dict] = [
    # CS 351075 — recent
    {"account": "CS 351075", "period": "202605", "begin": "2026-05-01", "end": "2026-06-01", "cost": 4736.68, "kwh": 31398, "days": 31, "demand": 286.98, "billed_demand": 128.1},
    {"account": "CS 351075", "period": "202604", "begin": "2026-04-01", "end": "2026-05-01", "cost": 5201.86, "kwh": 42296, "days": 30, "demand": 286.98, "billed_demand": 165.42},
    {"account": "CS 351075", "period": "202603", "begin": "2026-03-02", "end": "2026-04-01", "cost": 6395.68, "kwh": 51938, "days": 30, "demand": 286.98, "billed_demand": 218.94},
    {"account": "CS 351075", "period": "202602", "begin": "2026-02-01", "end": "2026-03-02", "cost": 7774.96, "kwh": 67205, "days": 29, "demand": 286.98, "billed_demand": 240.72},
    {"account": "CS 351075", "period": "202601", "begin": "2026-01-01", "end": "2026-02-01", "cost": 8269.37, "kwh": 81491, "days": 31, "demand": 284.82, "billed_demand": 284.82},
    {"account": "CS 351075", "period": "202512", "begin": "2025-12-01", "end": "2026-01-01", "cost": 6683.62, "kwh": 67328, "days": 31, "demand": 299.4, "billed_demand": 232.38},
    {"account": "CS 351075", "period": "202511", "begin": "2025-11-01", "end": "2025-12-01", "cost": 5086.0, "kwh": 42097, "days": 30, "demand": 299.4, "billed_demand": 166.98},
    {"account": "CS 351075", "period": "202510", "begin": "2025-10-01", "end": "2025-11-01", "cost": 4390.17, "kwh": 32552, "days": 31, "demand": 299.4, "billed_demand": 131.04},
    {"account": "CS 351075", "period": "202509", "begin": "2025-09-01", "end": "2025-10-01", "cost": 4781.2, "kwh": 31350, "days": 30, "demand": 299.4, "billed_demand": 133.74},
    {"account": "CS 351075", "period": "202508", "begin": "2025-08-01", "end": "2025-09-01", "cost": 5342.35, "kwh": 32789, "days": 31, "demand": 299.4, "billed_demand": 136.98},
    {"account": "CS 351075", "period": "202507", "begin": "2025-07-01", "end": "2025-08-01", "cost": 5353.53, "kwh": 33538, "days": 31, "demand": 299.4, "billed_demand": 160.14},
    {"account": "CS 351075", "period": "202506", "begin": "2025-06-01", "end": "2025-07-01", "cost": 5482.07, "kwh": 33955, "days": 30, "demand": 299.4, "billed_demand": 164.64},
    {"account": "CS 351075", "period": "202505", "begin": "2025-05-01", "end": "2025-06-01", "cost": 5220.29, "kwh": 38307, "days": 31, "demand": 299.4, "billed_demand": 152.4},
    {"account": "CS 351075", "period": "202504", "begin": "2025-04-01", "end": "2025-05-01", "cost": 5500.89, "kwh": 48953, "days": 30, "demand": 299.4, "billed_demand": 181.14},
    {"account": "CS 351075", "period": "202503", "begin": "2025-03-01", "end": "2025-04-01", "cost": 6167.3, "kwh": 55885, "days": 31, "demand": 212.52, "billed_demand": 299.4},
    {"account": "CS 351075", "period": "202502", "begin": "2025-02-01", "end": "2025-03-01", "cost": 7412.63, "kwh": 76931, "days": 28, "demand": 260.82, "billed_demand": 299.4},
    {"account": "CS 351075", "period": "202501", "begin": "2025-01-01", "end": "2025-02-01", "cost": 7670.2, "kwh": 82032, "days": 31, "demand": 299.4, "billed_demand": 299.4},
]

# AMY / model calibration window months with complete utility bills
GL14_MONTHS = [
    "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    "2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
]


def period_to_month(period: str) -> str:
    y, m = period[:4], period[4:]
    return f"{y}-{m}"


def main() -> int:
    util = ROOT / "utilities"
    util.mkdir(parents=True, exist_ok=True)
    raw_path = util / "utility_bills_raw.csv"
    fields = ["account", "billing_period", "bill_begin", "bill_end", "meter_cost_usd",
              "kwh", "days", "demand_kw", "billed_demand_kw"]
    with raw_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for b in BILLS:
            w.writerow({
                "account": b["account"],
                "billing_period": b["period"],
                "bill_begin": b["begin"],
                "bill_end": b["end"],
                "meter_cost_usd": b["cost"],
                "kwh": b["kwh"],
                "days": b["days"],
                "demand_kw": b["demand"],
                "billed_demand_kw": b["billed_demand"],
            })

    by_month = {period_to_month(b["period"]): b for b in BILLS}

    elec_u = util / "electricity_utility.csv"
    with elec_u.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Bill Month", "kWh Total"])
        for m in sorted(by_month.keys()):
            w.writerow([m, by_month[m]["kwh"]])

    demand_u = util / "electricity_utility_demand.csv"
    with demand_u.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["month", "kwh", "demand_kw", "billed_demand_kw", "cost_usd", "days"])
        for m in sorted(by_month.keys()):
            b = by_month[m]
            w.writerow([m, b["kwh"], b["demand"], b["billed_demand"], b["cost"], b["days"]])

    # GL14 observed series (complete utility months in AMY window)
    obs_dir = ROOT / "reports" / "eplus"
    obs_dir.mkdir(parents=True, exist_ok=True)
    obs_path = obs_dir / "observed_monthly_utility.csv"
    with obs_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["month", "kwh_obs", "peak_kw_obs", "complete_month", "source"])
        for m in GL14_MONTHS:
            b = by_month[m]
            w.writerow([m, b["kwh"], b["demand"], True, "utility_bill"])

    campus = {
        "campus_id": "lakeside_es",
        "label": "Lakeside Elementary School",
        "siteRef": "spasd_lakeside_es",
        "provenance": "utility_bills_CS351075",
        "notes": (
            "Monthly kWh / demand from client utility export (CS 351075). "
            "Billing-grade vs interval-integrated electricity.csv. "
            "GL14 utility window: 2025-08..2026-05."
        ),
        "lat": 43.16521,
        "lon": -89.25408,
        "location": {"city": "southern Wisconsin", "climate_zone": "6A"},
        "buildings": [{
            "building_id": "lakeside_main",
            "label": "Lakeside Elementary School",
            "floor_area_ft2": 91210,
            "property_type": "k12_school",
        }],
        "meters": [{
            "meter_id": "elec_utility",
            "fuel": "electricity",
            "unit": "kwh",
            "file": "electricity_utility.csv",
            "serves": ["lakeside_main"],
            "bill_columns": {"month": "Bill Month", "usage": "kWh Total"},
        }],
    }
    (util / "campus_utility.json").write_text(json.dumps(campus, indent=2) + "\n", encoding="utf-8")

    # Comparison vs interval-integrated (if present)
    interval = util / "electricity.csv"
    if interval.is_file():
        import pandas as pd
        iv = pd.read_csv(interval)
        iv["kWh Total"] = (
            iv["kWh Total"].astype(str).str.replace(",", "", regex=False).astype(float)
        )
        rows = []
        for m in GL14_MONTHS:
            u = by_month[m]["kwh"]
            match = iv.loc[iv["Bill Month"] == m, "kWh Total"]
            i = float(match.iloc[0]) if len(match) else None
            rows.append({
                "month": m,
                "kwh_utility": u,
                "kwh_interval": i,
                "pct_diff_interval_vs_utility": (
                    round((i - u) / u * 100, 2) if i is not None else None
                ),
            })
        cmp_path = obs_dir / "utility_vs_interval_kwh.csv"
        pd.DataFrame(rows).to_csv(cmp_path, index=False)
        print(f"wrote {cmp_path}")

    print(f"wrote {raw_path}")
    print(f"wrote {elec_u}")
    print(f"wrote {demand_u}")
    print(f"wrote {obs_path} ({len(GL14_MONTHS)} GL14 months)")
    print(f"wrote {util / 'campus_utility.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
