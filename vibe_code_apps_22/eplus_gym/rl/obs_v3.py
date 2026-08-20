"""Observation contract v3: 24-hour hourly forecast + carry-forward state."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from eplus_gym.control_v2 import SixZoneDailyParamsV2, school_windows
from eplus_gym.rl.midnight_forecast import FORECAST_HOURS, forecast_from_epw_replay

OBS_SCHEMA_V3 = "vibe22.obs.v3"
PERFECT_EPISODE_FORECAST = "PERFECT_EPISODE_FORECAST"
LABELED_PLACEHOLDER_FORECAST = "LABELED_PLACEHOLDER_FORECAST"
N_PREV_ACTION = 11
# 24 oat + 24 mask + 6 calendar + 6 zones + 4 billing + 11 prev action + 1 cc + 2 loop + 2 masks
N_OBS_V3 = 24 + 24 + 6 + 6 + 4 + N_PREV_ACTION + 1 + 2 + 2


def observation_space_v3():
    import gymnasium as gym

    return gym.spaces.Box(low=-np.inf, high=np.inf, shape=(N_OBS_V3,), dtype=np.float32)


def normalize_previous_action(previous_action: Sequence[float]) -> list[float]:
    prev = [float(x) for x in previous_action]
    if len(prev) != N_PREV_ACTION:
        raise ValueError(f"previous_action must have {N_PREV_ACTION} values")
    return [
        prev[0] / 100.0,
        prev[1] / 14.0,
        prev[2] / 96.0,
        prev[3] / 96.0,
        prev[4] / 180.0,
        *[(x + 3.0) / 4.0 for x in prev[5:11]],
    ]


def build_observation_v3(
    *,
    day: str,
    hourly_oat_c: Sequence[float],
    forecast_valid_mask: Sequence[float] | None = None,
    forecast_source: str = PERFECT_EPISODE_FORECAST,
    zone_temps_f: Sequence[float],
    billing_floor_kw: float,
    mtd_peak_kw: float,
    previous_day_peak_kw: float = 0.0,
    previous_day_kwh: float = 0.0,
    previous_action: Sequence[float] | None = None,
    continuous_conditioning_state: float = 0.0,
    loop_entering_water_c: float | None = None,
    loop_leaving_water_c: float | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    oat = [float(x) for x in hourly_oat_c]
    if len(oat) != FORECAST_HOURS:
        raise ValueError(f"need {FORECAST_HOURS} hourly OAT values, got {len(oat)}")
    mask = [1.0] * FORECAST_HOURS
    if forecast_valid_mask is not None:
        mask = [float(x) for x in forecast_valid_mask]
        if len(mask) != FORECAST_HOURS:
            raise ValueError("forecast_valid_mask must be length 24")
    temps = [float(x) for x in zone_temps_f]
    if len(temps) != 6:
        raise ValueError("need 6 zone temps")
    prev = [0.0] * N_PREV_ACTION
    if previous_action is not None:
        prev = [float(x) for x in previous_action]
        if len(prev) != N_PREV_ACTION:
            raise ValueError(f"previous_action must have {N_PREV_ACTION} values")
    prev_norm = normalize_previous_action(prev)
    win = school_windows(day)
    d = date.fromisoformat(str(day)[:10])
    ewt_present = 1.0 if loop_entering_water_c is not None else 0.0
    lwt_present = 1.0 if loop_leaving_water_c is not None else 0.0
    vec = np.asarray(
        oat
        + mask
        + [
            d.month / 12.0,
            d.weekday() / 6.0,
            int(d.strftime("%j")) / 366.0,
            1.0 if win["school_occupied"] else 0.0,
            1.0 if win["thursday_early_dismissal"] else 0.0,
            1.0 if win["weekend"] else 0.0,
        ]
        + [t / 100.0 for t in temps]
        + [
            float(mtd_peak_kw) / 500.0,
            float(billing_floor_kw) / 500.0,
            float(previous_day_peak_kw) / 500.0,
            float(previous_day_kwh) / 5000.0,
        ]
        + prev_norm
        + [float(continuous_conditioning_state)]
        + [
            float(loop_entering_water_c) / 40.0 if loop_entering_water_c is not None else 0.0,
            float(loop_leaving_water_c) / 40.0 if loop_leaving_water_c is not None else 0.0,
            ewt_present,
            lwt_present,
        ],
        dtype=np.float32,
    )
    if vec.size != N_OBS_V3:
        raise ValueError(f"obs v3 size {vec.size} != {N_OBS_V3}")
    ctx = {
        "obs_schema": OBS_SCHEMA_V3,
        "forecast_source": forecast_source,
        "hourly_oat_c": oat,
        "forecast_valid_mask": mask,
        "day": win,
        "zone_temps_f": temps,
        "billing_floor_kw": float(billing_floor_kw),
        "mtd_peak_kw": float(mtd_peak_kw),
        "mtd_peak_distinct_from_billing_floor": True,
        "previous_day_peak_kw": float(previous_day_peak_kw),
        "previous_day_kwh": float(previous_day_kwh),
        "previous_action": prev,
        "previous_action_normalized": prev_norm,
        "continuous_conditioning_state": float(continuous_conditioning_state),
        "loop_entering_water_present": bool(ewt_present),
        "loop_leaving_water_present": bool(lwt_present),
        "no_future_weather_beyond_declared_forecast": True,
    }
    return vec, ctx


def observation_from_epw_truth(
    *,
    day: str,
    epw: Path,
    zone_temps_f: Sequence[float],
    billing_floor_kw: float,
    mtd_peak_kw: float,
    previous_day_peak_kw: float = 0.0,
    previous_day_kwh: float = 0.0,
    previous_action: Sequence[float] | None = None,
    continuous_conditioning_state: float = 0.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    fc = forecast_from_epw_replay(Path(epw), day)
    return build_observation_v3(
        day=day,
        hourly_oat_c=fc.temps_c,
        forecast_source=PERFECT_EPISODE_FORECAST,
        zone_temps_f=zone_temps_f,
        billing_floor_kw=billing_floor_kw,
        mtd_peak_kw=mtd_peak_kw,
        previous_day_peak_kw=previous_day_peak_kw,
        previous_day_kwh=previous_day_kwh,
        previous_action=previous_action,
        continuous_conditioning_state=continuous_conditioning_state,
    )


def params_to_prev_action(params: SixZoneDailyParamsV2) -> list[float]:
    from eplus_gym.rl.spaces_v2 import encode_continuous_v2

    return encode_continuous_v2(params).astype(float).tolist()
