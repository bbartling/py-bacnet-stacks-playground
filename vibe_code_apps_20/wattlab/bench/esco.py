"""Open, independently implemented HVAC bin-method screening calculators.

Each calculator applies standard HVAC engineering relationships and is
validated with synthetic golden tests. Calculations are driven by an OAT bin table
(:mod:`wattlab.weather.bins`) plus an equipment inventory and daily-shift
operating schedules:

- ``scheduling_fan_bins``       — "CV/VV Scheduling_Fan" (start/stop optimization)
- ``scheduling_cooling_bins``   — "CV/VV Scheduling_Cooling" (vent cooling via MCWB enthalpy)
- ``scheduling_heating_bins``   — "CV/VV Scheduling_Heating" (vent heating below balance point)
- ``oad_unoccupied_closed``     — "OAD 0% Unocc" heating/cooling (damper closed hours)
- ``dcv_bins``                  — demand-control ventilation on avoided OA CFM
- ``static_pressure_reset``     — "VV Static Pressure Reset" (fan laws, sqrt-pressure speed)
- ``dat_reset_bins``            — "VV DAT Reset_Cooling" (supply enthalpy reset per bin)
- ``hydronic_reset_bins``       — "Hot Water Reset" (HW/CHW/CDW reset savings ladder)
- ``chw_reset``                 — chilled-water reset (thin ``chilled_water`` wrapper)
- ``condenser_water_reset``     — CW reset screening proxy (gentler ladder, no tower fan penalty)
- ``pneumatic_compressor``      — control-air compressor kWh from avoided run hours
- ``dewpoint_economizer``       — "Enthalpy Econ" (economizer-eligible bins)
- ``erv_bins``                  — air-side energy recovery (AHU OA / toilet exhaust)

Savings conventions use 4.5 * CFM * dH Btu/h for total-enthalpy
ventilation loads, 1.08 * CFM * dT Btu/h for sensible, 12,000 Btu/ton-h and
kW/ton for cooling electricity, boiler efficiency for heating fuel.
"""

from __future__ import annotations

from math import sqrt
from typing import Any

from wattlab.weather.bins import (
    OperatingSchedule,
    WeatherBins,
    hours_reduction_fraction,
    parse_bins_input,
)

from wattlab.engineering import openfdd_ecm as _ofdd

from .registry import register

MMBTU_PER_THERM = 0.1


def _schedule(i: dict[str, Any], key: str) -> OperatingSchedule:
    if key not in i:
        raise ValueError(f"Missing required input: {key}")
    return OperatingSchedule.from_dict(i[key])


def _bins(i: dict[str, Any]) -> WeatherBins:
    if "bins" not in i:
        raise ValueError("Missing required input: bins")
    return parse_bins_input(i["bins"])


def _vent_cooling_ton_per_hr(oa_cfm: float, oa_enthalpy: float | None, supply_enthalpy: float) -> float:
    """Sheet column "Vent Cooling Ton/Hr": ``CFM * (h_oa - h_sup) * 4.5 / 12000``, floored at 0."""
    if oa_enthalpy is None or oa_enthalpy < supply_enthalpy:
        return 0.0
    return oa_cfm * (oa_enthalpy - supply_enthalpy) * 4.5 / 12000.0


def _vent_heating_kbtu_per_hr(oa_cfm: float, bin_temp: float, balance_point: float) -> float:
    """Sheet column "Vent Heat MBtu/h": ``1.08 * CFM * (bp - T) / 1000``, floored at 0."""
    if balance_point < bin_temp:
        return 0.0
    return (balance_point - bin_temp) * oa_cfm * 1.08 / 1000.0


# ---------------------------------------------------------------------------
# Scheduling (start/stop optimization)
# ---------------------------------------------------------------------------

@register("scheduling_fan_bins")
def scheduling_fan_bins(i: dict[str, Any]) -> dict[str, Any]:
    """CV/VV Scheduling — fan power (Open-FDD bin method)."""
    return dict(_ofdd.scheduling_fan_bins(i))


