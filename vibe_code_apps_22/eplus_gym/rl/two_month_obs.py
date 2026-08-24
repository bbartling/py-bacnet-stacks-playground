"""Observation v4 builder for two-month frozen-policy replay."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from eplus_gym.mega.obs_tariff_v4 import N_OBS_V4, build_observation_v4
from eplus_gym.rl.research_eval import PolicyReloadError


def assert_obs_nonzero(obs: np.ndarray, *, context: str) -> None:
    obs = np.asarray(obs, dtype=np.float32).reshape(-1)
    if obs.size != N_OBS_V4:
        raise PolicyReloadError(f"{context}: obs dim {obs.size} != {N_OBS_V4}")
    if float(np.linalg.norm(obs)) <= 1e-9:
        raise PolicyReloadError(f"{context}: refusing all-zero observation vector")


def build_policy_observation_v4(
    *,
    day: str,
    hourly_oat_c: Sequence[float],
    zone_temps_f: Sequence[float],
    billing_floor_kw: float,
    mtd_peak_kw: float,
    ratchet_floor_kw: float,
    contract_floor_kw: float,
    previous_action: Sequence[float] | None,
    continuous_conditioning_state: float,
    tariff_mode: str,
    previous_day_peak_kw: float = 0.0,
    previous_day_kwh: float = 0.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    obs, ctx = build_observation_v4(
        day=day,
        hourly_oat_c=hourly_oat_c,
        forecast_valid_mask=[1.0] * 24,
        zone_temps_f=zone_temps_f,
        billing_floor_kw=billing_floor_kw,
        mtd_peak_kw=mtd_peak_kw,
        ratchet_floor_kw=ratchet_floor_kw,
        contract_floor_kw=contract_floor_kw,
        previous_action=previous_action,
        continuous_conditioning_state=continuous_conditioning_state,
        tariff_mode=tariff_mode,  # type: ignore[arg-type]
        previous_day_peak_kw=previous_day_peak_kw,
        previous_day_kwh=previous_day_kwh,
    )
    assert_obs_nonzero(obs, context=f"day={day}")
    ctx["forecast_source"] = "PERFECT_EPISODE_FORECAST_RETROSPECTIVE"
    return obs, ctx
