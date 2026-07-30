"""Central name -> IDF patch dispatch (extracted from easy_button._apply_patch).

Every patch callable takes (src, dest, params) where params is the (possibly
empty) ``idf_patch.params`` mapping from a measure, and returns the patch
metadata dict the underlying apply_* function produces. All patch names and
aliases previously hard-coded in ``wattlab.easy_button._apply_patch`` are
preserved here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from wattlab.energyplus.patches.capacity import apply_capacity_factors
from wattlab.energyplus.patches.chiller_lockout import apply_chiller_lockout
from wattlab.energyplus.patches.deep_retrofit import (
    apply_air_to_water_heat_pump_surrogate,
    apply_condensing_boiler_efficiency,
    apply_high_efficiency_chiller,
    apply_high_performance_glazing,
    apply_premium_fan_vfd,
)
from wattlab.energyplus.patches.dsp_reset import apply_dsp_reset
from wattlab.energyplus.patches.gl36_proxy import apply_gl36_airside_proxy
from wattlab.energyplus.patches.hourly_outputs import (
    apply_hourly_outputs,
    apply_monthly_energy_tables,
)
from wattlab.energyplus.patches.sat_reset import apply_sat_reset
from wattlab.energyplus.patches.schedules import (
    apply_fan_avail_continuous,
    apply_fan_avail_occupied_office,
)
from wattlab.energyplus.patches.ventilation import apply_outdoor_air_fraction

Params = Mapping[str, Any]
PatchFn = Callable[[Path, Path, Params], dict]


def _float_param(params: Params, name: str, default: float) -> float:
    value = params.get(name)
    return float(default if value is None else value)


def _bool_param(params: Params, name: str, default: bool = False) -> bool:
    value = params.get(name)
    return bool(default if value is None else value)


def _fan_avail_continuous(src: Path, dest: Path, params: Params) -> dict:
    return apply_fan_avail_continuous(src, dest)


def _fan_avail_occupied_office(src: Path, dest: Path, params: Params) -> dict:
    return apply_fan_avail_occupied_office(src, dest)


def _gl36_airside_proxy(src: Path, dest: Path, params: Params) -> dict:
    return apply_gl36_airside_proxy(
        src,
        dest,
        vav_min_fraction=_float_param(params, "vav_min_fraction", 0.15),
        fan_pressure_pa=_float_param(params, "fan_pressure_pa", 400.0),
        fan_power_min_fraction=_float_param(params, "fan_power_min_fraction", 0.15),
    )


def _chiller_lockout(src: Path, dest: Path, params: Params) -> dict:
    return apply_chiller_lockout(
        src, dest, oat_lockout_f=_float_param(params, "oat_lockout_f", 60.0)
    )


def _sat_reset(src: Path, dest: Path, params: Params) -> dict:
    return apply_sat_reset(src, dest)


def _dsp_reset(src: Path, dest: Path, params: Params) -> dict:
    return apply_dsp_reset(
        src, dest, fan_pressure_pa=_float_param(params, "fan_pressure_pa", 450.0)
    )


def _high_performance_glazing(src: Path, dest: Path, params: Params) -> dict:
    return apply_high_performance_glazing(
        src,
        dest,
        u_factor=_float_param(params, "u_factor", 1.4),
        shgc=_float_param(params, "shgc", 0.30),
        visible_transmittance=_float_param(params, "visible_transmittance", 0.50),
    )


def _condensing_boiler(src: Path, dest: Path, params: Params) -> dict:
    return apply_condensing_boiler_efficiency(
        src, dest, efficiency=_float_param(params, "efficiency", 0.95)
    )


def _high_efficiency_chiller(src: Path, dest: Path, params: Params) -> dict:
    return apply_high_efficiency_chiller(
        src, dest, cop=_float_param(params, "cop", 6.1)
    )


def _premium_fan_vfd(src: Path, dest: Path, params: Params) -> dict:
    return apply_premium_fan_vfd(
        src,
        dest,
        total_efficiency=_float_param(params, "total_efficiency", 0.75),
        motor_efficiency=_float_param(params, "motor_efficiency", 0.95),
        pressure_pa=_float_param(params, "pressure_pa", 400.0),
        min_flow_fraction=_float_param(params, "min_flow_fraction", 0.10),
    )


def _awhp_surrogate(src: Path, dest: Path, params: Params) -> dict:
    return apply_air_to_water_heat_pump_surrogate(
        src, dest, cop=_float_param(params, "cop", 2.8)
    )


def _hourly_outputs(src: Path, dest: Path, params: Params) -> dict:
    return apply_hourly_outputs(src, dest)


def _monthly_energy_tables(src: Path, dest: Path, params: Params) -> dict:
    return apply_monthly_energy_tables(src, dest)


def _capacity_factors(src: Path, dest: Path, params: Params) -> dict:
    factors = params.get("factors") or {
        k: v for k, v in params.items() if isinstance(v, (int, float))
    }
    return apply_capacity_factors(src, dest, factors)


def _outdoor_air_fraction(src: Path, dest: Path, params: Params) -> dict:
    return apply_outdoor_air_fraction(
        src,
        dest,
        min_oa_fraction=_float_param(params, "min_oa_fraction", 1.0),
        stuck_closed=_bool_param(params, "stuck_closed"),
        economizer_disabled=_bool_param(params, "economizer_disabled"),
    )


# Canonical name -> handler; aliases map onto the same handler so every
# spelling previously accepted by easy_button keeps working.
_REGISTRY: dict[str, PatchFn] = {
    "fan_avail_continuous": _fan_avail_continuous,
    "baseline_continuous": _fan_avail_continuous,
    "fan_avail_occupied_office": _fan_avail_occupied_office,
    "schedule_occupied": _fan_avail_occupied_office,
    "gl36_airside_proxy": _gl36_airside_proxy,
    "gl36_proxy": _gl36_airside_proxy,
    "chiller_lockout": _chiller_lockout,
    "mech_oat_lockout": _chiller_lockout,
    "sat_reset": _sat_reset,
    "sat_reset_proxy": _sat_reset,
    "dsp_reset": _dsp_reset,
    "duct_static_reset": _dsp_reset,
    "high_performance_glazing": _high_performance_glazing,
    "condensing_boiler": _condensing_boiler,
    "high_efficiency_chiller": _high_efficiency_chiller,
    "premium_fan_vfd": _premium_fan_vfd,
    "awhp_surrogate": _awhp_surrogate,
    "hourly_outputs": _hourly_outputs,
    "monthly_energy_tables": _monthly_energy_tables,
    "capacity_factors": _capacity_factors,
    "outdoor_air_fraction": _outdoor_air_fraction,
}


def known_patch_names() -> list[str]:
    """All accepted patch names (canonical + aliases), sorted."""
    return sorted(_REGISTRY)


def apply_patch(
    name: str,
    src: Path,
    dest: Path,
    params: Params | None = None,
) -> dict:
    """Dispatch a named IDF patch; raises ValueError for unknown names."""
    from wattlab.energyplus.patches.prototype_residuals import PROTOTYPE_RESIDUALS

    stub = PROTOTYPE_RESIDUALS.get(name)
    if stub is not None:
        # ECM-ERV-001: discoverable stub only — refuse silent / fake cascade.
        raise ValueError(
            f"idf_patch {name!r} is HAS_EP_PROTOTYPE only "
            f"({stub.get('ticket')}: Twin ERV topology not productized). "
            "Cascade must stay NO_EP; use full-parity spreadsheet ss_* for screening."
        )
    handler = _REGISTRY.get(name)
    if handler is None:
        raise ValueError(f"Unknown idf_patch name: {name}")
    return handler(Path(src), Path(dest), params or {})
