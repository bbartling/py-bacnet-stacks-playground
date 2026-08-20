"""Run one scored civil day via EnergyPlusContinuityPlant (96-row contract)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from eplus_gym.control_v2 import SixZoneDailyParamsV2, build_six_schedules_f
from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant
from eplus_gym.rl.eplus_watchdog import EplusWatchdog, WatchdogLimits, WatchdogTimeout
from eplus_gym.rl.midnight_forecast import forecast_from_epw_replay
from eplus_gym.trackb_scored_run import rows_from_continuity_payload


def params_for_arm(arm: str, *, day: str, epw: Path | None = None, tariff_mode: str = "tou_evening_peak_illustrative") -> SixZoneDailyParamsV2:
    from eplus_gym.control_v2 import arm_params, continuous_params, observed_bas_incumbent_params
    from eplus_gym.mega.fixed_rules import FIXED_TOU_RULE, FIXED_WEATHER_RULE
    from eplus_gym.mega.tariff_modes import default_tariff_catalog

    if arm == "incumbent":
        return observed_bas_incumbent_params()
    if arm == "continuous_68":
        return continuous_params(68.0)
    if arm == "continuous_70":
        return continuous_params(70.0)
    if arm == "shallow_setback":
        from eplus_gym.rl.research_eval import _shallow

        return _shallow()
    if arm == "deep_setback":
        from eplus_gym.rl.research_spaces import UNOCC_F_FLOOR_V2

        return SixZoneDailyParamsV2(
            occupied_heating_f=70.0,
            unoccupied_heating_f=max(60.0, UNOCC_F_FLOOR_V2),
            heating_setpoint_start_step=32,
            heating_setpoint_end_step=59,
            recovery_lead_minutes=90,
            recovery_ramp_minutes=90,
        )
    if arm == "FIXED_WEATHER_RULE":
        min_oat = -12.0
        if epw is not None:
            min_oat = float(min(forecast_from_epw_replay(epw, day).temps_c))
        return FIXED_WEATHER_RULE.params_for_day(day, forecast_min_oat_c=min_oat)
    if arm == "FIXED_TOU_RULE":
        rates = default_tariff_catalog()[tariff_mode].hourly_prices().tolist()
        return FIXED_TOU_RULE.params_for_day(day, hourly_energy_rates=rates)
    return arm_params(arm)


def _hourly_oat(epw: Path, day: str) -> list[float]:
    fc = forecast_from_epw_replay(epw, day)
    vals = [float(x) for x in fc.temps_c]
    if len(vals) != 24:
        raise ValueError(f"EPW replay for {day} must yield 24 hourly values, got {len(vals)}")
    return vals


def run_scored_continuity_day(
    *,
    site_root: Path,
    idf: Path,
    epw: Path,
    day: str,
    arm: str,
    output: Path,
    queue_timeout_s: float = 180.0,
    tariff_mode: str = "tou_evening_peak_illustrative",
) -> dict[str, Any]:
    params = params_for_arm(arm, day=day, epw=epw, tariff_mode=tariff_mode)
    schedules = build_six_schedules_f(params)
    oat = _hourly_oat(epw, day)
    watchdog = EplusWatchdog(
        output / "watchdog",
        WatchdogLimits(startup_s=1200.0, no_progress_s=600.0, overall_s=7200.0),
    )
    plant = EnergyPlusContinuityPlant(
        site_root=site_root,
        epw=epw,
        idf=idf,
        output=output / "continuity",
        days=[day],
        queue_timeout_s=queue_timeout_s,
    )
    watchdog.heartbeat("before_start_episode")
    try:
        plant.start_episode()
        watchdog.mark_started(note="after_start_episode")
        payload = plant.simulate_day(schedules, oat_c=oat)
        watchdog.heartbeat("after_simulate_day")
    except WatchdogTimeout:
        plant.close()
        raise
    except Exception:
        plant.close()
        watchdog.fail_artifact("scored_day_exception")
        raise
    gate = plant.finish_quality()
    watchdog.heartbeat("after_finish_quality")
    rows = rows_from_continuity_payload(payload, expected_day=day)
    return {
        "payload": payload,
        "rows": rows,
        "gate": gate,
        "watchdog": watchdog.snapshot(),
        "arm": arm,
        "schedules": schedules,
        "hourly_oat_c": oat,
        "n_process_starts": int(payload.get("n_process_starts") or plant.n_process_starts),
    }
