"""LIVE EnergyPlus two-month frozen-policy replay runners."""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

import numpy as np

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.control_v2 import continuous_params, observed_bas_incumbent_params
from eplus_gym.episode import run_controller_episode
from eplus_gym.envs.lakeside_w2a import LakesideW2AEnv
from eplus_gym.epw_stage import stage_year_aware_epw
from eplus_gym.objective import _facility_series
from eplus_gym.rl.billing_state import BillingState
from eplus_gym.rl.campaign_bundle import forecasts_from_epw
from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant
from eplus_gym.rl.multiday_env import schedule_fingerprint, trajectory_hash
from eplus_gym.rl.research_eval import load_sb3_model, predict_params
from eplus_gym.rl.research_poc import refuse_fake_plant
from eplus_gym.rl.research_spaces import (
    RESEARCH_ACTION_CONTRACT_V3,
    decode_discrete_research_v3,
    research_build_six_schedules_f,
    research_continuous_70,
)
from eplus_gym.rl.spaces_v2 import encode_continuous_v2
from eplus_gym.rl.reward_v2 import readiness_all_six
from eplus_gym.rl.two_month_calendar import (
    EXPECTED_INTERVALS_PER_STRATEGY,
    EXPECTED_SCORED_DAYS,
    FIRST_SCORED_DAY,
    LAST_SCORED_DAY,
    LOOKBACK_DAY,
    scored_days,
)
from eplus_gym.rl.two_month_obs import build_policy_observation_v4
from eplus_gym.rl.two_month_rolling import rolling_max_mean
from eplus_gym.site_pins import resolve_site_epw, sha256_file
from eplus_gym.stage_idf import stage_idf_for_period
from scripts.a04v2_compare_incumbent_schedules import SchHtgSpReplay, SETBACK_C

STRATEGIES = (
    "a04_native_sch_htgsp",
    "observed_bas_incumbent_v2",
    "continuous_68_heat_sensitivity",
    "frozen_ppo_flat_seed0",
    "frozen_dqn_tou_seed1",
    "grid_flat_discrete_42",
    "grid_tou_discrete_43",
)


class MultiDaySchHtgSpReplay:
    """Weekday-aware SCH_HtgSP for multi-day episodes (local step 0..N*96-1)."""

    def __init__(self, *, lookback_day: str, scored: list[str]):
        self.lookback_weekday = date.fromisoformat(lookback_day).weekday()
        self.scored = list(scored)

    def action_lookback(self, step: int) -> float:
        return SchHtgSpReplay.value_c(int(step) % 96, self.lookback_weekday)

    def action(self, step: int) -> float:
        day_idx = int(step) // 96
        day_idx = min(day_idx, len(self.scored) - 1)
        wd = date.fromisoformat(self.scored[day_idx]).weekday()
        return SchHtgSpReplay.value_c(int(step) % 96, wd)


def _daily_rows_from_payload(day: str, payload: dict[str, Any], *, strategy: str, extra: dict | None = None) -> dict[str, Any]:
    fac = [float(x) for x in payload["facility_kw"]]
    zones = payload.get("zone_temps_series_f") or {}
    ready = readiness_all_six(zones, day=day) if zones else {"readiness_ok": None}
    row = {
        "day": day,
        "strategy": strategy,
        "peak_kw": float(max(fac)),
        "peak_30min_mean_kw": rolling_max_mean(fac, 2),
        "peak_60min_mean_kw": rolling_max_mean(fac, 4),
        "daily_kwh": float(payload.get("daily_kwh") or sum(fac) * 0.25),
        "n_intervals": len(fac),
        "readiness_ok": ready.get("readiness_ok"),
        "schedule_fingerprint": payload.get("schedule_fingerprint"),
        "trajectory_hash": trajectory_hash(payload),
    }
    if extra:
        row.update(extra)
    return row


