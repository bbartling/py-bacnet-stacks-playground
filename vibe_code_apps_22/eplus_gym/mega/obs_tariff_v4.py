"""Phase 6: observation contract v4 — weather + tariff forecasts for PPO/DQN."""
from __future__ import annotations

from datetime import date
from typing import Any, Sequence

import numpy as np

from eplus_gym.mega.tariff_modes import (
    INTERVALS_PER_DAY,
    REQUIRED_MODES,
    TariffMode,
    build_tariff_forecast_vectors,
)
from eplus_gym.rl.midnight_forecast import FORECAST_HOURS
from eplus_gym.rl.obs_v3 import N_PREV_ACTION, normalize_previous_action

OBS_SCHEMA_V4 = "vibe22.obs.v4.mega"
N_TARIFF_MODES = len(REQUIRED_MODES)
# v3 base (80) + 24 hourly prices + 96 quarter-hour prices + tariff mode mask
N_OBS_V4 = 80 + FORECAST_HOURS + INTERVALS_PER_DAY + N_TARIFF_MODES


def observation_space_v4():
    import gymnasium as gym

    return gym.spaces.Box(low=-np.inf, high=np.inf, shape=(N_OBS_V4,), dtype=np.float32)


def build_observation_v4(
    *,
    day: str,
    hourly_oat_c: Sequence[float],
    forecast_valid_mask: Sequence[float] | None,
    zone_temps_f: Sequence[float],
    billing_floor_kw: float,
    mtd_peak_kw: float,
    ratchet_floor_kw: float,
    contract_floor_kw: float,
    previous_action: Sequence[float] | None,
    continuous_conditioning_state: float,
    tariff_mode: TariffMode,
    tariff_forecast: dict[str, Any] | None = None,
    previous_day_peak_kw: float = 0.0,
    previous_day_kwh: float = 0.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    from eplus_gym.control_v2 import school_windows
    from eplus_gym.rl.obs_v3 import build_observation_v3

    base, ctx = build_observation_v3(
        day=day,
        hourly_oat_c=hourly_oat_c,
        forecast_valid_mask=forecast_valid_mask,
        zone_temps_f=zone_temps_f,
        billing_floor_kw=billing_floor_kw,
        mtd_peak_kw=mtd_peak_kw,
        previous_day_peak_kw=previous_day_peak_kw,
        previous_day_kwh=previous_day_kwh,
        previous_action=previous_action,
        continuous_conditioning_state=continuous_conditioning_state,
    )
    fc = tariff_forecast or build_tariff_forecast_vectors(tariff_mode)
    hourly_prices = np.asarray(fc["next_24h_energy_rates"], dtype=np.float32) / 0.5
    qtr_prices = np.asarray(fc["next_96x15min_energy_rates"], dtype=np.float32) / 0.5
    mode_mask = np.asarray(fc["tariff_mode_mask"], dtype=np.float32)
    vec = np.concatenate([base, hourly_prices, qtr_prices, mode_mask]).astype(np.float32)
    if vec.size != N_OBS_V4:
        raise ValueError(f"obs v4 size {vec.size} != {N_OBS_V4}")
    d = date.fromisoformat(str(day)[:10])
    win = school_windows(day)
    ctx = {
        **ctx,
        "obs_schema": OBS_SCHEMA_V4,
        "tariff_mode": tariff_mode,
        "next_24h_energy_rates": fc["next_24h_energy_rates"],
        "next_96x15min_energy_rates": fc["next_96x15min_energy_rates"],
        "tariff_mode_mask": fc["tariff_mode_mask"],
        "ratchet_floor_kw": float(ratchet_floor_kw),
        "contract_floor_kw": float(contract_floor_kw),
        "billing_floor_kw_distinct": True,
        "calendar": {
            "month": d.month,
            "weekday": d.weekday(),
            "school_occupied": win["school_occupied"],
        },
        "previous_action_normalized": (
            normalize_previous_action(previous_action) if previous_action else None
        ),
        "future_tariff_in_observation": True,
    }
    return vec, ctx