@register("scheduling_cooling_bins")
def scheduling_cooling_bins(i: dict[str, Any]) -> dict[str, Any]:
    """CV/VV Scheduling — ventilation cooling (Open-FDD bin method)."""
    return dict(_ofdd.scheduling_cooling_bins(i))


@register("scheduling_heating_bins")
def scheduling_heating_bins(i: dict[str, Any]) -> dict[str, Any]:
    """CV/VV Scheduling — ventilation heating (Open-FDD bin method)."""
    return dict(_ofdd.scheduling_heating_bins(i))


# ---------------------------------------------------------------------------
# OAD 0% unoccupied and DCV
# ---------------------------------------------------------------------------

@register("oad_unoccupied_closed")
def oad_unoccupied_closed(i: dict[str, Any]) -> dict[str, Any]:
    """"OAD 0% Unocc" — close outside-air dampers during unoccupied/warmup hours.

    ``vent_hours_schedule`` describes the *reduction in ventilating hours*
    (shift hours where the damper closes); the entire ventilation load in
    those hours is saved. ``mode`` is ``"cooling"`` (kWh via ``kw_per_ton``)
    or ``"heating"`` (MMBtu via ``boiler_efficiency`` and ``balance_point_f``).
    """
    mode = str(i.get("mode", "cooling")).lower()
    oa_cfm = float(i["oa_cfm_total"])
    schedule = _schedule(i, "vent_hours_schedule")
    bins = _bins(i)

    details = []
    if mode == "cooling":
        kw_per_ton = float(i["kw_per_ton"])
        supply_h = float(i.get("supply_enthalpy", 23.2))
        total = 0.0
        for row in bins.rows:
            vent_hours = schedule.total_operating_hours(row.shift_hours)
            ton_hr = _vent_cooling_ton_per_hr(oa_cfm, row.oa_enthalpy, supply_h)
            saved = ton_hr * vent_hours * kw_per_ton
            total += saved
            details.append({
                "temp": row.temp,
                "vent_hours": vent_hours,
                "vent_cooling_ton_hr": ton_hr,
                "saved_kwh": saved,
            })
        return {"savings_kwh": total, "mode": mode, "bins": details}

    if mode == "heating":
        balance_point = float(i.get("balance_point_f", 55.0))
        efficiency = float(i.get("boiler_efficiency", 0.8))
        if efficiency <= 0:
            raise ValueError("boiler_efficiency must be > 0")
        total = 0.0
        for row in bins.rows:
            vent_hours = schedule.total_operating_hours(row.shift_hours)
            load_kbtu_h = _vent_heating_kbtu_per_hr(oa_cfm, row.temp, balance_point)
            saved = load_kbtu_h * vent_hours / efficiency / 1000.0
            total += saved
            details.append({
                "temp": row.temp,
                "vent_hours": vent_hours,
                "vent_heat_kbtu_hr": load_kbtu_h,
                "saved_mmbtu": saved,
            })
        return {
            "savings_mmbtu": total,
            "savings_therms": total / MMBTU_PER_THERM,
            "mode": mode,
            "bins": details,
        }

    raise ValueError("mode must be 'cooling' or 'heating'")


