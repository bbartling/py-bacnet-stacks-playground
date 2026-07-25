from __future__ import annotations
from math import isfinite
from typing import Any
from .registry import register

def _req(d: dict[str, Any], key: str) -> float:
    if key not in d:
        raise ValueError(f"Missing required input: {key}")
    value = float(d[key])
    if not isfinite(value):
        raise ValueError(f"Input must be finite: {key}")
    return value

def _result(**kwargs: Any) -> dict[str, Any]:
    return kwargs

@register("fan_affinity")
def fan_affinity(i: dict[str, Any]) -> dict[str, Any]:
    design_kw = _req(i, "design_kw")
    baseline_speed = _req(i, "baseline_speed_fraction")
    proposed_speed = _req(i, "proposed_speed_fraction")
    hours = _req(i, "hours")
    exponent = float(i.get("power_exponent", 3.0))
    baseline_kwh = design_kw * baseline_speed**exponent * hours
    proposed_kwh = design_kw * proposed_speed**exponent * hours
    return _result(
        baseline_kwh=baseline_kwh,
        proposed_kwh=proposed_kwh,
        savings_kwh=baseline_kwh-proposed_kwh,
        savings_fraction=(baseline_kwh-proposed_kwh)/baseline_kwh if baseline_kwh else 0.0,
        assumptions={"power_exponent": exponent},
    )

@register("schedule_reduction")
def schedule_reduction(i: dict[str, Any]) -> dict[str, Any]:
    kw = _req(i, "equipment_kw")
    baseline_hours = _req(i, "baseline_annual_hours")
    proposed_hours = _req(i, "proposed_annual_hours")
    load_fraction = float(i.get("average_load_fraction", 1.0))
    baseline_kwh = kw * baseline_hours * load_fraction
    proposed_kwh = kw * proposed_hours * load_fraction
    return _result(
        baseline_kwh=baseline_kwh,
        proposed_kwh=proposed_kwh,
        savings_kwh=baseline_kwh-proposed_kwh,
        reduced_hours=baseline_hours-proposed_hours,
    )

@register("outside_air_sensible")
def outside_air_sensible(i: dict[str, Any]) -> dict[str, Any]:
    cfm = _req(i, "outside_air_cfm")
    delta_t_f = _req(i, "average_delta_t_f")
    hours = _req(i, "hours")
    efficiency = float(i.get("system_efficiency", 1.0))
    fuel = str(i.get("fuel", "electric")).lower()
    load_btu = 1.08 * cfm * delta_t_f * hours
    if efficiency <= 0:
        raise ValueError("system_efficiency must be > 0")
    input_btu = load_btu / efficiency
    out = {"load_btu": load_btu, "input_btu": input_btu}
    if fuel == "electric":
        out["savings_kwh"] = input_btu / 3412.142
    elif fuel == "natural_gas":
        out["savings_therms"] = input_btu / 100000.0
    else:
        raise ValueError("fuel must be electric or natural_gas")
    return out

@register("demand_control_ventilation")
def demand_control_ventilation(i: dict[str, Any]) -> dict[str, Any]:
    baseline_oa_cfm = _req(i, "baseline_oa_cfm")
    proposed_oa_cfm = _req(i, "proposed_oa_cfm")
    delta_t_f = _req(i, "average_delta_t_f")
    hours = _req(i, "hours")
    efficiency = float(i.get("system_efficiency", 1.0))
    fuel = str(i.get("fuel", "electric")).lower()
    avoided_cfm = max(0.0, baseline_oa_cfm - proposed_oa_cfm)
    return outside_air_sensible({
        "outside_air_cfm": avoided_cfm,
        "average_delta_t_f": delta_t_f,
        "hours": hours,
        "system_efficiency": efficiency,
        "fuel": fuel,
    }) | {"avoided_oa_cfm": avoided_cfm}

@register("economizer_proxy")
def economizer_proxy(i: dict[str, Any]) -> dict[str, Any]:
    cooling_load_tons = _req(i, "average_cooling_load_tons")
    eligible_hours = _req(i, "eligible_hours")
    mechanical_fraction_avoided = _req(i, "mechanical_fraction_avoided")
    kw_per_ton = _req(i, "baseline_kw_per_ton")
    savings = cooling_load_tons * eligible_hours * mechanical_fraction_avoided * kw_per_ton
    return _result(savings_kwh=savings, eligible_hours=eligible_hours)

