from __future__ import annotations
from math import isfinite
from typing import Any

from wattlab.engineering import openfdd_ecm as _ofdd

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
    """Delegate to Open-FDD; preserve WattLab savings_fraction key."""
    out = dict(_ofdd.calculate("fan_affinity", dict(i)))
    baseline = float(out.get("baseline_kwh") or 0.0)
    savings = float(out.get("savings_kwh") or 0.0)
    out.setdefault("savings_fraction", (savings / baseline) if baseline else 0.0)
    out.setdefault("assumptions", {"power_exponent": float(i.get("power_exponent", 3.0))})
    return out

@register("schedule_reduction")
def schedule_reduction(i: dict[str, Any]) -> dict[str, Any]:
    return dict(_ofdd.calculate("schedule_reduction", dict(i)))

@register("outside_air_sensible")
def outside_air_sensible(i: dict[str, Any]) -> dict[str, Any]:
    # WattLab default fuel is electric; Open-FDD defaults to natural_gas.
    payload = dict(i)
    payload.setdefault("fuel", "electric")
    return dict(_ofdd.calculate("outside_air_sensible", payload))

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
    return dict(_ofdd.calculate("kw_per_ton_improvement", dict(i)))

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
    """Screening gas savings from raising boiler thermal efficiency (Open-FDD)."""
    baseline = _req(i, "baseline_efficiency")
    proposed = _req(i, "proposed_efficiency")
    if baseline <= 0 or proposed <= 0:
        raise ValueError("efficiencies must be > 0")
    if proposed < baseline:
        raise ValueError("proposed_efficiency must be >= baseline_efficiency")
    out = dict(_ofdd.calculate("boiler_efficiency_improvement", dict(i)))
    bt = float(out.get("baseline_therms") or 0.0)
    st = float(out.get("savings_therms") or 0.0)
    out.setdefault("savings_fraction", (st / bt) if bt else 0.0)
    out.setdefault("assumptions", {"load_is_delivered_mmbtu": True})
    return out


@register("heat_pump_electrification")
def heat_pump_electrification(i: dict[str, Any]) -> dict[str, Any]:
    """Screen gas→heat-pump fuel switch (screening-grade, not a real HP curve).

    Delivered heating load MMBtu is currently served by a combustion plant at
    ``baseline_efficiency``. Proposed plant uses electricity at ``proposed_cop``
    (W_thermal/W_electric). Returns positive ``savings_therms`` (gas avoided)
    and typically **negative** ``savings_kwh`` (electric load added) so net
    dollar savings = therms×gas_rate + kwh×elec_rate still works.
    """
    load_mmbtu = _req(i, "annual_heating_mmbtu")
    baseline = float(i.get("baseline_efficiency", 0.80))
    cop = _req(i, "proposed_cop")
    if baseline <= 0 or cop <= 0:
        raise ValueError("baseline_efficiency and proposed_cop must be > 0")
    # 1 MMBtu = 10 therms input at η=1; 1 MMBtu ≈ 293.071 kWh thermal
    baseline_therms = load_mmbtu * 10.0 / baseline
    thermal_kwh = load_mmbtu * 293.07107
    proposed_kwh = thermal_kwh / cop
    return _result(
        baseline_therms=baseline_therms,
        proposed_kwh=proposed_kwh,
        savings_therms=baseline_therms,
        savings_kwh=-proposed_kwh,
        assumptions={
            "load_is_delivered_mmbtu": True,
            "heat_pump_curves": False,
            "defrost_not_modeled": True,
        },
    )