@register("dcv_bins")
def dcv_bins(i: dict[str, Any]) -> dict[str, Any]:
    """Demand-control ventilation — bin-method savings on avoided OA CFM.

    Applies the scheduling-sheet ventilation load math to
    ``baseline_oa_cfm - proposed_oa_cfm`` during occupied hours: cooling kWh
    where OA enthalpy exceeds ``supply_enthalpy`` and heating MMBtu below
    ``balance_point_f``.
    """
    baseline_cfm = float(i["baseline_oa_cfm"])
    proposed_cfm = float(i["proposed_oa_cfm"])
    avoided_cfm = max(0.0, baseline_cfm - proposed_cfm)
    kw_per_ton = float(i["kw_per_ton"])
    supply_h = float(i.get("supply_enthalpy", 23.2))
    balance_point = float(i.get("balance_point_f", 55.0))
    efficiency = float(i.get("boiler_efficiency", 0.8))
    if efficiency <= 0:
        raise ValueError("boiler_efficiency must be > 0")
    schedule = _schedule(i, "schedule")
    bins = _bins(i)

    kwh = 0.0
    mmbtu = 0.0
    details = []
    for row in bins.rows:
        op_hours = schedule.total_operating_hours(row.shift_hours)
        ton_hr = _vent_cooling_ton_per_hr(avoided_cfm, row.oa_enthalpy, supply_h)
        saved_kwh = ton_hr * op_hours * kw_per_ton
        load_kbtu_h = _vent_heating_kbtu_per_hr(avoided_cfm, row.temp, balance_point)
        saved_mmbtu = load_kbtu_h * op_hours / efficiency / 1000.0
        kwh += saved_kwh
        mmbtu += saved_mmbtu
        details.append({
            "temp": row.temp,
            "operating_hours": op_hours,
            "saved_kwh": saved_kwh,
            "saved_mmbtu": saved_mmbtu,
        })
    return {
        "avoided_oa_cfm": avoided_cfm,
        "savings_kwh": kwh,
        "savings_mmbtu": mmbtu,
        "savings_therms": mmbtu / MMBTU_PER_THERM,
        "bins": details,
    }


# ---------------------------------------------------------------------------
# Static pressure reset (fan laws)
# ---------------------------------------------------------------------------

@register("static_pressure_reset")
def static_pressure_reset(i: dict[str, Any]) -> dict[str, Any]:
    """"VV Static Pressure Reset" — fan-law savings from reduced duct static.

    Per unit: existing kW = motor_kw * speed^3; the reduced speed follows the
    fan laws from the static pressure ratio, ``speed * sqrt(pressure_ratio)``
    (the sheet's ``F / SQRT(1 / 0.7)``). ``units`` is a list of
    ``{"tag", "motor_kw", "avg_speed_fraction", "annual_hours"}``;
    ``pressure_ratio`` defaults to 0.7 (proposed/existing static).
    """
    units = i.get("units")
    if not isinstance(units, list) or not units:
        raise ValueError("units must be a non-empty list")
    pressure_ratio = float(i.get("pressure_ratio", 0.7))
    if not 0.0 < pressure_ratio <= 1.0:
        raise ValueError("pressure_ratio must be in (0, 1]")
    exponent = float(i.get("power_exponent", 3.0))

    total = 0.0
    details = []
    for u in units:
        kw = float(u["motor_kw"])
        speed = float(u["avg_speed_fraction"])
        hours = float(u["annual_hours"])
        reduced_speed = speed * sqrt(pressure_ratio)
        existing_kw = kw * speed**exponent
        reduced_kw = kw * reduced_speed**exponent
        saved = (existing_kw - reduced_kw) * hours
        total += saved
        details.append({
            "tag": u.get("tag"),
            "avg_speed_fraction": speed,
            "reduced_speed_fraction": reduced_speed,
            "existing_kw": existing_kw,
            "reduced_kw": reduced_kw,
            "savings_kwh": saved,
        })
    return {
        "savings_kwh": total,
        "pressure_ratio": pressure_ratio,
        "units": details,
    }


# ---------------------------------------------------------------------------
# DAT reset
# ---------------------------------------------------------------------------