def run_six_zone_strategy(
    *,
    site: Path,
    app_root: Path,
    out_dir: Path,
    strategy: str,
    params_fn: Callable[[str], Any],
    policy_zip: Path | None = None,
    algo: str | None = None,
    tariff_mode: str = "flat_illustrative",
    queue_timeout_s: float = 900.0,
) -> dict[str, Any]:
    days = scored_days()
    epw = resolve_site_epw(site)
    idf = app_root / "models" / "eplus" / A04_IDF_NAME
    oat = forecasts_from_epw(epw, days)
    out_dir.mkdir(parents=True, exist_ok=True)
    plant = EnergyPlusContinuityPlant(
        site_root=site,
        epw=epw,
        idf=idf,
        output=out_dir,
        days=days,
        lookback_days=1,
        lookback_schedules=research_build_six_schedules_f(research_continuous_70(), LOOKBACK_DAY),
        queue_timeout_s=queue_timeout_s,
    )
    refuse_fake_plant(plant)
    billing = BillingState(floor_kw=0.0, ratchet_kw=0.0, contract_kw=0.0)
    t0 = time.perf_counter()
    model = (
        load_sb3_model(policy_zip, algo=str(algo), contract={"action_contract_version": RESEARCH_ACTION_CONTRACT_V3})
        if policy_zip
        else None
    )
    plant.start_episode()
    prev_action: list[float] = [0.0] * 11
    prev_peak = 0.0
    prev_kwh = 0.0
    prev_cc = 0.0
    daily: list[dict[str, Any]] = []
    facility_all: list[float] = []
    for day in days:
        billing.start_of_day(day)
        opening_mtd = billing.mtd_peak_kw
        if model is not None:
            obs, obs_ctx = build_policy_observation_v4(
                day=day,
                hourly_oat_c=oat[day][:24] if len(oat[day]) >= 24 else list(oat[day]),
                zone_temps_f=plant.zone_temps_f,
                billing_floor_kw=billing.billing_floor_kw(),
                mtd_peak_kw=billing.mtd_peak_kw,
                ratchet_floor_kw=billing.ratchet_kw,
                contract_floor_kw=billing.contract_kw,
                previous_action=prev_action,
                continuous_conditioning_state=prev_cc,
                tariff_mode=tariff_mode,
                previous_day_peak_kw=prev_peak,
                previous_day_kwh=prev_kwh,
            )
            params = predict_params(
                model=model,
                obs=obs,
                algo=str(algo),
                day=day,
                action_contract_version=RESEARCH_ACTION_CONTRACT_V3,
                expected_obs_dim=206,
            )
            action_note = "full_obs_v4_replay"
        else:
            params = params_fn(day)
            action_note = None
        sched = research_build_six_schedules_f(params, day)
        payload = plant.simulate_day(sched, oat_c=list(oat[day]))
        peak = float(max(payload["facility_kw"]))
        billing.observe_peak(peak)
        prev_action = encode_continuous_v2(params).astype(float).tolist()
        prev_peak = peak
        prev_kwh = float(payload["daily_kwh"])
        prev_cc = 1.0 if params.continuous_conditioning else 0.0
        payload["schedule_fingerprint"] = schedule_fingerprint(sched)
        payload["zone_temps_series_f"] = payload.get("zone_temps_series_f") or {}
        extra = {"opening_mtd_kw": opening_mtd, "closing_mtd_kw": billing.mtd_peak_kw}
        if action_note:
            extra["action_decode_note"] = action_note
        if model is not None:
            extra["obs_norm"] = float(np.linalg.norm(obs))
        row = _daily_rows_from_payload(day, payload, strategy=strategy, extra=extra)
        row["zone_temps_series_f"] = payload.get("zone_temps_series_f")
        daily.append(row)
        facility_all.extend([float(x) for x in payload["facility_kw"]])
        if plant.zone_temps_f:
            payload["start_zone_temps_f"] = list(plant.zone_temps_f)
    quality = plant.finish_quality()
    if len(facility_all) != EXPECTED_INTERVALS_PER_STRATEGY:
        raise ValueError(f"{strategy}: expected {EXPECTED_INTERVALS_PER_STRATEGY} intervals, got {len(facility_all)}")
    if len(daily) != EXPECTED_SCORED_DAYS:
        raise ValueError(f"{strategy}: expected {EXPECTED_SCORED_DAYS} days, got {len(daily)}")
    result = {
        "strategy": strategy,
        "baseline_contract_name": strategy,
        "facility_kw": facility_all,
        "daily": daily,
        "n_process_starts": int(plant.n_process_starts),
        "n_intervals": len(facility_all),
        "n_days": len(daily),
        "quality": quality,
        "elapsed_s": time.perf_counter() - t0,
        "idf_sha256": sha256_file(idf),
        "epw_sha256": sha256_file(epw),
        "trajectory_hash": trajectory_hash({"facility_kw": facility_all, "n_intervals": len(facility_all)}),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_a04_native(*, site: Path, app_root: Path, out_dir: Path) -> dict[str, Any]:
    days = scored_days()
    epw = resolve_site_epw(site)
    idf = app_root / "models" / "eplus" / A04_IDF_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    staged_epw = stage_year_aware_epw(epw, out_dir / f"staged_{epw.name}")["staged_epw"]
    staged = stage_idf_for_period(
        idf,
        out_dir / f"staged_{idf.name}",
        LOOKBACK_DAY,
        LAST_SCORED_DAY,
        site_root=site,
        six_zone_actuators=False,
    )
    ctrl = MultiDaySchHtgSpReplay(lookback_day=LOOKBACK_DAY, scored=days)

    def factory():
        return LakesideW2AEnv(
            {
                "epw": str(staged_epw),
                "idf": str(staged),
                "output": str(out_dir / "eplus"),
                "queue_timeout_s": 900.0,
                "six_zone_actuators": False,
                "default_action_c": SETBACK_C,
                "htg_schedule": "SCH_HtgSP",
            }
        )

    t0 = time.perf_counter()
    result_ep = run_controller_episode(
        factory, ctrl, lookback_days=1, scored_day=None, max_steps=(len(days) + 1) * 96
    )
    import pandas as pd

    df = pd.DataFrame(result_ep.get("all_rows") or result_ep["rows"])
    df.to_parquet(out_dir / "trajectory.parquet", index=False)
    non_lb = df[~df["lookback"].astype(bool)].reset_index(drop=True)
    if len(non_lb) != EXPECTED_INTERVALS_PER_STRATEGY:
        raise ValueError(
            f"a04 native expected {EXPECTED_INTERVALS_PER_STRATEGY} scored intervals, got {len(non_lb)}"
        )
    daily = []
    facility_all: list[float] = []
    for i, day in enumerate(days):
        chunk = non_lb.iloc[i * 96 : (i + 1) * 96]
        fac = _facility_series(chunk).tolist()
        if len(fac) != 96:
            raise ValueError(f"a04 native missing 96 intervals on {day}")
        payload = {
            "facility_kw": fac,
            "daily_kwh": float(sum(fac) * 0.25),
            "schedule_fingerprint": "SCH_HtgSP_native_multiday",
            "zone_temps_series_f": {},
        }
        daily.append(_daily_rows_from_payload(day, payload, strategy="a04_native_sch_htgsp"))
        facility_all.extend(fac)
    err_path = list(out_dir.rglob("eplusout.err"))
    quality = {}
    if err_path:
        from eplus_gym.eplus_err import parse_eplus_err

        quality = parse_eplus_err(err_path[0])
    out = {
        "strategy": "a04_native_sch_htgsp",
        "baseline_contract_name": "A04_NATIVE_CALIBRATION_REFERENCE",
        "facility_kw": facility_all,
        "daily": daily,
        "n_process_starts": 1,
        "n_intervals": len(facility_all),
        "n_days": len(daily),
        "quality": quality,
        "elapsed_s": time.perf_counter() - t0,
        "idf_sha256": sha256_file(idf),
        "epw_sha256": sha256_file(epw),
        "trajectory_hash": trajectory_hash({"facility_kw": facility_all, "n_intervals": len(facility_all)}),
    }
    (out_dir / "result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def run_strategy(*, strategy: str, site: Path, app_root: Path, site_out: Path) -> dict[str, Any]:
    out_dir = site_out / strategy
    if strategy == "a04_native_sch_htgsp":
        return run_a04_native(site=site, app_root=app_root, out_dir=out_dir)
    if strategy == "observed_bas_incumbent_v2":
        return run_six_zone_strategy(
            site=site,
            app_root=app_root,
            out_dir=out_dir,
            strategy=strategy,
            params_fn=lambda _d: observed_bas_incumbent_params(),
        )
    if strategy == "continuous_68_heat_sensitivity":
        return run_six_zone_strategy(
            site=site,
            app_root=app_root,
            out_dir=out_dir,
            strategy=strategy,
            params_fn=lambda _d: continuous_params(68.0),
        )
    if strategy == "grid_flat_discrete_42":
        return run_six_zone_strategy(
            site=site,
            app_root=app_root,
            out_dir=out_dir,
            strategy=strategy,
            params_fn=lambda d: decode_discrete_research_v3(42, day=d),
        )
    if strategy == "grid_tou_discrete_43":
        return run_six_zone_strategy(
            site=site,
            app_root=app_root,
            out_dir=out_dir,
            strategy=strategy,
            params_fn=lambda d: decode_discrete_research_v3(43, day=d),
        )
    if strategy == "frozen_ppo_flat_seed0":
        ppo = site / "reports/eplus_gym/rl/research_long_flat_plus_demand_20260820T132506Z/ppo_seed0/models/ppo_final.zip"
        return run_six_zone_strategy(
            site=site,
            app_root=app_root,
            out_dir=out_dir,
            strategy=strategy,
            params_fn=lambda _d: observed_bas_incumbent_params(),
            policy_zip=ppo,
            algo="PPO",
            tariff_mode="flat_illustrative",
        )
    if strategy == "frozen_dqn_tou_seed1":
        dqn = site / "reports/eplus_gym/rl/research_long_illustrative_tou_plus_demand_20260820T210304Z/dqn_seed1/models/dqn_final.zip"
        return run_six_zone_strategy(
            site=site,
            app_root=app_root,
            out_dir=out_dir,
            strategy=strategy,
            params_fn=lambda _d: observed_bas_incumbent_params(),
            policy_zip=dqn,
            algo="DQN",
            tariff_mode="tou_evening_peak_illustrative",
        )
    raise KeyError(strategy)
