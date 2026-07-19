"""App-owned IDF text patches for ECMs EnergyPlus-MCP cannot fully edit yet."""

from .capacity import apply_capacity_factors
from .chiller_lockout import apply_chiller_lockout
from .deep_retrofit import (
    apply_air_to_water_heat_pump_surrogate,
    apply_condensing_boiler_efficiency,
    apply_high_efficiency_chiller,
    apply_high_performance_glazing,
    apply_premium_fan_vfd,
)
from .gl36_proxy import apply_gl36_airside_proxy
from .hourly_outputs import apply_hourly_outputs, apply_monthly_energy_tables
from .registry import apply_patch, known_patch_names
from .run_period import apply_run_period
from .sat_reset import apply_sat_reset
from .schedules import apply_fan_avail_continuous, apply_fan_avail_occupied_office
from .ventilation import apply_outdoor_air_fraction

__all__ = [
    "apply_fan_avail_continuous",
    "apply_fan_avail_occupied_office",
    "apply_gl36_airside_proxy",
    "apply_chiller_lockout",
    "apply_high_performance_glazing",
    "apply_condensing_boiler_efficiency",
    "apply_high_efficiency_chiller",
    "apply_premium_fan_vfd",
    "apply_air_to_water_heat_pump_surrogate",
    "apply_sat_reset",
    "apply_run_period",
    "apply_hourly_outputs",
    "apply_monthly_energy_tables",
    "apply_capacity_factors",
    "apply_outdoor_air_fraction",
    "apply_patch",
    "known_patch_names",
]