@register("dat_reset_bins")
def dat_reset_bins(i: dict[str, Any]) -> dict[str, Any]:
    """"VV DAT Reset_Cooling" — raise supply-air enthalpy setpoint in mild bins.

    Inputs: ``total_cfm``, ``oa_cfm``, ``return_enthalpy``,
    ``supply_enthalpy`` (existing), ``kw_per_ton``, ``schedule``, ``bins``,
    and ``reset`` — a list of ``{"temp", "proposed_supply_enthalpy",
    "vav_fraction"?}`` per-bin overrides (bins without an entry keep the
    existing setpoint and 100% airflow).
    """
    total_cfm = float(i["total_cfm"])
    oa_cfm = float(i.get("oa_cfm", total_cfm))
    return_h = float(i["return_enthalpy"])
    supply_h = float(i.get("supply_enthalpy", 23.2))
    kw_per_ton = float(i["kw_per_ton"])
    schedule = _schedule(i, "schedule")
    bins = _bins(i)
    reset_by_temp = {
        float(r["temp"]): r for r in i.get("reset", [])
    }
    if total_cfm <= 0:
        raise ValueError("total_cfm must be > 0")

    total = 0.0
    details = []
    for row in bins.rows:
        h_oa = row.oa_enthalpy
        op_hours = schedule.total_operating_hours(row.shift_hours)
        override = reset_by_temp.get(row.temp, {})
        vav = float(override.get("vav_fraction", 1.0))
        proposed_h = float(override.get("proposed_supply_enthalpy", supply_h))
        if h_oa is None:
            h_mix = None
            existing_ton_hr = proposed_ton_hr = 0.0
        else:
            h_mix = h_oa * oa_cfm / total_cfm + return_h * (total_cfm - oa_cfm) / total_cfm
            existing_ton_hr = (
                0.0 if h_oa < supply_h else total_cfm * (h_mix - supply_h) * 4.5 / 12000.0
            ) * vav
            proposed_ton_hr = (
                0.0 if h_oa < proposed_h else total_cfm * (h_mix - proposed_h) * 4.5 / 12000.0
            ) * vav
        saved = (existing_ton_hr - proposed_ton_hr) * op_hours * kw_per_ton
        total += saved
        details.append({
            "temp": row.temp,
            "operating_hours": op_hours,
            "mixed_enthalpy": h_mix,
            "proposed_supply_enthalpy": proposed_h,
            "vav_fraction": vav,
            "saved_kwh": saved,
        })
    return {"savings_kwh": total, "bins": details}


# ---------------------------------------------------------------------------
# Hydronic (HW/CHW/CDW) reset
# ---------------------------------------------------------------------------

@register("hydronic_reset_bins")
def hydronic_reset_bins(i: dict[str, Any]) -> dict[str, Any]:
    """"Hot Water Reset" — supply-water temperature reset savings ladder.

    Load fraction ramps linearly from 0 at ``on_point_f`` to 1 at
    ``design_temp_f``; existing consumption per bin is
    ``capacity_mbh * load * operating_hours / 1000`` MMBtu. Savings percent
    starts at ``max_savings_fraction`` in the first (mildest) bin at/below the
    on-point and steps down by ``max_savings_fraction / n_reset_bins`` per
    colder bin (the sheet's diminishing-reset ladder). ``mode`` is
    ``"hot_water"`` (MMBtu / boiler_efficiency) or ``"chilled_water"``
    (ton-h * kw_per_ton, load ramps up with *rising* temperature).
    """
    mode = str(i.get("mode", "hot_water")).lower()
    capacity_mbh = float(i["capacity_mbh"])
    on_point = float(i.get("on_point_f", 55.0))
    design_temp = float(i.get("design_temp_f", 0.0 if mode == "hot_water" else 95.0))
    max_savings = float(i.get("max_savings_fraction", 0.05))
    schedule = _schedule(i, "schedule")
    bins = _bins(i)
    if design_temp == on_point:
        raise ValueError("design_temp_f must differ from on_point_f")

    n_reset_bins = i.get("n_reset_bins")
    if n_reset_bins is not None:
        step = max_savings / float(n_reset_bins)
    else:
        step = float(i.get("savings_step_fraction", 0.0))

    def load_fraction(temp: float) -> float:
        if mode == "hot_water":
            if temp >= on_point:
                return 0.0
        else:
            if temp <= on_point:
                return 0.0
        return (temp - on_point) / (design_temp - on_point)

    rows = sorted(bins.rows, key=lambda r: r.temp, reverse=(mode == "hot_water"))
    # Ladder anchor: the mildest bin whose 5 F range reaches the on-point.
    bin_half_width = 2.5
    ladder_started = False
    savings_pct = max_savings

    details = []
    total_mmbtu = 0.0
    total_kwh = 0.0
    for row in rows:
        near_on_point = (
            row.temp - bin_half_width <= on_point
            if mode == "hot_water"
            else row.temp + bin_half_width >= on_point
        )
        if not ladder_started and near_on_point:
            ladder_started = True
        elif ladder_started and step > 0:
            savings_pct = max(savings_pct - step, 0.0)

        pct = savings_pct if ladder_started else 0.0
        load = load_fraction(row.temp)
        op_hours = schedule.total_operating_hours(row.shift_hours)
        if mode == "hot_water":
            efficiency = float(i.get("boiler_efficiency", 0.8))
            existing_mmbtu = capacity_mbh * load * op_hours / 1000.0
            saved = existing_mmbtu * pct / efficiency
            total_mmbtu += saved
            details.append({
                "temp": row.temp,
                "load_fraction": load,
                "operating_hours": op_hours,
                "savings_pct": pct,
                "existing_mmbtu": existing_mmbtu,
                "saved_mmbtu": saved,
            })
        else:
            kw_per_ton = float(i["kw_per_ton"])
            existing_ton_hr = capacity_mbh * load * op_hours / 12.0  # MBH -> tons
            saved = existing_ton_hr * pct * kw_per_ton
            total_kwh += saved
            details.append({
                "temp": row.temp,
                "load_fraction": load,
                "operating_hours": op_hours,
                "savings_pct": pct,
                "existing_ton_hr": existing_ton_hr,
                "saved_kwh": saved,
            })

    out: dict[str, Any] = {"mode": mode, "bins": details}
    if mode == "hot_water":
        out["savings_mmbtu"] = total_mmbtu
        out["savings_therms"] = total_mmbtu / MMBTU_PER_THERM
    else:
        out["savings_kwh"] = total_kwh
    return out


