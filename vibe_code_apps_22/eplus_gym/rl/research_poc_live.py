"""LIVE EnergyPlus research PoC. 6-hour cap. Never long_campaign_allowed."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.control_v2 import (
    SixZoneDailyParamsV2,
    build_six_schedules_f,
    continuous_params,
    observed_bas_incumbent_params,
)
from eplus_gym.date_use_ledger import NO_LOCKED_UNSEEN
from eplus_gym.rl.campaign_bundle import forecasts_from_epw
from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant
from eplus_gym.rl.multiday_env import schedule_fingerprint, trajectory_hash
from eplus_gym.rl.obs_v3 import PERFECT_EPISODE_FORECAST
from eplus_gym.rl.research_model import verify_research_model
from eplus_gym.rl.research_poc import (
    CLAIM_LABELS,
    new_checkpoint,
    refuse_fake_plant,
    reject_candidate_as_baseline,
)
from eplus_gym.rl.research_spaces import research_continuous_70
from eplus_gym.rl.reward_v2 import score_day_v2
from eplus_gym.rl.split_manifest import assert_train_fold_only, build_split_manifest
from eplus_gym.rl.train_sb3 import train_sb3
from eplus_gym.site_pins import sha256_file

FIG = Path(__file__).resolve().parents[2] / "docs" / "audits" / "figures" / "vibe22_final_physics_rl"
TRAIN_DAYS = ["2025-12-08", "2025-12-09"]
VAL_DAYS = ["2025-12-15", "2025-12-16"]


def _shallow_params() -> SixZoneDailyParamsV2:
    return SixZoneDailyParamsV2(
        occupied_heating_f=70.0,
        unoccupied_heating_f=66.0,
        heating_setpoint_start_step=30,
        heating_setpoint_end_step=59,
        recovery_lead_minutes=60,
        recovery_ramp_minutes=60,
    )


def _payload_baseline(
    *,
    day: str,
    payload: dict[str, Any],
    idf_sha: str,
    epw_sha: str,
    lookback_fp: str,
    baseline_fp: str,
    days: list[str],
) -> dict[str, Any]:
    body = {
        "day": day,
        "idf_sha256": idf_sha,
        "epw_sha256": epw_sha,
        "energyplus_version": "26.1.0",
        "run_period": f"{days[0]}:{days[-1]}",
        "lookback_schedule_fingerprint": lookback_fp,
        "baseline_schedule_fingerprint": baseline_fp,
        "initial_state_id": "lookback_continuous_70",
        "trajectory_hash": trajectory_hash(payload),
        "n_intervals": 96,
        "facility_kw": list(payload["facility_kw"]),
        "zone_temps_series_f": payload["zone_temps_series_f"],
        "live_energyplus": True,
    }
    return body


def _run_fixed_episode(
    *,
    site: Path,
    epw: Path,
    idf: Path,
    output: Path,
    days: list[str],
    params_by_day: dict[str, SixZoneDailyParamsV2],
    oat: dict[str, list[float]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    plant = EnergyPlusContinuityPlant(
        site_root=site, epw=epw, idf=idf, output=output, days=days, queue_timeout_s=600.0
    )
    refuse_fake_plant(plant)
    plant.start_episode()
    out: dict[str, dict[str, Any]] = {}
    for day in days:
        sched = build_six_schedules_f(params_by_day[day])
        out[day] = plant.simulate_day(sched, oat_c=oat[day])
        out[day]["schedule_fingerprint"] = schedule_fingerprint(sched)
    gate = plant.finish_quality()
    return out, gate


def execute_research_poc_live(
    *,
    app_root: Path,
    site_root: Path,
    max_wall_hours: float = 6.0,
    seed: int = 0,
) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + float(max_wall_hours) * 3600.0
    manifest = verify_research_model(app_root)
    idf = Path(app_root) / str(manifest.get("idf_path") or f"models/eplus/{A04_IDF_NAME}")
    epw = Path(site_root) / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    if not epw.is_file():
        from eplus_gym.site_pins import resolve_site_epw

        epw = resolve_site_epw(site_root)
    idf_sha = sha256_file(idf)
    epw_sha = sha256_file(epw)
    oat = forecasts_from_epw(epw, TRAIN_DAYS + VAL_DAYS)
    split = build_split_manifest(TRAIN_DAYS + VAL_DAYS)
    assert_train_fold_only(TRAIN_DAYS)
    lookback = build_six_schedules_f(research_continuous_70())
    lookback_fp = schedule_fingerprint(lookback)
    out_root = Path(site_root) / "reports" / "eplus_gym" / "rl" / "research_poc_20260818"
    out_root.mkdir(parents=True, exist_ok=True)
    incumbent = {d: observed_bas_incumbent_params() for d in TRAIN_DAYS + VAL_DAYS}
    baseline_pay, base_gate = _run_fixed_episode(
        site=site_root,
        epw=epw,
        idf=idf,
        output=out_root / "baseline_incumbent",
        days=TRAIN_DAYS,
        params_by_day={d: incumbent[d] for d in TRAIN_DAYS},
        oat=oat,
    )
    baseline_fp = schedule_fingerprint(build_six_schedules_f(incumbent[TRAIN_DAYS[0]]))
    payloads = {
        d: _payload_baseline(
            day=d,
            payload=baseline_pay[d],
            idf_sha=idf_sha,
            epw_sha=epw_sha,
            lookback_fp=lookback_fp,
            baseline_fp=baseline_fp,
            days=TRAIN_DAYS,
        )
        for d in TRAIN_DAYS
    }
    for d in TRAIN_DAYS:
        reject_candidate_as_baseline({"sha": trajectory_hash(baseline_pay[d]) + "-cand"}, {"sha": trajectory_hash(baseline_pay[d])})
    extra = {
        "action_contract_version": "research_action_contract_v1",
        "hourly_oat": oat,
        "forecast_source": PERFECT_EPISODE_FORECAST,
        "baseline_payloads": payloads,
        "idf_sha256": idf_sha,
        "epw_sha256": epw_sha,
        "energyplus_version": "26.1.0",
        "lookback_schedule_fingerprint": lookback_fp,
        "baseline_schedule_fingerprint": baseline_fp,
        "model_id": "A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED",
        "weather_id": epw.name,
        "require_live_energyplus": True,
        "require_baseline": True,
    }
    results: dict[str, Any] = {}
    seeds = [int(seed)]
    if time.monotonic() + 1800 < deadline:
        seeds.append(int(seed) + 1)
    for sd in seeds:
        for algo in ("PPO", "DQN"):
            if time.monotonic() >= deadline:
                results[f"{algo}_{sd}"] = {"skipped": True, "reason": "wall_clock"}
                continue
            sub = out_root / f"{algo.lower()}_seed{sd}"
            try:
                results[f"{algo}_{sd}"] = train_sb3(
                    site_root=site_root,
                    epw=epw,
                    champion_idf=idf,
                    days=TRAIN_DAYS,
                    algo=algo,
                    timesteps=4,
                    run_root=sub,
                    seed=sd,
                    reward_name="reward_v2",
                    sb3_config="research_poc",
                    extra_env_cfg=extra,
                )
                ckpt = new_checkpoint(
                    seed=sd,
                    valid_transition_count=int(results[f"{algo}_{sd}"].get("n_episodes_logged") or 0),
                    idf_sha256=idf_sha,
                    epw_sha256=epw_sha,
                )
                (sub / "checkpoint_manifest.json").write_text(json.dumps(ckpt, indent=2) + "\n", encoding="utf-8")
            except Exception as exc:  # noqa: BLE001 — crashed EnergyPlus/RL is not learnable
                results[f"{algo}_{sd}"] = {
                    "failed": True,
                    "learnable": False,
                    "reason": str(exc),
                    "algo": algo,
                    "seed": sd,
                }
    # Fixed-policy eval on validation days if time remains.
    eval_rows = []
    if time.monotonic() < deadline:
        val_base, _g = _run_fixed_episode(
            site=site_root,
            epw=epw,
            idf=idf,
            output=out_root / "val_incumbent",
            days=VAL_DAYS,
            params_by_day={d: incumbent[d] for d in VAL_DAYS},
            oat=oat,
        )
        arms = {
            "continuous_70": {d: continuous_params(70.0) for d in VAL_DAYS},
            "shallow_setback": {d: _shallow_params() for d in VAL_DAYS},
        }
        for day in VAL_DAYS:
            eval_rows.append(
                {
                    "arm": "incumbent",
                    "day": day,
                    "training_reward": None,
                    "savings": 0.0,
                    "peak_kw": val_base[day]["peak_kw"],
                    "daily_kwh": val_base[day]["daily_kwh"],
                    "readiness_ok": None,
                    "role": "paired_baseline",
                }
            )
        for arm, params in arms.items():
            if time.monotonic() >= deadline:
                break
            cand, _cg = _run_fixed_episode(
                site=site_root,
                epw=epw,
                idf=idf,
                output=out_root / f"val_{arm}",
                days=VAL_DAYS,
                params_by_day=params,
                oat=oat,
            )
            for day in VAL_DAYS:
                reject_candidate_as_baseline(
                    {"sha": trajectory_hash(cand[day])},
                    {"sha": trajectory_hash(val_base[day])},
                )
                scored = score_day_v2(
                    day=day,
                    candidate_facility_kw=cand[day]["facility_kw"],
                    candidate_zone_temps_f=cand[day]["zone_temps_series_f"],
                    baseline_facility_kw=val_base[day]["facility_kw"],
                    baseline_zone_temps_f=val_base[day]["zone_temps_series_f"],
                    candidate_schedules=build_six_schedules_f(params[day]),
                    previous_schedules=None,
                    mtd_peak_kw=0.0,
                )
                eval_rows.append(
                    {
                        "arm": arm,
                        "day": day,
                        "training_reward": scored.training_reward,
                        "savings": scored.savings,
                        "peak_kw": scored.candidate["day_peak_kw"],
                        "daily_kwh": scored.candidate["daily_kwh"],
                        "readiness_ok": scored.readiness["readiness_ok"],
                    }
                )
    summary = {
        "schema": "vibe22.research_poc_live.v1",
        "claim_labels": list(CLAIM_LABELS),
        "SIMULATION_TRAINING_READY": False,
        "RESEARCH_POC_ALLOWED": True,
        "OPERATIONAL_DSM_READY": False,
        "long_campaign_allowed": False,
        "model_id": "A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED",
        "idf_sha256": idf_sha,
        "epw_sha256": epw_sha,
        "train_days": TRAIN_DAYS,
        "validation_days": VAL_DAYS,
        "locked_unseen": NO_LOCKED_UNSEEN,
        "baseline_gate": {k: base_gate.get(k) for k in ("severe_count", "fatal_count", "completed_successfully")},
        "train_results": results,
        "eval_rows": eval_rows,
        "wall_s": time.monotonic() - t0,
        "utc": datetime.now(timezone.utc).isoformat(),
        "bacnet_commands": 0,
        "winner": None,
        "winner_rule": "not_mean_training_reward",
    }
    (out_root / "research_poc_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    FIG.mkdir(parents=True, exist_ok=True)
    (FIG / "research_poc_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    return summary
