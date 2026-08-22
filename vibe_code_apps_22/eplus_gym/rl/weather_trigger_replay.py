"""LIVE EnergyPlus weather-triggered continuous-conditioning multi-day replay."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.rl.billing_state import BillingState
from eplus_gym.rl.campaign_bundle import forecasts_from_epw
from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant
from eplus_gym.rl.multiday_env import schedule_fingerprint, trajectory_hash
from eplus_gym.rl.research_poc import refuse_fake_plant
from eplus_gym.rl.research_spaces import research_build_six_schedules_f, research_continuous_70
from eplus_gym.rl.reward_v2 import occupied_zone_degree_hours, readiness_all_six
from eplus_gym.rl.two_month_calendar import (
    EXPECTED_INTERVALS_PER_STRATEGY,
    EXPECTED_SCORED_DAYS,
    LOOKBACK_DAY,
    scored_days,
)
from eplus_gym.rl.two_month_rolling import rolling_max_mean
from eplus_gym.rl.weather_trigger_select import (
    load_weather_trigger_contract,
    oat_c_to_f,
    params_for_selection,
    select_daily_policy,
)
from eplus_gym.site_pins import resolve_site_epw, sha256_file

POLICY_IDS = (
    "ALWAYS_GRID_114",
    "ALWAYS_GRID_42",
    "ALWAYS_GRID_43",
    "ALWAYS_CONTINUOUS_68_74",
    "COLD_TRIGGER_10F",
    "COLD_TRIGGER_20F",
    "COLD_TRIGGER_30F",
    "COLD_TRIGGER_20F_4H",
    "COLD_TRIGGER_20F_8H",
)


def run_weather_policy(
    *,
    site: Path,
    app_root: Path,
    out_dir: Path,
    policy_id: str,
    queue_timeout_s: float = 900.0,
) -> dict[str, Any]:
    contract = load_weather_trigger_contract(app_root)
    if policy_id not in (contract.get("policy_ids") or POLICY_IDS):
        raise ValueError(f"unknown policy_id {policy_id}")
    days = scored_days()
    epw = resolve_site_epw(site)
    idf = Path(app_root) / "models" / "eplus" / A04_IDF_NAME
    oat_c = forecasts_from_epw(epw, days)
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
    plant.start_episode()
    daily: list[dict[str, Any]] = []
    facility_all: list[float] = []
    trigger_log: list[dict[str, Any]] = []
    prev_end_zones: list[float] | None = None
    for day in days:
        billing.start_of_day(day)
        opening_mtd = billing.mtd_peak_kw
        start_zones = list(plant.zone_temps_f) if plant.zone_temps_f else []
        if prev_end_zones is not None and start_zones:
            for a, b in zip(prev_end_zones, start_zones):
                if abs(float(a) - float(b)) > 0.05:
                    raise RuntimeError(
                        f"{policy_id} thermal discontinuity at {day}: {a} vs {b}"
                    )
        hourly_f = oat_c_to_f(oat_c[day][:24])
        selection = select_daily_policy(
            policy_id=policy_id, day=day, hourly_oat_f=hourly_f, contract=contract
        )
        params = params_for_selection(selection, day=day)
        sched = research_build_six_schedules_f(params, day)
        payload = plant.simulate_day(sched, oat_c=list(oat_c[day]))
        peak = float(max(payload["facility_kw"]))
        billing.observe_peak(peak)
        zones = payload.get("zone_temps_series_f") or {}
        ready = readiness_all_six(zones, day=day) if zones else {"readiness_ok": None, "checked": False}
        occ_dh = float(occupied_zone_degree_hours(zones, day=day) if zones else 0.0)
        end_zones = list(plant.zone_temps_f) if plant.zone_temps_f else []
        prev_end_zones = end_zones
        fac = [float(x) for x in payload["facility_kw"]]
        row = {
            "day": day,
            "strategy": policy_id,
            "selected_mode": selection.selected_mode,
            "continuous_day": selection.continuous_day,
            "trigger_reason": selection.trigger_reason,
            "peak_kw": peak,
            "peak_30min_mean_kw": rolling_max_mean(fac, 2),
            "peak_60min_mean_kw": rolling_max_mean(fac, 4),
            "daily_kwh": float(payload.get("daily_kwh") or sum(fac) * 0.25),
            "n_intervals": len(fac),
            "readiness_ok": ready.get("readiness_ok"),
            "school_day": ready.get("school_day"),
            "checked_school_day": bool(ready.get("checked")),
            "occupied_comfort_degree_hours": occ_dh,
            "schedule_fingerprint": schedule_fingerprint(sched),
            "trajectory_hash": trajectory_hash(payload),
            "opening_mtd_kw": opening_mtd,
            "closing_mtd_kw": billing.mtd_peak_kw,
            "start_zone_temps_f": start_zones,
            "end_zone_temps_f": end_zones,
            "zone_temps_series_f": zones,
            "hourly_oat_f": selection.hourly_oat_f,
        }
        daily.append(row)
        facility_all.extend(fac)
        tl = selection.to_dict()
        tl["strategy"] = policy_id
        trigger_log.append(tl)
    quality = plant.finish_quality()
    if len(facility_all) != EXPECTED_INTERVALS_PER_STRATEGY:
        raise ValueError(
            f"{policy_id}: expected {EXPECTED_INTERVALS_PER_STRATEGY} intervals, got {len(facility_all)}"
        )
    if len(daily) != EXPECTED_SCORED_DAYS:
        raise ValueError(f"{policy_id}: expected {EXPECTED_SCORED_DAYS} days, got {len(daily)}")
    if int(plant.n_process_starts) != 1:
        raise ValueError(f"{policy_id}: expected 1 EnergyPlus process, got {plant.n_process_starts}")
    n_cont = sum(1 for d in daily if d.get("continuous_day"))
    trigger_dates = [d["day"] for d in daily if d.get("continuous_day")]
    result = {
        "strategy": policy_id,
        "policy_id": policy_id,
        "baseline_contract_name": policy_id,
        "weather_label": "RETROSPECTIVE_WEATHER_POLICY_SCREEN",
        "facility_kw": facility_all,
        "daily": daily,
        "trigger_log": trigger_log,
        "n_continuous_days": n_cont,
        "trigger_dates": trigger_dates,
        "n_process_starts": int(plant.n_process_starts),
        "n_intervals": len(facility_all),
        "n_days": len(daily),
        "quality": quality,
        "elapsed_s": time.perf_counter() - t0,
        "idf_sha256": sha256_file(idf),
        "epw_sha256": sha256_file(epw),
        "trajectory_hash": trajectory_hash({"facility_kw": facility_all, "n_intervals": len(facility_all)}),
        "bacnet_command_authority": 0,
        "status": "OK",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out_dir / "trigger_log.json").write_text(json.dumps(trigger_log, indent=2), encoding="utf-8")
    return result


def import_two_month_reference(
    *,
    two_month_site_run: Path,
    strategy: str,
) -> dict[str, Any]:
    """Import a frozen two-month strategy result (no re-run)."""
    path = Path(two_month_site_run) / strategy / "result.json"
    if not path.is_file():
        alt = Path(two_month_site_run) / f"_result_{strategy}.json"
        path = alt if alt.is_file() else path
    if not path.is_file():
        raise FileNotFoundError(f"missing two-month result for {strategy}: {path}")
    blob = json.loads(path.read_text(encoding="utf-8"))
    if int(blob.get("n_intervals") or 0) != EXPECTED_INTERVALS_PER_STRATEGY:
        raise ValueError(f"{strategy}: imported intervals != 5952")
    blob["imported_from"] = str(path)
    blob["status"] = "OK"
    blob["weather_label"] = "RETROSPECTIVE_WEATHER_POLICY_SCREEN"
    return blob