@register("chw_reset")
def chw_reset(i: dict[str, Any]) -> dict[str, Any]:
    """Chilled-water supply temperature reset — thin wrapper over
    :func:`hydronic_reset_bins` in ``chilled_water`` mode (load ramps up with
    rising OAT from ``on_point_f`` to ``design_temp_f``; savings ladder starts
    at ``max_savings_fraction`` in the mildest cooling bin).

    Required inputs: ``capacity_mbh``, ``kw_per_ton``, ``schedule``, ``bins``.
    """
    return hydronic_reset_bins({**i, "mode": "chilled_water"})


@register("condenser_water_reset")
def condenser_water_reset(i: dict[str, Any]) -> dict[str, Any]:
    """Condenser-water temperature reset — screening proxy reusing the
    ``chilled_water`` reset ladder (chiller kW relief in mild bins where tower
    approach allows a lower CW setpoint). Added tower fan energy is NOT
    modeled; treat results as an upper bound. Defaults to a gentler ladder
    (``max_savings_fraction`` 0.03) than CHW reset.

    Required inputs: ``capacity_mbh``, ``kw_per_ton``, ``schedule``, ``bins``.
    """
    inputs = {"max_savings_fraction": 0.03, **i, "mode": "chilled_water"}
    out = hydronic_reset_bins(inputs)
    out["mode"] = "condenser_water"
    out["note"] = "Screening proxy via chilled_water reset ladder; tower fan penalty not modeled."
    return out


@register("pneumatic_compressor")
def pneumatic_compressor(i: dict[str, Any]) -> dict[str, Any]:
    """Control-air compressor savings from pneumatic-to-DDC conversion (or
    leak repair): ``compressor_kw * load_factor`` over avoided run hours.

    Inputs: ``compressor_kw``, ``baseline_annual_hours``,
    ``proposed_annual_hours`` (default 0 — full conversion removes the
    compressor), ``load_factor`` (default 0.5 average loaded fraction).
    """
    kw = float(i["compressor_kw"])
    baseline_hours = float(i["baseline_annual_hours"])
    proposed_hours = float(i.get("proposed_annual_hours", 0.0))
    load_factor = float(i.get("load_factor", 0.5))
    if kw <= 0 or baseline_hours < 0 or proposed_hours < 0:
        raise ValueError("compressor_kw must be > 0 and hours must be >= 0")
    if not 0.0 < load_factor <= 1.0:
        raise ValueError("load_factor must be in (0, 1]")
    avoided_hours = max(baseline_hours - proposed_hours, 0.0)
    baseline_kwh = kw * load_factor * baseline_hours
    savings = kw * load_factor * avoided_hours
    return {
        "baseline_kwh": baseline_kwh,
        "proposed_kwh": baseline_kwh - savings,
        "savings_kwh": savings,
        "avoided_hours": avoided_hours,
        "load_factor": load_factor,
    }


