"""Pilot arm parameter builders and RL smoke helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from eplus_gym.control_v2 import SixZoneDailyParamsV2, arm_params, build_six_schedules_f, continuous_params
from eplus_gym.mega.fixed_rules import FIXED_TOU_RULE, FIXED_WEATHER_RULE
from eplus_gym.mega.tariff_modes import default_tariff_catalog
from eplus_gym.rl.midnight_forecast import forecast_from_epw_replay
from eplus_gym.rl.multiday_env import schedule_fingerprint
from eplus_gym.rl.research_spaces import (
    UNOCC_F_FLOOR_V2,
    decode_continuous_research_v2,
    decode_discrete_research_v2,
    discrete_action_space_research_v2,
)
from eplus_gym.rl.spaces_v2 import encode_continuous_v2


def weather_rule_params(*, day: str, epw: Path) -> SixZoneDailyParamsV2:
    min_oat = float(min(forecast_from_epw_replay(epw, day).temps_c))
    return FIXED_WEATHER_RULE.params_for_day(day, forecast_min_oat_c=min_oat)


def tou_rule_params(*, day: str, tariff_mode: str = "tou_evening_peak_illustrative") -> SixZoneDailyParamsV2:
    rates = default_tariff_catalog()[tariff_mode].hourly_prices().tolist()  # type: ignore[index]
    return FIXED_TOU_RULE.params_for_day(day, hourly_energy_rates=rates)


def random_continuous_params(*, day: str, seed: int) -> tuple[SixZoneDailyParamsV2, np.ndarray, list[float]]:
    rng = np.random.default_rng(int(seed))
    from eplus_gym.rl.research_spaces import continuous_action_space_research_v2

    space = continuous_action_space_research_v2()
    raw = rng.uniform(space.low, space.high).astype(np.float32)
    params = decode_continuous_research_v2(raw, day=day)
    decoded = encode_continuous_v2(params).astype(float).tolist()
    return params, raw, decoded


def random_discrete_action(*, day: str, seed: int) -> tuple[int, SixZoneDailyParamsV2]:
    rng = np.random.default_rng(int(seed))
    space = discrete_action_space_research_v2()
    action = int(rng.integers(0, space.n))
    params = decode_discrete_research_v2(action, day=day)
    return action, params


def deep_setback_params() -> SixZoneDailyParamsV2:
    return SixZoneDailyParamsV2(
        occupied_heating_f=70.0,
        unoccupied_heating_f=max(60.0, UNOCC_F_FLOOR_V2),
        heating_setpoint_start_step=32,
        heating_setpoint_end_step=59,
        recovery_lead_minutes=90,
        recovery_ramp_minutes=90,
    )


def scaffold_only_arms() -> list[str]:
    return ["grid_search", "day_ahead_optimizer"]


def action_record(
    *,
    arm: str,
    raw_action: Any,
    params: SixZoneDailyParamsV2,
    day: str,
    schedules: dict[str, list[float]] | None = None,
) -> dict[str, Any]:
    if schedules is None:
        from eplus_gym.rl.research_spaces import research_build_six_schedules_f

        try:
            schedules = build_six_schedules_f(params)
        except ValueError:
            schedules = research_build_six_schedules_f(params, day)
    return {
        "arm": arm,
        "day": day,
        "raw_action": raw_action.tolist() if hasattr(raw_action, "tolist") else raw_action,
        "decoded": encode_continuous_v2(params).astype(float).tolist(),
        "schedule_fingerprint": schedule_fingerprint(schedules),
    }


def rate_vector_sha256(tariff_mode: str) -> str:
    from eplus_gym.mega.tariff_modes import build_tariff_forecast_vectors

    rates = build_tariff_forecast_vectors(tariff_mode)["next_96x15min_energy_rates"]  # type: ignore[arg-type]
    return hashlib.sha256(json.dumps(list(rates)).encode("utf-8")).hexdigest()
