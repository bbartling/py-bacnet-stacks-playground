"""Freeze BAS/Gym incumbent control contract from train_dev winter weekdays."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.site_env import require_site_root
from eplus_gym.six_zone_daily_controller import incumbent_lookback_params

GATE = {"2026-01-25", "2026-01-26", "2026-03-16"}


def freeze_from_bas(df: pd.DataFrame, ledger: pd.DataFrame) -> dict:
    t = pd.to_datetime(df["timestamp_local"])
    work = df.copy()
    work["timestamp_local"] = t
    work["date"] = t.dt.date.astype(str)
    work = work.merge(ledger[["date", "fold"]], on="date", how="left")
    winter = work[
        work["fold"].eq("train_dev")
        & ~work["date"].isin(GATE)
        & (t.dt.month.isin([12, 1, 2]))
        & (work["is_weekend"].astype(float) < 0.5)
    ]
    occ = winter[winter["occupied"].astype(float) > 0.5]
    unocc = winter[winter["occupied"].astype(float) < 0.5]
    # Occupancy start: first occupied step per weekday
    starts = []
    for _, g in occ.groupby("date"):
        ts = pd.to_datetime(g["timestamp_local"]).min()
        starts.append(ts.hour + ts.minute / 60.0)
    gym = incumbent_lookback_params()
    return {
        "schema": "vibe22.a04v2.incumbent_control_contract.v1",
        "split": "train_dev winter weekdays; Jan 25/26 and Mar 16 excluded",
        "n_intervals": int(len(winter)),
        "bas_occ_htg_sp_f_median": float(occ["occ_htg_sp_f"].median()) if len(occ) else None,
        "bas_unocc_htg_sp_f_median": float(unocc["unocc_htg_sp_f"].median()) if len(unocc) else None,
        "bas_occupancy_start_hour_median": float(pd.Series(starts).median()) if starts else None,
        "gym_incumbent": {
            "occupied_heating_f": gym.occupied_heating_f,
            "unoccupied_heating_f": gym.unoccupied_heating_f,
            "occupancy_start_step": gym.occupancy_start_step,
            "occupancy_end_step": gym.occupancy_end_step,
            "recovery_ramp_minutes": gym.recovery_ramp_minutes,
            "note": "07:00 start (step 28), 60-min recovery 06:00-07:00, DualSP 70/65",
        },
        "a04_sch_htgsp": {
            "setback_c": 7.78,
            "setback_f": 46.004,
            "occupied_c": 21.11,
            "occupied_f": 69.998,
            "until_occupied_local": "03:15",
            "note": "03:15 is calendar 06:45 minus optimum_start_h=3.5, not BAS occupancy",
        },
        "candidate_peak_comparison_uses": "gym_incumbent",
        "label": "smoke_calibration_not_heldout",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", default=None)
    args = p.parse_args()
    site = require_site_root(args.site_root)
    df = pd.read_parquet(site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet")
    ledger = pd.read_csv(_APP / "docs" / "audits" / "figures" / "a04v2" / "phase2" / "day_event_ledger.csv")
    body = freeze_from_bas(df, ledger)
    out = _APP / "docs" / "audits" / "figures" / "a04v2" / "incumbent_control_contract.json"
    out.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: body[k] for k in ("bas_occ_htg_sp_f_median", "bas_unocc_htg_sp_f_median", "bas_occupancy_start_hour_median")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