# ---------------------------------------------------------------------------
# Enthalpy economizer
# ---------------------------------------------------------------------------

@register("dewpoint_economizer")
def dewpoint_economizer(i: dict[str, Any]) -> dict[str, Any]:
    """"Enthalpy Econ" — free cooling when OA enthalpy is below return enthalpy.

    Per bin, mechanical cooling on the supply airstream
    (``vav_fraction * unit_cfm * 4.5 * (return_h - discharge_h) / 12000`` tons)
    is avoided entirely whenever OA enthalpy < ``return_enthalpy`` and the bin
    is warm enough for cooling (``temp > discharge_temp_f``). VAV airflow
    ramps from ``min_vav_fraction`` up to 1 between ``chiller_on_point_f`` and
    ``cooling_design_temp_f``; CV airflow stays at 1.
    """
    unit_cfm = float(i["unit_cfm_total"])
    oa_cfm = float(i.get("oa_cfm_total", 0.0))
    recirc_cfm = max(unit_cfm - oa_cfm, 0.0)
    return_h = float(i["return_enthalpy"])
    discharge_h = float(i["discharge_enthalpy"])
    discharge_temp = float(i.get("discharge_temp_f", 57.0))
    kw_per_ton = float(i["kw_per_ton"])
    unit_type = str(i.get("unit_type", "cv")).lower()
    min_vav = float(i.get("min_vav_fraction", 0.7))
    on_point = float(i.get("chiller_on_point_f", 55.0))
    design_temp = float(i.get("cooling_design_temp_f", 95.0))
    schedule = _schedule(i, "schedule")
    bins = _bins(i)
    if design_temp == on_point:
        raise ValueError("cooling_design_temp_f must differ from chiller_on_point_f")

    total = 0.0
    details = []
    for row in bins.rows:
        op_hours = schedule.total_operating_hours(row.shift_hours)
        if unit_type == "vv":
            ramp = (row.temp - on_point) / (design_temp - on_point)
            vav = 1.0 if ramp > 1.0 else max(ramp, min_vav)
        else:
            vav = 1.0
        cooling_kwh = (
            vav * recirc_cfm * 4.5 * (return_h - discharge_h) * op_hours / 12000.0 * kw_per_ton
            if row.temp > discharge_temp
            else 0.0
        )
        h_oa = row.oa_enthalpy
        eligible = cooling_kwh > 0.0 and h_oa is not None and h_oa < return_h
        saved = cooling_kwh if eligible else 0.0
        total += saved
        details.append({
            "temp": row.temp,
            "operating_hours": op_hours,
            "vav_fraction": vav,
            "mechanical_cooling_kwh": cooling_kwh,
            "economizer_eligible": eligible,
            "saved_kwh": saved,
        })
    return {"savings_kwh": total, "bins": details}


