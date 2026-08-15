"""P1 EnergyPlus gates: 3-day subprocess smoke + Jan 26 paired physics."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.rl.live_day_worker import run_live_day_subprocess
from eplus_gym.six_zone_daily_controller import SixZoneDailyParams, incumbent_lookback_params


def main() -> int:
    site = Path(os.environ.get("SITE_ROOT") or "")
    if not site.is_dir():
        print("SITE_ROOT required", file=sys.stderr)
        return 2
    epw = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    idf = _APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    out = _APP / "docs" / "audits" / "figures" / "postfix"
    out.mkdir(parents=True, exist_ok=True)
    days = ["2026-01-25", "2026-01-26", "2026-03-16"]
    smoke = []
    for day in days:
        ep_dir = out / "smoke" / day
        payload = run_live_day_subprocess(
            site_root=site,
            epw=epw,
            champion_idf=idf,
            day=day,
            params=incumbent_lookback_params().to_dict(),
            ep_dir=ep_dir,
            lookback_days=1,
            reward_name="legacy_reward_v1",
        )
        q = payload.get("eplus_quality") or {}
        rec = q.get("recurring") or {}
        row = {
            "day": day,
            "failed": payload.get("failed"),
            "n_rows": payload.get("n_rows"),
            "n_all_rows": payload.get("n_all_rows"),
            "severe": q.get("severe_count"),
            "fatal": q.get("fatal_count"),
            "actuator_handle_warnings": rec.get("actuator_handle"),
            "peak_kw": payload.get("peak_kw"),
            "daily_kwh": payload.get("daily_kwh"),
        }
        smoke.append(row)
        print(json.dumps(row))
        if payload.get("failed") or row["n_rows"] != 96 or row["n_all_rows"] != 192:
            print("SMOKE FAIL", row, file=sys.stderr)
            return 2
        if int(row["severe"] or 0) or int(row["fatal"] or 0):
            print("SEVERE/FATAL", row, file=sys.stderr)
            return 2
    inc = run_live_day_subprocess(
        site_root=site,
        epw=epw,
        champion_idf=idf,
        day="2026-01-26",
        params=incumbent_lookback_params().to_dict(),
        ep_dir=out / "pair_incumbent",
        lookback_days=1,
        reward_name="legacy_reward_v1",
    )
    pert = SixZoneDailyParams(occupied_heating_f=68.0, unoccupied_heating_f=58.0)
    cand = run_live_day_subprocess(
        site_root=site,
        epw=epw,
        champion_idf=idf,
        day="2026-01-26",
        params=pert.to_dict(),
        ep_dir=out / "pair_perturbed",
        lookback_days=1,
        reward_name="legacy_reward_v1",
    )
    pair = {
        "incumbent_peak": inc.get("peak_kw"),
        "perturbed_peak": cand.get("peak_kw"),
        "incumbent_kwh": inc.get("daily_kwh"),
        "perturbed_kwh": cand.get("daily_kwh"),
        "physics_moved": (
            inc.get("peak_kw") != cand.get("peak_kw")
            or inc.get("daily_kwh") != cand.get("daily_kwh")
        ),
        "incumbent_failed": inc.get("failed"),
        "perturbed_failed": cand.get("failed"),
    }
    (out / "p1_gates.json").write_text(json.dumps({"smoke": smoke, "pair": pair}, indent=2) + "\n")
    print(json.dumps(pair, indent=2))
    if not pair["physics_moved"] or inc.get("failed") or cand.get("failed"):
        print("NO-GO physics inert or failed", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
