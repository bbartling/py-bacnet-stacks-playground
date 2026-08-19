#!/usr/bin/env python
"""Build floor/thermal-zone HP data model + monthly occ/unocc zone temps & run hours."""
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
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = site_root()
CLEAN = clean_data_building_dir()
REPORTS = ROOT / "reports"
CHARTS = ROOT / "plots" / "analytics"
MODEL_PATH = CLEAN / "thermal_zone_model.json"
SITE_REF = "spasd_lakeside_es"
BUILDING = "LAKESIDE_ES"
TZ = "America/Chicago"
GRID_HOURS = 5.0 / 60.0  # each 5-min fan_s==1 sample

# Generic K-12 school schedule (local time)
OCC_START = 7  # 07:00 inclusive
OCC_END = 16  # 16:00 exclusive


def load_inventory() -> list[dict]:
    inv = json.loads((CLEAN / "equipment_inventory.json").read_text(encoding="utf-8"))
    return [e for e in inv if e.get("type") == "HEAT_PUMP"]


def zone_id(floor: str, area: str) -> str:
    fl = "1F" if "first" in floor.lower() else ("2F" if "second" in floor.lower() else "XF")
    area_code = area.replace(" ", "_")
    return f"{fl}_{area_code}"


def build_model(hps: list[dict]) -> dict:
    """Floor → thermal zone (ALC Area) → heat pumps."""
    floors: dict[str, dict] = {}
    for hp in sorted(hps, key=lambda x: (x["floor"], x["area"], x["equip_id"])):
        floor = hp.get("floor") or "Unknown Floor"
        area = hp.get("area") or "Unknown Area"
        if floor not in floors:
            floors[floor] = {
                "floor_id": "first_floor"
                if "first" in floor.lower()
                else ("second_floor" if "second" in floor.lower() else _slug(floor)),
                "label": floor,
                "thermal_zones": {},
            }
        zid = zone_id(floor, area)
        zones = floors[floor]["thermal_zones"]
        if zid not in zones:
            zones[zid] = {
                "zone_id": zid,
                "label": area,
                "floor": floor,
                "area": area,
                "heat_pumps": [],
            }
        # detect available points from folder
        hist = CLEAN / hp["equip_id"] / "history_wide.csv"
        cols = []
        if hist.is_file():
            cols = list(pd.read_csv(hist, nrows=0).columns)
        zones[zid]["heat_pumps"].append(
            {
                "equip_id": hp["equip_id"],
                "device_name": hp.get("device_name") or hp.get("device") or hp["equip_id"],
                "display_path": hp.get("display_path") or "",
                "has_zone_temp": "zn_t" in cols,
                "has_discharge_temp": "da_t" in cols,
                "has_fan_status": "fan_s" in cols,
            }
        )

    floor_list = []
    for floor_label in sorted(floors.keys()):
        f = floors[floor_label]
        zone_list = [f["thermal_zones"][z] for z in sorted(f["thermal_zones"].keys())]
        floor_list.append(
            {
                "floor_id": f["floor_id"],
                "label": f["label"],
                "thermal_zone_count": len(zone_list),
                "heat_pump_count": sum(len(z["heat_pumps"]) for z in zone_list),
                "thermal_zones": zone_list,
            }
        )

    model = {
        "version": 1,
        "siteRef": SITE_REF,
        "building": BUILDING,
        "source": "ALC WebCTRL title hierarchy (Floor / Area / Heat Pump)",
        "notes": (
            "Thermal zones = original ALC Area A–D groupings per floor. "
            "Occupied schedule is a generic K-12 weekday window (local America/Chicago), "
            "not a BAS occupancy point."
        ),
        "schedule": {
            "name": "generic_k12_weekday",
            "timezone": TZ,
            "occupied_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "occupied_start_local": f"{OCC_START:02d}:00",
            "occupied_end_local": f"{OCC_END:02d}:00",
            "occupied_definition": (
                f"dayofweek Mon-Fri AND local hour in [{OCC_START}, {OCC_END})"
            ),
            "unoccupied_definition": "all other timestamps (nights, weekends, holidays treated as unocc)",
        },
        "floors": floor_list,
        "summary": {
            "floor_count": len(floor_list),
            "thermal_zone_count": sum(f["thermal_zone_count"] for f in floor_list),
            "heat_pump_count": sum(f["heat_pump_count"] for f in floor_list),
        },
    }
    return model


def _slug(s: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in s.lower()).strip("_")


def is_occupied(ts_local: pd.Series) -> pd.Series:
    dow = ts_local.dt.dayofweek  # Mon=0
    hour = ts_local.dt.hour
    return (dow < 5) & (hour >= OCC_START) & (hour < OCC_END)


