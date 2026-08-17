"""January 2026 peak + monthly kWh screen for an A04-v2 candidate (LIVE E+).

Runs one incumbent day (2026-01-26) already covered by ramp; additionally runs
calendar month 2026-01 as a contiguous EnergyPlus period for monthly kWh vs utility.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.episode import run_controller_episode
from eplus_gym.envs.lakeside_w2a import LakesideW2AEnv
from eplus_gym.eplus_err import assert_eplus_quality, parse_eplus_err
from eplus_gym.epw_stage import stage_year_aware_epw
from eplus_gym.objective import _facility_series
from eplus_gym.six_zone_daily_controller import SixZoneDailyController, incumbent_lookback_params
from eplus_gym.stage_idf import stage_idf_for_period
from eplus_native.w2a_monthly_hold import (
    PEAK_BAND_HI_KW,
    PEAK_BAND_LO_KW,
    UTILITY_JAN2026_DEMAND_KW,
    peak_band_pass,
)

# Frozen before selection (mission): ±10% of Jan 2026 utility billed demand
PEAK_TOL_FRAC = 0.10


def run_month(*, site: Path, epw: Path, idf: Path, out: Path, begin: str, end: str) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    staged_epw = stage_year_aware_epw(epw, out / f"staged_{epw.name}")["staged_epw"]
    staged = stage_idf_for_period(
        idf,
        out / f"staged_{idf.name}",
        begin,
        end,
        site_root=site,
        six_zone_actuators=True,
    )
    ctrl = SixZoneDailyController(incumbent_lookback_params())

    def factory():
        return LakesideW2AEnv(
            {
                "epw": str(staged_epw),
                "idf": str(staged),
                "output": str(out / "eplus"),
                "queue_timeout_s": 300.0,
                "occupied_heating_f": float(ctrl.params.occupied_heating_f),
                "default_action_c": list(ctrl.action(0)),
                "six_zone_actuators": True,
            }
        )

    # Full month ~31 days × 96 steps
    from datetime import date

    n_days = (date.fromisoformat(end) - date.fromisoformat(begin)).days + 1
    result = run_controller_episode(
        factory, ctrl, lookback_days=0, scored_day=None, max_steps=int(n_days) * 96
    )
    df = pd.DataFrame(result["rows"])
    df.to_parquet(out / "trajectory.parquet", index=False)
    err = out / "eplus" / "eplusout.err"
    if not err.is_file():
        found = list(out.rglob("eplusout.err"))
        err = found[0] if found else err
    gate = parse_eplus_err(err)
    assert_eplus_quality(gate)
    fac = _facility_series(df)
    peak = float(fac.max())
    kwh = float(fac.sum() * 0.25)
    return {
        "begin": begin,
        "end": end,
        "n_rows": int(len(df)),
        "peak_kw": peak,
        "kwh": kwh,
        "severe": int(gate.get("severe_count") or 0),
        "fatal": int(gate.get("fatal_count") or 0),
        "eplus_quality": gate,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--idf", type=Path, required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--site-root", type=Path, default=Path(os.environ.get("SITE_ROOT") or ""))
    args = p.parse_args()
    site = args.site_root
    epw = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    out = _APP / "docs" / "audits" / "figures" / "a04v2" / "stageA" / args.run_id / "jan2026_month"
    # Jan 2026 full month
    month = run_month(site=site, epw=epw, idf=args.idf, out=out, begin="2026-01-01", end="2026-01-31")
    util_kwh = 81491.0
    util_peak = UTILITY_JAN2026_DEMAND_KW
    peak_tol = {
        "anchor_kw": util_peak,
        "tol_frac": PEAK_TOL_FRAC,
        "lo_kw": util_peak * (1 - PEAK_TOL_FRAC),
        "hi_kw": util_peak * (1 + PEAK_TOL_FRAC),
        "legacy_band": peak_band_pass(month["peak_kw"]),
    }
    peak_tol["pass_frozen_10pct"] = peak_tol["lo_kw"] <= month["peak_kw"] <= peak_tol["hi_kw"]
    # also require legacy 250-290 band for continuity with A04 dial
    peak_tol["pass"] = bool(peak_tol["pass_frozen_10pct"] and peak_tol["legacy_band"]["pass"])
    report = {
        "schema": "vibe22.a04v2.jan2026_screen.v1",
        "run_id": args.run_id,
        "idf": str(args.idf),
        "month": month,
        "utility_jan2026_kwh": util_kwh,
        "utility_jan2026_demand_kw": util_peak,
        "kwh_pct_diff": 100.0 * (month["kwh"] - util_kwh) / util_kwh,
        "peak_tolerance_frozen_before_selection": peak_tol,
        "label": "January-only diagnostic; not a full partial-period GL14 screen",
    }
    (out / "jan2026_screen.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["peak_tolerance_frozen_before_selection"]["pass"] else 5


if __name__ == "__main__":
    raise SystemExit(main())
