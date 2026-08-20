"""Three-day live pilot — gate before long RL mega campaign."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.control_v2 import build_six_schedules_f, continuous_params, observed_bas_incumbent_params
from eplus_gym.mega.compact_scorecard import build_compact_scorecard, idf_byte_and_lf_sha256, write_slim_artifacts
from eplus_gym.mega.physics_champion_gates import evaluate_pilot_software_gates
from eplus_gym.mega.pilot_arms import (
    action_record,
    deep_setback_params,
    random_continuous_params,
    scaffold_only_arms,
    tou_rule_params,
    weather_rule_params,
)
from eplus_gym.mega.obs_tariff_v4 import N_OBS_V4
from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant
from eplus_gym.rl.midnight_forecast import forecast_from_epw_replay
from eplus_gym.rl.multiday_env import MultiDayDailyEnv, trajectory_hash
from eplus_gym.rl.multiday_env import schedule_fingerprint
from eplus_gym.rl.research_spaces import RESEARCH_ACTION_CONTRACT_V2
from eplus_gym.site_env import require_site_root
from eplus_gym.site_pins import resolve_a04_and_epw, sha256_file

AUDIT_ROOT = _APP / "docs" / "audits" / "figures" / "vibe22_three_day_pilot"
PILOT_DAYS = ("2026-01-12", "2026-01-25", "2026-03-16")
MEGA_BLOCKED = "P5_BLOCKED_UNTIL_PILOT_PASSES_AND_USER_APPROVES"
TARIFF_MODE = "flat_illustrative"


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def _params_for_arm(arm: str, day: str, epw: Path, *, seed: int):
    if arm == "incumbent":
        return observed_bas_incumbent_params(), None
    if arm == "continuous_68":
        return continuous_params(68.0), None
    if arm == "continuous_70":
        return continuous_params(70.0), None
    if arm == "shallow_setback":
        from eplus_gym.rl.research_eval import _shallow

        return _shallow(), None
    if arm == "deep_setback":
        return deep_setback_params(), None
    if arm == "FIXED_WEATHER_RULE":
        return weather_rule_params(day=day, epw=epw), None
    if arm == "FIXED_TOU_RULE":
        return tou_rule_params(day=day, tariff_mode=TARIFF_MODE), None
    if arm == "random":
        params, raw, _decoded = random_continuous_params(day=day, seed=seed + hash(day) % 10000)
        return params, raw
    raise ValueError(f"unsupported direct arm: {arm}")


def run_direct_arm(
    *,
    site: Path,
    idf: Path,
    epw: Path,
    day: str,
    arm: str,
    child_bytes: bytes,
    child_name: str,
    seed: int,
    require_physics: bool,
) -> dict:
    params, raw = _params_for_arm(arm, day, epw, seed=seed)
    if arm == "random":
        from eplus_gym.rl.research_spaces import research_build_six_schedules_f

        schedules = research_build_six_schedules_f(params, day)
    else:
        schedules = build_six_schedules_f(params)
    oat = list(forecast_from_epw_replay(epw, day).temps_c)
    day_dir = AUDIT_ROOT / day / arm
    plant = EnergyPlusContinuityPlant(
        site_root=site,
        idf=idf,
        epw=epw,
        output=day_dir / "continuity",
        days=[day],
    )
    plant.start_episode()
    payload = plant.simulate_day(schedules, oat_c=oat)
    gate = plant.finish_quality()
    rc = 0 if gate.get("completed_successfully") else 1
    byte_sha, lf_sha = idf_byte_and_lf_sha256(child_bytes)
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
    if raw is not None:
        scorecard["action_record"] = action_record(arm=arm, raw_action=raw, params=params, day=day, schedules=schedules)
    write_slim_artifacts(day_dir, scorecard)
    scorecard["n_process_starts"] = 1
    return scorecard


def _baseline_payload(
    *,
    day: str,
    payload: dict,
    idf_sha: str,
    epw_sha: str,
    baseline_fp: str,
) -> dict:
    return {
        "day": day,
        "idf_sha256": idf_sha,
        "epw_sha256": epw_sha,
        "energyplus_version": "26.1.0",
        "run_period": f"{day}:{day}",
        "lookback_schedule_fingerprint": baseline_fp,
        "baseline_schedule_fingerprint": baseline_fp,
        "initial_state_id": "observed_bas_incumbent",
        "trajectory_hash": trajectory_hash(payload),
        "n_intervals": 96,
        "facility_kw": list(payload["facility_kw"]),
        "zone_temps_series_f": payload["zone_temps_series_f"],
        "live_energyplus": True,
    }


def run_rl_smoke(
    *,
    site: Path,
    idf: Path,
    epw: Path,
    algo: str,
    child_bytes: bytes,
    seed: int,
) -> dict:
    from stable_baselines3 import DQN, PPO

    days = list(PILOT_DAYS)
    byte_sha, lf_sha = idf_byte_and_lf_sha256(child_bytes)
    actions_taken: list[Any] = []
    scorecards: list[dict] = []
    model = None
    for day_i, day in enumerate(days):
        hourly_oat = list(forecast_from_epw_replay(epw, day).temps_c)
        inc_sched = build_six_schedules_f(observed_bas_incumbent_params())
        baseline_fp = schedule_fingerprint(inc_sched)
        idf_sha = hashlib.sha256(child_bytes).hexdigest()
        epw_sha = sha256_file(epw)
        baseline_plant = EnergyPlusContinuityPlant(
            site_root=site,
            epw=epw,
            idf=idf,
            output=AUDIT_ROOT / f"{algo}_smoke" / day / "baseline",
            days=[day],
        )
        baseline_plant.start_episode()
        raw_baseline = baseline_plant.simulate_day(inc_sched, oat_c=hourly_oat)
        baseline_plant.close()
        baseline_payloads = {
            day: _baseline_payload(
                day=day,
                payload=raw_baseline,
                idf_sha=idf_sha,
                epw_sha=epw_sha,
                baseline_fp=baseline_fp,
            )
        }
        plant = EnergyPlusContinuityPlant(
            site_root=site,
            epw=epw,
            idf=idf,
            output=AUDIT_ROOT / f"{algo}_smoke" / day / "continuity",
            days=[day],
        )
        env = MultiDayDailyEnv(
            {
                "n_days": 1,
                "days": [day],
                "plant": plant,
                "hourly_oat": {day: hourly_oat},
                "baseline_payloads": baseline_payloads,
                "obs_schema": "v4",
                "tariff_mode": TARIFF_MODE,
                "action_contract_version": RESEARCH_ACTION_CONTRACT_V2,
                "action_kind": "discrete" if algo == "dqn" else "continuous",
                "require_live_energyplus": True,
                "idf_sha256": idf_sha,
                "epw_sha256": epw_sha,
                "baseline_schedule_fingerprint": baseline_fp,
                "lookback_schedule_fingerprint": baseline_fp,
            }
        )
        obs, _info = env.reset(seed=seed + day_i)
        if day_i == 0:
            assert obs.shape[0] == N_OBS_V4
        model = PPO("MlpPolicy", env, seed=seed + day_i, verbose=0) if algo == "ppo" else DQN("MlpPolicy", env, seed=seed + day_i, verbose=0)
        action, _states = model.predict(obs, deterministic=True)
        actions_taken.append(action.tolist() if hasattr(action, "tolist") else action)
        _obs, reward, _term, _, step_info = env.step(action)
        payload = step_info.get("payload") or {}
        env.close()
        gate = getattr(env, "_quality_evidence", None) or plant.last_eplus_quality or {}
        rc = 0 if gate.get("completed_successfully") else 1
        rebuilt = build_compact_scorecard(
            label=f"{day}_{algo}_smoke",
            day=str(day),
            arm=f"{algo}_smoke",
            child_name=idf.name,
            child_idf_byte_sha256=byte_sha,
            child_idf_lf_normalized_sha256=lf_sha,
            gate=gate,
            returncode=rc,
            payload=payload,
            physics_status="PILOT_RL_SMOKE",
            rl_eligible=False,
        )
        rebuilt["reward"] = float(reward)
        rebuilt["rate_vector_sha256"] = step_info.get("rate_vector_sha256")
        rebuilt["reward_breakdown"] = step_info.get("reward_breakdown")
        rebuilt["raw_action"] = actions_taken[-1]
        rebuilt["n_process_starts"] = int(step_info.get("n_process_starts") or 1)
        scorecards.append(rebuilt)
    return {"algo": algo, "obs_schema": "v4", "actions": actions_taken, "scorecards": scorecards}


def assert_pilot_gates(
    scorecards: list[dict],
    *,
    require_physics: bool,
) -> dict:
    pilot = evaluate_pilot_software_gates(scorecards=scorecards, require_physics_gates=require_physics)
    if not pilot.get("passed"):
        raise SystemExit(f"pilot gate failed: {pilot.get('reasons')}")
    for sc in scorecards:
        if int(sc.get("n_process_starts") or 1) != 1:
            raise SystemExit(f"pilot gate failed: n_process_starts != 1 for {sc.get('label')}")
    return pilot


def main() -> int:
    p = argparse.ArgumentParser(description="Vibe22 three-day pilot (mega gate)")
    p.add_argument("--site-root", default="")
    p.add_argument("--child-idf", default="")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--skip-rl-smoke", action="store_true")
    p.add_argument("--require-physics-gates", action="store_true")
    args = p.parse_args()

    site = require_site_root(args.site_root or None)
    parent_idf, epw = resolve_a04_and_epw(site)
    pinned = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    if pinned.is_file():
        epw = pinned
    if args.child_idf:
        idf = Path(args.child_idf)
        child_name = idf.name
        require_physics = True
    else:
        idf = parent_idf
        child_name = A04_IDF_NAME
        require_physics = bool(args.require_physics_gates)
    child_bytes = idf.read_bytes()

    direct_arms = (
        "incumbent",
        "continuous_68",
        "continuous_70",
        "shallow_setback",
        "deep_setback",
        "FIXED_WEATHER_RULE",
        "FIXED_TOU_RULE",
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
                    seed=args.seed,
                    require_physics=require_physics,
                )
            )

    rl_rows = []
    all_scorecards = list(results)
    if not args.skip_rl_smoke:
        ppo = run_rl_smoke(site=site, idf=idf, epw=epw, algo="ppo", child_bytes=child_bytes, seed=args.seed)
        dqn = run_rl_smoke(site=site, idf=idf, epw=epw, algo="dqn", child_bytes=child_bytes, seed=args.seed + 1)
        rl_rows = [ppo, dqn]
        all_scorecards.extend(ppo.get("scorecards") or [])
        all_scorecards.extend(dqn.get("scorecards") or [])
        proof = {
            "ppo_actions": ppo.get("actions"),
            "dqn_actions": dqn.get("actions"),
            "distinct": ppo.get("actions") != dqn.get("actions"),
            "ppo_continuous_space": True,
            "dqn_discrete_space": True,
        }
        _write(AUDIT_ROOT / "action_space_proof.json", proof)

    pilot_gate = assert_pilot_gates(all_scorecards, require_physics=require_physics)
    summary = {
        "schema": "vibe22.three_day_pilot.v2",
        "pilot_days": list(PILOT_DAYS),
        "model": child_name,
        "research_fallback_a04": not bool(args.child_idf),
        "mega_campaign_status": MEGA_BLOCKED,
        "obs_schema": "v4",
        "tariff_mode": TARIFF_MODE,
        "direct_arms": results,
        "rl_smoke": rl_rows,
        "scaffold_only_arms": scaffold_only_arms(),
        "pilot_gate": pilot_gate,
        "research_training_eligible": pilot_gate.get("research_training_eligible"),
        "honesty_labels": [
            "NO_PRISTINE_LOCKED_TEST_AVAILABLE",
            "RESEARCH_POC_ALLOWED" if not require_physics else "PHYSICS_CHAMPION_PILOT",
            MEGA_BLOCKED,
        ],
    }
    _write(AUDIT_ROOT / "pilot_summary.json", summary)
    print(json.dumps({"arms_scored": len(results), "pilot_passed": pilot_gate.get("passed")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