def load_hp_frame(equip_id: str) -> pd.DataFrame | None:
    path = CLEAN / equip_id / "history_wide.csv"
    if not path.is_file():
        return None
    df = pd.read_csv(path)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["ts_local"] = df["timestamp_utc"].dt.tz_convert(TZ)
    df["month"] = df["ts_local"].dt.strftime("%Y-%m")
    df["occupied"] = is_occupied(df["ts_local"])
    df["occ_label"] = np.where(df["occupied"], "occupied", "unoccupied")
    return df


def analyze(model: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return zone monthly temps, equip monthly temps, equip run hours, zone avg run hours."""
    temp_rows: list[dict] = []
    run_equip_rows: list[dict] = []
    run_zone_rows: list[dict] = []

    for floor in model["floors"]:
        for zone in floor["thermal_zones"]:
            zid = zone["zone_id"]
            zone_run_by_month: dict[str, list[float]] = defaultdict(list)

            for hp in zone["heat_pumps"]:
                eid = hp["equip_id"]
                df = load_hp_frame(eid)
                if df is None or df.empty:
                    continue

                # Zone temps: monthly mean by occupied/unoccupied (skip zeros / missing)
                if "zn_t" in df.columns:
                    t = df[["month", "occ_label", "zn_t"]].copy()
                    t["zn_t"] = pd.to_numeric(t["zn_t"], errors="coerce")
                    t = t[t["zn_t"].notna() & (t["zn_t"] > 0)]
                    if not t.empty:
                        g = t.groupby(["month", "occ_label"], as_index=False).agg(
                            zn_t_avg=("zn_t", "mean"),
                            zn_t_min=("zn_t", "min"),
                            zn_t_max=("zn_t", "max"),
                            n_samples=("zn_t", "size"),
                        )
                        for _, row in g.iterrows():
                            temp_rows.append(
                                {
                                    "floor": floor["label"],
                                    "area": zone["area"],
                                    "zone_id": zid,
                                    "equip_id": eid,
                                    "device_name": hp["device_name"],
                                    "month": row["month"],
                                    "occupancy": row["occ_label"],
                                    "zn_t_avg_f": round(float(row["zn_t_avg"]), 2),
                                    "zn_t_min_f": round(float(row["zn_t_min"]), 2),
                                    "zn_t_max_f": round(float(row["zn_t_max"]), 2),
                                    "n_samples": int(row["n_samples"]),
                                }
                            )

                # Fan run hours
                if "fan_s" in df.columns:
                    f = df[["month", "fan_s"]].copy()
                    f["fan_s"] = pd.to_numeric(f["fan_s"], errors="coerce").fillna(0)
                    # treat >0.5 as on
                    f["on"] = (f["fan_s"] >= 0.5).astype(float)
                    hours = f.groupby("month")["on"].sum() * GRID_HOURS
                    for month, hrs in hours.items():
                        hrs_f = float(hrs)
                        run_equip_rows.append(
                            {
                                "floor": floor["label"],
                                "area": zone["area"],
                                "zone_id": zid,
                                "equip_id": eid,
                                "device_name": hp["device_name"],
                                "month": month,
                                "fan_run_hours": round(hrs_f, 2),
                            }
                        )
                        zone_run_by_month[month].append(hrs_f)

            for month, hrs_list in sorted(zone_run_by_month.items()):
                run_zone_rows.append(
                    {
                        "floor": floor["label"],
                        "area": zone["area"],
                        "zone_id": zid,
                        "month": month,
                        "n_heat_pumps": len(hrs_list),
                        "avg_fan_run_hours": round(float(np.mean(hrs_list)), 2),
                        "total_fan_run_hours": round(float(np.sum(hrs_list)), 2),
                        "min_fan_run_hours": round(float(np.min(hrs_list)), 2),
                        "max_fan_run_hours": round(float(np.max(hrs_list)), 2),
                    }
                )

    temp_equip = pd.DataFrame(temp_rows)
    # Zone-level temp: average across HPs in zone for each month × occupancy
    if not temp_equip.empty:
        temp_zone = (
            temp_equip.groupby(
                ["floor", "area", "zone_id", "month", "occupancy"], as_index=False
            )
            .agg(
                zn_t_avg_f=("zn_t_avg_f", "mean"),
                n_heat_pumps=("equip_id", "nunique"),
                n_samples=("n_samples", "sum"),
            )
            .sort_values(["zone_id", "month", "occupancy"])
        )
        temp_zone["zn_t_avg_f"] = temp_zone["zn_t_avg_f"].round(2)
    else:
        temp_zone = pd.DataFrame()

    run_equip = pd.DataFrame(run_equip_rows).sort_values(["zone_id", "equip_id", "month"])
    run_zone = pd.DataFrame(run_zone_rows).sort_values(["zone_id", "month"])
    return temp_zone, temp_equip, run_equip, run_zone


def chart_zone_temps(temp_zone: pd.DataFrame) -> None:
    if temp_zone.empty:
        return
    CHARTS.mkdir(parents=True, exist_ok=True)
    zones = sorted(temp_zone["zone_id"].unique())
    ncols = 3
    nrows = int(np.ceil(len(zones) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 3.0 * nrows), sharey=True)
    fig.patch.set_facecolor("#0f1419")
    axes = np.atleast_1d(axes).ravel()
    for i, zid in enumerate(zones):
        ax = axes[i]
        ax.set_facecolor("#1a222c")
        sub = temp_zone[temp_zone["zone_id"] == zid]
        for occ, color in (("occupied", "#3ecf8e"), ("unoccupied", "#5eb1ff")):
            s = sub[sub["occupancy"] == occ].sort_values("month")
            if s.empty:
                continue
            ax.plot(s["month"], s["zn_t_avg_f"], marker="o", ms=3, lw=1.8, color=color, label=occ)
        ax.set_title(zid, color="#e8eef4", fontsize=10)
        ax.tick_params(colors="#8b9aab", labelsize=7)
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, color="#2a3544", alpha=0.6)
        for sp in ax.spines.values():
            sp.set_color("#2a3544")
        ax.set_ylabel("Avg zn_t °F", color="#8b9aab", fontsize=8)
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", facecolor="#1a222c", labelcolor="#e8eef4")
    fig.suptitle(
        "Lakeside avg zone temp by thermal zone × month\n"
        f"Occupied = weekday {OCC_START:02d}:00–{OCC_END:02d}:00 {TZ}",
        color="#e8eef4",
        fontsize=13,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = CHARTS / "zone_temp_occ_unocc_by_month.png"
    fig.savefig(out, dpi=130, facecolor="#0f1419")
    plt.close(fig)
    print(f"chart: {out}")


def chart_zone_runtime(run_zone: pd.DataFrame) -> None:
    if run_zone.empty:
        return
    CHARTS.mkdir(parents=True, exist_ok=True)
    zones = sorted(run_zone["zone_id"].unique())
    ncols = 3
    nrows = int(np.ceil(len(zones) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 3.0 * nrows), sharey=True)
    fig.patch.set_facecolor("#0f1419")
    axes = np.atleast_1d(axes).ravel()
    for i, zid in enumerate(zones):
        ax = axes[i]
        ax.set_facecolor("#1a222c")
        s = run_zone[run_zone["zone_id"] == zid].sort_values("month")
        ax.bar(s["month"], s["avg_fan_run_hours"], color="#f0a04b", width=0.7)
        ax.set_title(zid, color="#e8eef4", fontsize=10)
        ax.tick_params(colors="#8b9aab", labelsize=7)
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, axis="y", color="#2a3544", alpha=0.6)
        for sp in ax.spines.values():
            sp.set_color("#2a3544")
        ax.set_ylabel("Avg HP fan hours", color="#8b9aab", fontsize=8)
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)
    fig.suptitle(
        "Lakeside avg heat-pump fan run hours per thermal zone × month",
        color="#e8eef4",
        fontsize=13,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = CHARTS / "zone_avg_fan_run_hours_by_month.png"
    fig.savefig(out, dpi=130, facecolor="#0f1419")
    plt.close(fig)
    print(f"chart: {out}")


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    hps = load_inventory()
    print(f"heat pumps in inventory: {len(hps)}")
    model = build_model(hps)
    MODEL_PATH.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
    # also copy to reports for easy find
    (REPORTS / "thermal_zone_model.json").write_text(
        json.dumps(model, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"model: {MODEL_PATH}  "
        f"floors={model['summary']['floor_count']}  "
        f"zones={model['summary']['thermal_zone_count']}  "
        f"hps={model['summary']['heat_pump_count']}"
    )

    temp_zone, temp_equip, run_equip, run_zone = analyze(model)
    temp_zone.to_csv(REPORTS / "zone_temp_monthly_occ_unocc.csv", index=False)
    temp_equip.to_csv(REPORTS / "equip_zone_temp_monthly_occ_unocc.csv", index=False)
    run_equip.to_csv(REPORTS / "equip_fan_run_hours_monthly.csv", index=False)
    run_zone.to_csv(REPORTS / "zone_avg_fan_run_hours_monthly.csv", index=False)

    print(f"zone temp rows: {len(temp_zone)}")
    print(f"equip temp rows: {len(temp_equip)}")
    print(f"equip run-hour rows: {len(run_equip)}")
    print(f"zone avg run-hour rows: {len(run_zone)}")
    if not temp_zone.empty:
        print(temp_zone.head(8).to_string(index=False))
    if not run_zone.empty:
        print(run_zone.head(8).to_string(index=False))

    chart_zone_temps(temp_zone)
    chart_zone_runtime(run_zone)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
