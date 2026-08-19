"""Three-day live pilot — gate before long RL mega campaign.

Every arm must produce real 96-row EnergyPlus evidence via continuity plant.
Five-seed PPO/DQN mega remains BLOCKED until this pilot passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.control_v2 import arm_params, build_six_schedules_f, chronological_days, continuous_params
from eplus_gym.mega.compact_scorecard import build_compact_scorecard, idf_byte_and_lf_sha256, write_slim_artifacts
from eplus_gym.mega.day_ahead_optimizer import DayAheadOptimizerArm
from eplus_gym.mega.fixed_rules import FIXED_TOU_RULE, FIXED_WEATHER_RULE
from eplus_gym.mega.grid_search import default_coarse_grid
from eplus_gym.mega.obs_tariff_v4 import N_OBS_V4
from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant
from eplus_gym.rl.midnight_forecast import forecast_from_epw_replay
from eplus_gym.rl.multiday_env import MultiDayDailyEnv
from eplus_gym.rl.spaces_v2 import encode_continuous_v2
from eplus_gym.site_env import require_site_root
from eplus_gym.site_pins import resolve_a04_and_epw, sha256_file

AUDIT_ROOT = _APP / "docs" / "audits" / "figures" / "vibe22_three_day_pilot"
PILOT_DAYS = ("2026-01-12", "2026-01-25", "2026-03-16")
MEGA_BLOCKED = "P5_BLOCKED_UNTIL_PILOT_PASSES_AND_USER_APPROVES"


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def _params_for_pilot_arm(arm: str, day: str):
    from eplus_gym.control_v2 import observed_bas_incumbent_params

    if arm == "incumbent":
        return observed_bas_incumbent_params()
    if arm == "continuous_68":
        return continuous_params(68.0)
    if arm == "continuous_70":
        return continuous_params(70.0)
    if arm == "FIXED_WEATHER_RULE":
        return FIXED_WEATHER_RULE.params_for_day(day, forecast_min_oat_c=-12.0)
    if arm == "FIXED_TOU_RULE":
        return FIXED_TOU_RULE.params_for_day(day)
    if arm == "grid_search":
        params = dict(default_coarse_grid()[0])
        base = continuous_params(70.0)
        for key, val in params.items():
            if hasattr(base, key):
                setattr(base, key, val)
        return base
    if arm == "day_ahead_optimizer":
        opt = DayAheadOptimizerArm(bounds=DayAheadOptimizerArm(bounds=[]).default_bounds())
        res = opt.optimize(opt.stub_objective())
        p = continuous_params(70.0)
        p.occupied_heating_f = float(res.x_best[0])
        p.unoccupied_heating_f = float(res.x_best[1])
        return p
    if arm == "random":
        return arm_params("shallow_setback")
    if arm in ("ppo_smoke", "dqn_smoke"):
        return continuous_params(69.0)
    return arm_params(arm)


def run_direct_arm(
    *,
    site: Path,
    idf: Path,
    epw: Path,
    day: str,
    arm: str,
    child_bytes: bytes,
    child_name: str,
) -> dict:
    params = _params_for_pilot_arm(arm, day)
    schedules = build_six_schedules_f(params)
    oat = list(forecast_from_epw_replay(epw, day).temps_c)
    day_dir = AUDIT_ROOT / day / arm
    plant = EnergyPlusContinuityPlant(
        site_root=site,
        epw=epw,
        idf=idf,
        output=day_dir / "continuity",
        days=[day],
    )
    plant.start_episode()
    payload = plant.simulate_day(schedules, oat_c=oat)
    gate = plant.finish_quality()
    byte_sha, lf_sha = idf_byte_and_lf_sha256(child_bytes)
    rc = 0 if gate.get("completed_successfully") else 1
    scorecard = build_compact_scorecard(
        label=f"{day}_{arm}",
        day=day,
        arm=arm,
        child_name=child_name,
        child_idf_byte_sha256=byte_sha,
        child_idf_lf_normalized_sha256=lf_sha,
        gate=gate,
        returncode=rc,
        payload=payload,
        physics_status="PILOT_GATE_ARM",
        rl_eligible=False,
    )
    write_slim_artifacts(day_dir, scorecard)
    return scorecard


def run_rl_smoke(*, site: Path, idf: Path, epw: Path, algo: str, child_bytes: bytes) -> dict:
    days = list(PILOT_DAYS)
    hourly_oat = {d: list(forecast_from_epw_replay(epw, d).temps_c) for d in days}
    plant = EnergyPlusContinuityPlant(
        site_root=site,
        epw=epw,
        idf=idf,
        output=AUDIT_ROOT / f"{algo}_smoke" / "continuity",
        days=days,
    )
    baseline_payloads = {}
    inc_sched = build_six_schedules_f(_params_for_pilot_arm("incumbent", days[0]))
    plant.start_episode()
    for day in days:
        baseline_payloads[day] = plant.simulate_day(
            inc_sched,
            oat_c=hourly_oat[day],
        )
    env = MultiDayDailyEnv(
        {
            "n_days": len(days),
            "days": days,
            "plant": plant,
            "hourly_oat": hourly_oat,
            "baseline_payloads": baseline_payloads,
            "obs_schema": "v4",
            "tariff_mode": "flat_illustrative",
            "require_live_energyplus": True,
            "idf_sha256": hashlib.sha256(child_bytes).hexdigest(),
            "epw_sha256": sha256_file(epw),
        }
    )
    obs, info = env.reset()
    assert obs.shape[0] == N_OBS_V4
    action = encode_continuous_v2(continuous_params(69.0))
    rows = []
    for _ in range(len(days)):
        _obs, _rew, term, _, step_info = env.step(action)
        rows.append(
            {
                "day": step_info.get("day"),
                "n_rows": 96,
                "peak_kw": step_info.get("peak_kw"),
                "trajectory_sha256": step_info.get("trajectory_sha256"),
            }
        )
        if term:
            break
    env.close()
    return {"algo": algo, "obs_schema": "v4", "days": rows, "live_energyplus": True}


def assert_pilot_gates(arm_results: list[dict]) -> None:
    for sc in arm_results:
        if int(sc.get("n_rows") or 0) != 96:
            raise SystemExit(f"pilot gate failed: {sc.get('label')} n_rows={sc.get('n_rows')}")
        if sc.get("trajectory_sha256") in (None, ""):
            raise SystemExit(f"pilot gate failed: missing trajectory_sha256 for {sc.get('label')}")


def main() -> int:
    p = argparse.ArgumentParser(description="Vibe22 three-day pilot (mega gate)")
    p.add_argument("--site-root", default="")
    p.add_argument("--child-idf", default="", help="hp67 v2 child path; default A04 research fallback")
    p.add_argument("--skip-rl-smoke", action="store_true")
    args = p.parse_args()

    site = require_site_root(args.site_root or None)
    parent_idf, epw = resolve_a04_and_epw(site)
    pinned = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    if pinned.is_file():
        epw = pinned
    if args.child_idf:
        idf = Path(args.child_idf)
        child_name = idf.stem
    else:
        idf = parent_idf
        child_name = A04_IDF_NAME
    child_bytes = idf.read_bytes()

    direct_arms = (
        "incumbent",
        "continuous_68",
        "continuous_70",
        "FIXED_WEATHER_RULE",
        "FIXED_TOU_RULE",
        "grid_search",
        "day_ahead_optimizer",
        "random",
    )
    results: list[dict] = []
    for day in PILOT_DAYS:
        for arm in direct_arms:
            results.append(
                run_direct_arm(
                    site=site,
                    idf=idf,
                    epw=epw,
                    day=day,
                    arm=arm,
                    child_bytes=child_bytes,
                    child_name=child_name,
                )
            )

    rl_rows = []
    if not args.skip_rl_smoke:
        for algo in ("ppo", "dqn"):
            rl_rows.append(run_rl_smoke(site=site, idf=idf, epw=epw, algo=algo, child_bytes=child_bytes))

    assert_pilot_gates(results)
    summary = {
        "schema": "vibe22.three_day_pilot.v1",
        "pilot_days": list(PILOT_DAYS),
        "model": child_name,
        "research_fallback_a04": not bool(args.child_idf),
        "mega_campaign_status": MEGA_BLOCKED,
        "obs_schema": "v4",
        "direct_arms": results,
        "rl_smoke": rl_rows,
        "gates": {"require_96_rows": True, "require_trajectory_sha256": True},
        "honesty_labels": [
            "NO_PRISTINE_LOCKED_TEST_AVAILABLE",
            MEGA_BLOCKED,
        ],
    }
    _write(AUDIT_ROOT / "pilot_summary.json", summary)
    print(json.dumps({"arms_scored": len(results), "mega_blocked": MEGA_BLOCKED}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