@register("kw_per_ton_improvement")
def kw_per_ton_improvement(i: dict[str, Any]) -> dict[str, Any]:
    ton_hours = _req(i, "annual_ton_hours")
    baseline = _req(i, "baseline_kw_per_ton")
    proposed = _req(i, "proposed_kw_per_ton")
    return _result(
        baseline_kwh=ton_hours*baseline,
        proposed_kwh=ton_hours*proposed,
        savings_kwh=ton_hours*(baseline-proposed),
    )

@register("pump_vfd")
def pump_vfd(i: dict[str, Any]) -> dict[str, Any]:
    return fan_affinity({
        "design_kw": _req(i, "design_kw"),
        "baseline_speed_fraction": _req(i, "baseline_speed_fraction"),
        "proposed_speed_fraction": _req(i, "proposed_speed_fraction"),
        "hours": _req(i, "hours"),
        "power_exponent": float(i.get("power_exponent", 3.0)),
    })

@register("temperature_reset_bins")
def temperature_reset_bins(i: dict[str, Any]) -> dict[str, Any]:
    design_kw = _req(i, "design_kw")
    bins = i.get("bins")
    if not isinstance(bins, list) or not bins:
        raise ValueError("bins must be a non-empty list")
    exponent = float(i.get("power_exponent", 3.0))
    baseline_kwh = 0.0
    proposed_kwh = 0.0
    details = []
    for row in bins:
        hours = float(row["hours"])
        b = float(row["baseline_speed_fraction"])
        p = float(row["proposed_speed_fraction"])
        bk = design_kw * b**exponent * hours
        pk = design_kw * p**exponent * hours
        baseline_kwh += bk
        proposed_kwh += pk
        details.append({"label": row.get("label"), "baseline_kwh": bk, "proposed_kwh": pk})
    return _result(
        baseline_kwh=baseline_kwh,
        proposed_kwh=proposed_kwh,
        savings_kwh=baseline_kwh-proposed_kwh,
        bins=details,
    )

@register("eui")
def eui(i: dict[str, Any]) -> dict[str, Any]:
    annual_energy_kbtu = _req(i, "annual_energy_kbtu")
    floor_area_ft2 = _req(i, "floor_area_ft2")
    if floor_area_ft2 <= 0:
        raise ValueError("floor_area_ft2 must be > 0")
    return _result(eui_kbtu_ft2=annual_energy_kbtu/floor_area_ft2)

@register("simple_payback")
def simple_payback(i: dict[str, Any]) -> dict[str, Any]:
    implementation_cost = _req(i, "implementation_cost")
    annual_cost_savings = _req(i, "annual_cost_savings")
    return _result(
        simple_payback_years=implementation_cost/annual_cost_savings if annual_cost_savings > 0 else None
    )

@register("boiler_efficiency_improvement")
def boiler_efficiency_improvement(i: dict[str, Any]) -> dict[str, Any]:
    """Screening gas savings from raising boiler thermal efficiency.

    ``annual_heating_mmbtu`` is delivered (output) load. Input fuel falls as
    efficiency rises: therms = MMBtu × 10 / η.
    """
    load_mmbtu = _req(i, "annual_heating_mmbtu")
    baseline = _req(i, "baseline_efficiency")
    proposed = _req(i, "proposed_efficiency")
    if baseline <= 0 or proposed <= 0:
        raise ValueError("efficiencies must be > 0")
    if proposed < baseline:
        raise ValueError("proposed_efficiency must be >= baseline_efficiency")
    baseline_therms = load_mmbtu * 10.0 / baseline
    proposed_therms = load_mmbtu * 10.0 / proposed
    return _result(
        baseline_therms=baseline_therms,
        proposed_therms=proposed_therms,
        savings_therms=baseline_therms - proposed_therms,
        savings_fraction=(baseline_therms - proposed_therms) / baseline_therms if baseline_therms else 0.0,
        assumptions={"load_is_delivered_mmbtu": True},
    )
