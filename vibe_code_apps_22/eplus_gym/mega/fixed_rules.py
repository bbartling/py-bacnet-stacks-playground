"""Phase 9: FIXED_WEATHER_RULE and FIXED_TOU_RULE deterministic arms."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

from eplus_gym.control_v2 import SixZoneDailyParamsV2, observed_bas_incumbent_params

FixedRuleArm = Literal["FIXED_WEATHER_RULE", "FIXED_TOU_RULE"]


@dataclass(frozen=True)
class FixedRuleSpec:
    arm: FixedRuleArm
    label: str
    params_fn_name: str
    deterministic: bool = True

    def params_for_day(
        self,
        day: str,
        *,
        forecast_min_oat_c: float | None = None,
        hourly_energy_rates: Sequence[float] | None = None,
    ) -> SixZoneDailyParamsV2:
        _ = day
        if self.arm == "FIXED_WEATHER_RULE":
            return _weather_rule_params(forecast_min_oat_c=forecast_min_oat_c)
        return _tou_rule_params(hourly_energy_rates=hourly_energy_rates)


def _weather_rule_params(*, forecast_min_oat_c: float | None) -> SixZoneDailyParamsV2:
    base = observed_bas_incumbent_params()
    recovery = 90
    if forecast_min_oat_c is not None:
        if forecast_min_oat_c <= -10.0:
            recovery = 120
        elif forecast_min_oat_c <= 0.0:
            recovery = 90
        else:
            recovery = 60
    return SixZoneDailyParamsV2(
        occupied_heating_f=base.occupied_heating_f,
        unoccupied_heating_f=max(64.0, base.unoccupied_heating_f - 2.0),
        heating_setpoint_start_step=base.heating_setpoint_start_step,
        heating_setpoint_end_step=base.heating_setpoint_end_step,
        recovery_lead_minutes=recovery,
        recovery_ramp_minutes=recovery,
    )


def _tou_rule_params(*, hourly_energy_rates: Sequence[float] | None) -> SixZoneDailyParamsV2:
    base = observed_bas_incumbent_params()
    start_step = max(28, base.heating_setpoint_start_step - 4)
    end_step = min(64, base.heating_setpoint_end_step + 4)
    if hourly_energy_rates is not None and len(hourly_energy_rates) >= 20:
        peak_hour = max(range(24), key=lambda h: float(hourly_energy_rates[h]))
        if peak_hour <= 10:
            start_step = max(20, base.heating_setpoint_start_step - 8)
        elif peak_hour >= 16:
            start_step = max(32, base.heating_setpoint_start_step - 2)
    return SixZoneDailyParamsV2(
        occupied_heating_f=base.occupied_heating_f,
        unoccupied_heating_f=base.unoccupied_heating_f,
        heating_setpoint_start_step=start_step,
        heating_setpoint_end_step=end_step,
        recovery_lead_minutes=60,
        recovery_ramp_minutes=45,
    )


FIXED_WEATHER_RULE = FixedRuleSpec(
    "FIXED_WEATHER_RULE",
    "Weather-sensitive setback + extended morning recovery",
    "weather_rule_v1",
)
FIXED_TOU_RULE = FixedRuleSpec(
    "FIXED_TOU_RULE",
    "TOU-aware preheat/cool window shift (deterministic schedule)",
    "tou_rule_v1",
)


def all_fixed_rules() -> list[FixedRuleSpec]:
    return [FIXED_WEATHER_RULE, FIXED_TOU_RULE]


def arm_manifest() -> dict[str, Any]:
    return {
        "schema": "vibe22.mega.fixed_rules.v1",
        "label": "CONTRACT_ONLY",
        "arms": [
            {
                "arm": r.arm,
                "label": r.label,
                "params_fn": r.params_fn_name,
                "deterministic": r.deterministic,
            }
            for r in all_fixed_rules()
        ],
    }