@register("erv_bins")
def erv_bins(i: dict[str, Any]) -> dict[str, Any]:
    """Air-side energy recovery — AHU OA or toilet-exhaust makeup screening.

    Recovers a fraction of ventilation heating/cooling between outdoor air and
    an exhaust / return stream. Balanced AHU ERV: pass ``oa_cfm`` (exhaust
    defaults to OA). Toilet exhaust ER: pass ``exhaust_cfm`` (toilet) and
    ``oa_cfm`` (makeup) — recovered CFM is ``min(oa, exhaust)``.

    Inputs: ``oa_cfm``, optional ``exhaust_cfm``, ``sensible_effectiveness``
    (default 0.65), optional ``latent_effectiveness`` (default 0 — sensible
    screening), ``return_temp_f`` (75), ``return_enthalpy`` (28.3),
    ``kw_per_ton``, ``boiler_efficiency``, ``schedule``, ``bins``.
    """
    oa_cfm = float(i["oa_cfm"] if "oa_cfm" in i else i.get("oa_cfm_total", 0.0))
    exh_cfm = float(i["exhaust_cfm"]) if i.get("exhaust_cfm") is not None else oa_cfm
    recovered_cfm = min(max(0.0, oa_cfm), max(0.0, exh_cfm))
    if recovered_cfm <= 0:
        raise ValueError("oa_cfm / exhaust_cfm must yield recovered CFM > 0")
    sens_eff = float(i.get("sensible_effectiveness", 0.65))
    lat_eff = float(i.get("latent_effectiveness", 0.0))
    if not 0.0 <= sens_eff <= 1.0 or not 0.0 <= lat_eff <= 1.0:
        raise ValueError("effectiveness must be in [0, 1]")
    return_t = float(i.get("return_temp_f", 75.0))
    return_h = float(i.get("return_enthalpy", 28.3))
    kw_per_ton = float(i.get("kw_per_ton", 0.9))
    efficiency = float(i.get("boiler_efficiency", 0.8))
    if efficiency <= 0:
        raise ValueError("boiler_efficiency must be > 0")
    schedule = _schedule(i, "schedule")
    bins = _bins(i)

    kwh = 0.0
    mmbtu = 0.0
    details = []
    for row in bins.rows:
        op_hours = schedule.total_operating_hours(row.shift_hours)
        dT_heat = max(0.0, return_t - float(row.temp))
        heat_kbtu_h = 1.08 * recovered_cfm * sens_eff * dT_heat / 1000.0
        saved_mmbtu = heat_kbtu_h * op_hours / efficiency / 1000.0
        h_oa = row.oa_enthalpy
        cool_ton_h = 0.0
        if h_oa is not None and h_oa > return_h:
            # Sensible-only screening uses sensible ε on enthalpy delta; when
            # latent ε is set, blend toward total-enthalpy recovery without
            # overstating sensible-only cases via max(sens, lat).
            if lat_eff > 0:
                dH = (h_oa - return_h) * (0.7 * sens_eff + 0.3 * lat_eff)
            else:
                dH = (h_oa - return_h) * sens_eff
            cool_ton_h = recovered_cfm * dH * 4.5 / 12000.0
        saved_kwh = cool_ton_h * op_hours * kw_per_ton
        kwh += saved_kwh
        mmbtu += saved_mmbtu
        details.append(
            {
                "temp": row.temp,
                "operating_hours": op_hours,
                "saved_kwh": saved_kwh,
                "saved_mmbtu": saved_mmbtu,
            }
        )
    return {
        "recovered_cfm": recovered_cfm,
        "sensible_effectiveness": sens_eff,
        "latent_effectiveness": lat_eff,
        "savings_kwh": kwh,
        "savings_mmbtu": mmbtu,
        "savings_therms": mmbtu / MMBTU_PER_THERM,
        "bins": details,
    }


@register("toilet_exhaust_erv_bins")
def toilet_exhaust_erv_bins(i: dict[str, Any]) -> dict[str, Any]:
    """Toilet / restroom exhaust energy recovery (thin wrapper on ``erv_bins``).

    Requires ``exhaust_cfm`` (toilet exhaust) and ``oa_cfm`` (makeup OA).
    """
    payload = dict(i)
    if "exhaust_cfm" not in payload and "toilet_exhaust_cfm" in payload:
        payload["exhaust_cfm"] = payload["toilet_exhaust_cfm"]
    if "exhaust_cfm" not in payload:
        raise ValueError("toilet_exhaust_erv_bins requires exhaust_cfm (or toilet_exhaust_cfm)")
    return erv_bins(payload)
