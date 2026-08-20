"""Run immutable A04 under SCH_HtgSP replay vs Gym/BAS incumbent. Jan 26 is smoke/calibration, not holdout."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.demand_windows import demand_window_report
from eplus_gym.episode import run_controller_episode
from eplus_gym.envs.lakeside_w2a import LakesideW2AEnv
from eplus_gym.epw_stage import stage_year_aware_epw
from eplus_gym.objective import _facility_series
from eplus_gym.path_sanitize import redact_obj
from eplus_gym.site_env import require_site_root
from eplus_gym.six_zone_daily_controller import SixZoneDailyController, incumbent_lookback_params
from eplus_gym.stage_idf import stage_idf_for_period

SETBACK_C = 7.78
OCC_C = 21.11


class SchHtgSpReplay:
    """Replay A04 SCH_HtgSP on the scalar Schedule Value actuator.

    DualSP six-zone schedules stay off (``six_zone_actuators=False``). Values match
    IDF lines 853-879: 7.78 °C until 03:15, then 21.11 °C until 15:30 weekdays
    (Thursday 13:30); weekends 7.78 °C all day.
    """

    def __init__(self, *, scored_weekday: int, lookback_weekday: int):
        self.scored_weekday = int(scored_weekday)
        self.lookback_weekday = int(lookback_weekday)

    @staticmethod
    def value_c(step: int, weekday: int) -> float:
        t = int(step) % 96
        if weekday >= 5:
            return SETBACK_C
        occ_end = 54 if weekday == 3 else 62  # Thu 13:30 else 15:30
        start = 13  # 03:15
        if start <= t < occ_end:
            return OCC_C
        return SETBACK_C

    def action(self, step: int):
        return self.value_c(step, self.scored_weekday)

    def action_lookback(self, step: int):
        return self.value_c(step, self.lookback_weekday)


def run_arm(*, site: Path, epw: Path, idf: Path, out: Path, begin: str, end: str, controller, six_zone: bool) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    staged_epw = stage_year_aware_epw(epw, out / f"staged_{epw.name}")["staged_epw"]
    staged = stage_idf_for_period(
        idf,
        out / f"staged_{idf.name}",
        begin,
        end,
        site_root=site,
        six_zone_actuators=six_zone,
    )

    def factory():
        cfg = {
            "epw": str(staged_epw),
            "idf": str(staged),
            "output": str(out / "eplus"),
            "queue_timeout_s": 300.0,
            "six_zone_actuators": six_zone,
        }
        if six_zone and isinstance(controller, SixZoneDailyController):
            cfg["occupied_heating_f"] = float(controller.params.occupied_heating_f)
            cfg["default_action_c"] = list(controller.action(0))
        else:
            cfg["default_action_c"] = SETBACK_C
            cfg["htg_schedule"] = "SCH_HtgSP"
        return LakesideW2AEnv(cfg)

    result = run_controller_episode(factory, controller, lookback_days=1, scored_day=None, max_steps=192)
    df = pd.DataFrame(result["rows"])
    df.to_parquet(out / "trajectory.parquet", index=False)
    fac = _facility_series(df)
    idx = pd.date_range(begin, periods=len(fac), freq="15min")
    windows = demand_window_report(pd.Series(fac.to_numpy(), index=idx))
    return {"n_rows": int(len(df)), "native_max_kw": windows["native_max_kw"], "windows": windows}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", default=None)
    p.add_argument("--day", default="2026-01-26")
    args = p.parse_args()
    site = require_site_root(args.site_root)
    epw = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    idf = _APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    root = _APP / "docs" / "audits" / "figures" / "a04v2" / "incumbent_schedule_compare"
    day = pd.Timestamp(args.day)
    lookback = (day - pd.Timedelta(days=1)).date().isoformat()
    a = run_arm(
        site=site,
        epw=epw,
        idf=idf,
        out=root / "sch_htgsp",
        begin=lookback,
        end=args.day,
        controller=SchHtgSpReplay(scored_weekday=int(day.dayofweek), lookback_weekday=int((day - pd.Timedelta(days=1)).dayofweek)),
        six_zone=False,
    )
    b = run_arm(
        site=site,
        epw=epw,
        idf=idf,
        out=root / "gym_incumbent",
        begin=lookback,
        end=args.day,
        controller=SixZoneDailyController(incumbent_lookback_params()),
        six_zone=True,
    )
    report = redact_obj(
        {
            "schema": "vibe22.a04v2.incumbent_schedule_compare.v1",
            "day": args.day,
            "label": "smoke_calibration_not_heldout",
            "sch_htgsp": a,
            "gym_incumbent": b,
            "peak_delta_kw": (b["native_max_kw"] or 0) - (a["native_max_kw"] or 0),
            "explanation": (
                "SCH_HtgSP uses 46°F setback until 03:15 (optimum-start shifted 06:45) then 70°F. "
                "Gym DualSP uses 65°F overnight and 06:00-07:00 recovery to 70°F. Peaks are not interchangeable. "
                "Candidate peak comparisons use gym_incumbent only."
            ),
        }
    )
    (root / "compare.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"sch_htgsp_max": a["native_max_kw"], "gym_max": b["native_max_kw"], "delta": report["peak_delta_kw"]},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
