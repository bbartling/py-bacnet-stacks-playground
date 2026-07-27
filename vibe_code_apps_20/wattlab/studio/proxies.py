"""ESCO screening proxy savings (shared by Studio ECM page)."""

from __future__ import annotations

from typing import Any

PROXY_ASSUMPTIONS = {
    "supply_cfm_per_ft2": 1.0,
    "oa_fraction": 0.20,
    "fan_w_per_cfm": 0.8,
    "kw_per_ton": 0.9,
    "boiler_efficiency": 0.80,
    "condensing_boiler_efficiency": 0.95,
    "boiler_tune_efficiency": 0.84,
    "heating_mmbtu_per_ft2_year": 0.035,  # screening delivered heating intensity
    "cooling_ton_hours_per_ft2_year": 1.2,
    "pump_kw_fraction_of_fan": 0.35,
    "existing_schedule": {"shifts": [8, 8, 8], "days_per_week": 7},
    "proposed_schedule": {"shifts": [1, 8, 3], "days_per_week": 5, "override_allowance": 0.10},
}

DEFAULT_MEASURE_COSTS = {
    "ECM-AHU-SCHED-ALIGN": 8000.0,
    "ECM-CHILLER-LOCKOUT": 6000.0,
    "ECM-SAT-RESET": 12000.0,
    "ECM-DSP-RESET": 8500.0,
    "ECM-GL36-AIRSIDE": 45000.0,
    "ECM-ERV": 85000.0,
    "ECM-TOILET-EXH-ERV": 35000.0,
    "ECM-PREMIUM-FAN-VFD": 90000.0,
    "ECM-PUMP-VFD": 45000.0,
    "ECM-CONDENSING-BOILER": 400000.0,
    "ECM-CHILLER-REPLACE-HIEFF": 600000.0,
    "ECM-ADVANCED-RTU": 25000.0,
    "ECM-BOILER-TUNE": 12000.0,
    "ECM-BOILER-RESET": 10000.0,
    "ECM-DCV-CO2": 18000.0,
    "ECM-OCC-STANDBY-DCV": 24000.0,
    "ECM-ECON-REPAIR": 15000.0,
    "ECM-VAV-MIN-RESET": 20000.0,
    "ECM-WINDOW-HP-GLAZING": 350000.0,
    "ECM-ENVELOPE-INSUL-CODE": 420000.0,
}


def _erv_proxy(get, *, oa_cfm: float, exhaust_cfm: float, kw_per_ton: float, bins, schedule) -> dict[str, float]:
    res = get("erv_bins")(
        {
            "oa_cfm": oa_cfm,
            "exhaust_cfm": exhaust_cfm,
            "sensible_effectiveness": 0.65,
            "kw_per_ton": kw_per_ton,
            "boiler_efficiency": PROXY_ASSUMPTIONS["boiler_efficiency"],
            "schedule": schedule,
            "bins": bins,
        }
    )
    return {
        "savings_kwh": round(float(res["savings_kwh"]), 1),
        "savings_therms": round(float(res["savings_therms"]), 1),
    }


def _fan_affinity_proxy(get, *, fan_kw: float) -> dict[str, float]:
    res = get("fan_affinity")(
        {
            "design_kw": fan_kw,
            "baseline_speed_fraction": 1.0,
            "proposed_speed_fraction": 0.80,
            "hours": 4200.0,
            "power_exponent": 3.0,
        }
    )
    return {"savings_kwh": round(float(res["savings_kwh"]), 1), "savings_therms": 0.0}


def _static_proxy(get, *, fan_kw: float) -> dict[str, float]:
    res = get("static_pressure_reset")(
        {
            "pressure_ratio": 0.7,
            "units": [
                {
                    "tag": "supply fans",
                    "motor_kw": fan_kw,
                    "avg_speed_fraction": 0.75,
                    "annual_hours": 3289.0,
                }
            ],
        }
    )
    return {"savings_kwh": round(float(res["savings_kwh"]), 1), "savings_therms": 0.0}


def _schedule_proxy(get, *, fan_kw: float, oa_cfm: float, kw_per_ton: float, bins, existing, proposed) -> dict[str, float]:
    fan = get("scheduling_fan_bins")(
        {
            "fan_kw_total": fan_kw,
            "existing_schedule": existing,
            "proposed_schedule": proposed,
            "bins": bins,
        }
    )
    cool = get("scheduling_cooling_bins")(
        {
            "oa_cfm_total": oa_cfm,
            "kw_per_ton": kw_per_ton,
            "existing_schedule": existing,
            "proposed_schedule": proposed,
            "bins": bins,
        }
    )
    heat = get("scheduling_heating_bins")(
        {
            "oa_cfm_total": oa_cfm,
            "existing_schedule": existing,
            "proposed_schedule": proposed,
            "bins": bins,
        }
    )
    return {
        "savings_kwh": round(fan["savings_kwh"] + cool["savings_kwh"], 1),
        "savings_therms": round(heat["savings_therms"], 1),
    }


def _occ_standby_dcv_proxy(get, *, oa_cfm: float, kw_per_ton: float, bins, occupied) -> dict[str, Any]:
    """Combine unoccupied damper closure with occupied DCV bin-method savings."""
    unoccupied = {"shifts": [7, 0, 5], "days_per_week": 5}
    common = {
        "oa_cfm_total": oa_cfm,
        "kw_per_ton": kw_per_ton,
        "boiler_efficiency": PROXY_ASSUMPTIONS["boiler_efficiency"],
        "bins": bins,
    }
    oad_cooling = get("oad_unoccupied_closed")({**common, "mode": "cooling", "vent_hours_schedule": unoccupied})
    oad_heating = get("oad_unoccupied_closed")({**common, "mode": "heating", "vent_hours_schedule": unoccupied})
    dcv = get("dcv_bins")(
        {
            "baseline_oa_cfm": oa_cfm,
            "proposed_oa_cfm": oa_cfm * 0.65,
            "kw_per_ton": kw_per_ton,
            "boiler_efficiency": PROXY_ASSUMPTIONS["boiler_efficiency"],
            "schedule": occupied,
            "bins": bins,
        }
    )
    return {
        "savings_kwh": round(float(oad_cooling["savings_kwh"]) + float(dcv["savings_kwh"]), 1),
        "savings_therms": round(float(oad_heating["savings_therms"]) + float(dcv["savings_therms"]), 1),
        "calculators": ["oad_unoccupied_closed", "dcv_bins"],
    }


def resolve_proxy_inputs(profile: dict[str, Any]) -> dict[str, Any]:
    """Derive ESCO bin inputs from profile area and optional nameplate sizing.

    Prefers ``cooling_tons`` / ``fan_hp`` (or ``supply_fan_hp``) when present on
    the profile, nested ``hard_size``, or ``model_seed`` — otherwise falls back
    to the screening ``PROXY_ASSUMPTIONS`` intensities.
    """
    seed = profile.get("model_seed") if isinstance(profile.get("model_seed"), dict) else {}
    hard = profile.get("hard_size") if isinstance(profile.get("hard_size"), dict) else {}

    area = float(
        profile.get("conditioned_floor_area_ft2")
        or profile.get("floor_area_ft2")
        or seed.get("conditioned_floor_area_ft2")
        or seed.get("floor_area_ft2")
        or 50000.0
    )

    def _num(*keys: str) -> float | None:
        for src in (profile, hard, seed):
            for k in keys:
                v = src.get(k)
                if v is None or v == "":
                    continue
                try:
                    f = float(v)
                except (TypeError, ValueError):
                    continue
                if f > 0:
                    return f
        return None

    cooling_tons = _num("cooling_tons", "cooling_capacity_tons")
    fan_hp = _num("fan_hp", "supply_fan_hp")

    supply_cfm = area * PROXY_ASSUMPTIONS["supply_cfm_per_ft2"]
    sources: list[str] = ["area_cfm_per_ft2"]
    if cooling_tons is not None:
        sources.append("cooling_tons")
        # ~400 cfm/ton screening airside when nameplate known
        tons_cfm = cooling_tons * 400.0
        if tons_cfm > supply_cfm:
            supply_cfm = tons_cfm

    oa_cfm = supply_cfm * PROXY_ASSUMPTIONS["oa_fraction"]
    toilet_cfm = max(0.05 * supply_cfm, 500.0)

    if fan_hp is not None:
        fan_kw = fan_hp * 0.746
        sources.append("fan_hp")
    else:
        fan_kw = supply_cfm * PROXY_ASSUMPTIONS["fan_w_per_cfm"] / 1000.0

    pump_kw = fan_kw * PROXY_ASSUMPTIONS["pump_kw_fraction_of_fan"]
    kw_per_ton = PROXY_ASSUMPTIONS["kw_per_ton"]
    heating_mmbtu = area * PROXY_ASSUMPTIONS["heating_mmbtu_per_ft2_year"]
    if cooling_tons is not None:
        # ~1,200 equivalent full-load hours screening
        ton_hours = cooling_tons * 1200.0
        sources.append("cooling_tons_eflh")
    else:
        ton_hours = area * PROXY_ASSUMPTIONS["cooling_ton_hours_per_ft2_year"]

    capacity_mbh = max(area * 0.03, 500.0)
    if cooling_tons is not None:
        # rough boiler plant screening still area-based; chiller capacity from tons
        capacity_mbh = max(capacity_mbh, cooling_tons * 12.0)

    return {
        "area_ft2": area,
        "supply_cfm": supply_cfm,
        "oa_cfm": oa_cfm,
        "toilet_cfm": toilet_cfm,
        "fan_kw": fan_kw,
        "pump_kw": pump_kw,
        "kw_per_ton": kw_per_ton,
        "heating_mmbtu": heating_mmbtu,
        "ton_hours": ton_hours,
        "capacity_mbh": capacity_mbh,
        "cooling_tons": cooling_tons,
        "fan_hp": fan_hp,
        "sources": sources,
        "existing_schedule": PROXY_ASSUMPTIONS["existing_schedule"],
        "proposed_schedule": PROXY_ASSUMPTIONS["proposed_schedule"],
    }


def estimate_proxy_savings(profile: dict[str, Any], measure_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Screening proxy savings per measure from the ESCO bin calculators."""
    from wattlab.bench import runner  # noqa: F401  (registers calculators)
    from wattlab.bench.registry import get
    from wattlab.weather.bins import washington_dc_noaa

    inputs = resolve_proxy_inputs(profile)
    area = float(inputs["area_ft2"])
    supply_cfm = float(inputs["supply_cfm"])
    oa_cfm = float(inputs["oa_cfm"])
    toilet_cfm = float(inputs["toilet_cfm"])
    fan_kw = float(inputs["fan_kw"])
    pump_kw = float(inputs["pump_kw"])
    kw_per_ton = float(inputs["kw_per_ton"])
    heating_mmbtu = float(inputs["heating_mmbtu"])
    ton_hours = float(inputs["ton_hours"])
    bins = washington_dc_noaa()
    existing = inputs["existing_schedule"]
    proposed = inputs["proposed_schedule"]
    capacity_mbh = float(inputs["capacity_mbh"])

    out: dict[str, dict[str, Any]] = {}
    for mid in measure_ids:
        try:
            if mid == "ECM-ERV" or (mid.endswith("-ERV") and "TOILET" not in mid):
                out[mid] = _erv_proxy(
                    get, oa_cfm=oa_cfm, exhaust_cfm=oa_cfm, kw_per_ton=kw_per_ton, bins=bins, schedule=existing
                )
            elif "TOILET" in mid and "ERV" in mid:
                out[mid] = _erv_proxy(
                    get,
                    oa_cfm=toilet_cfm,
                    exhaust_cfm=toilet_cfm,
                    kw_per_ton=kw_per_ton,
                    bins=bins,
                    schedule=existing,
                )
            elif mid == "ECM-ADVANCED-RTU" or "ADVANCED-RTU" in mid:
                # Bundle: fan affinity + partial economizer + schedule slice
                fan = _fan_affinity_proxy(get, fan_kw=fan_kw * 0.6)
                econ = get("dewpoint_economizer")(
                    {
                        "unit_cfm_total": supply_cfm * 0.5,
                        "oa_cfm_total": oa_cfm * 0.5,
                        "return_enthalpy": 28.3,
                        "discharge_enthalpy": 24.5,
                        "kw_per_ton": kw_per_ton,
                        "unit_type": "cv",
                        "schedule": existing,
                        "bins": bins,
                    }
                )
                sched = _schedule_proxy(
                    get,
                    fan_kw=fan_kw * 0.25,
                    oa_cfm=oa_cfm * 0.25,
                    kw_per_ton=kw_per_ton,
                    bins=bins,
                    existing=existing,
                    proposed=proposed,
                )
                out[mid] = {
                    "savings_kwh": round(
                        fan["savings_kwh"] + float(econ["savings_kwh"]) + sched["savings_kwh"],
                        1,
                    ),
                    "savings_therms": round(sched["savings_therms"], 1),
                }
            elif mid == "ECM-RCX-SETPOINT-REVIEW" or "RCX-SETPOINT" in mid:
                # Incremental RCx only — do NOT clone full schedule savings (would double-count)
                sched = _schedule_proxy(
                    get,
                    fan_kw=fan_kw,
                    oa_cfm=oa_cfm,
                    kw_per_ton=kw_per_ton,
                    bins=bins,
                    existing=existing,
                    proposed=proposed,
                )
                out[mid] = {
                    "savings_kwh": round(float(sched["savings_kwh"]) * 0.20, 1),
                    "savings_therms": round(float(sched["savings_therms"]) * 0.20, 1),
                    "basis": "python_proxy",
                    "calculators": ["scheduling_fan_bins", "rcx_incremental_0.20"],
                    "notes": "Incremental RCx setpoint review — ~20% of schedule bin savings (not additive full clone)",
                }
            elif "SCHED" in mid:
                out[mid] = _schedule_proxy(
                    get,
                    fan_kw=fan_kw,
                    oa_cfm=oa_cfm,
                    kw_per_ton=kw_per_ton,
                    bins=bins,
                    existing=existing,
                    proposed=proposed,
                )
            elif any(tok in mid for tok in ("GL36", "STATIC", "DSP", "VAV-MIN", "PREMIUM-FAN", "FAN-VFD")):
                if "DSP" in mid or "STATIC" in mid or "VAV-MIN" in mid:
                    out[mid] = _static_proxy(get, fan_kw=fan_kw)
                else:
                    out[mid] = _fan_affinity_proxy(get, fan_kw=fan_kw)
            elif "PUMP" in mid:
                res = get("pump_vfd")(
                    {
                        "design_kw": pump_kw,
                        "baseline_speed_fraction": 1.0,
                        "proposed_speed_fraction": 0.70,
                        "hours": 4000.0,
                        "power_exponent": 3.0,
                    }
                )
                out[mid] = {"savings_kwh": round(float(res["savings_kwh"]), 1), "savings_therms": 0.0}
            elif "LOCKOUT" in mid:
                # Align with FORMULA_ESCO_KWH: require cooling_tons (blank tons → 0)
                tons = float(inputs.get("cooling_tons") or 0)
                if tons <= 0:
                    out[mid] = {
                        "savings_kwh": 0.0,
                        "savings_therms": 0.0,
                        "basis": "python_proxy",
                        "notes": "Chiller lockout needs cooling_tons on Baseline — blank ≠ zero forever",
                    }
                else:
                    lockout_h = float(profile.get("lockout_hours") or 800)
                    out[mid] = {
                        "savings_kwh": round(tons * kw_per_ton * lockout_h, 1),
                        "savings_therms": 0.0,
                        "basis": "python_proxy",
                        "calculators": ["chiller_lockout_hours"],
                    }
            elif "ECON" in mid:
                res = get("dewpoint_economizer")(
                    {
                        "unit_cfm_total": supply_cfm,
                        "oa_cfm_total": oa_cfm,
                        "return_enthalpy": 28.3,
                        "discharge_enthalpy": 24.5,
                        "kw_per_ton": kw_per_ton,
                        "unit_type": "cv",
                        "schedule": existing,
                        "bins": bins,
                    }
                )
                out[mid] = {"savings_kwh": round(float(res["savings_kwh"]), 1), "savings_therms": 0.0}
            elif mid in ("ECM-OA-DAMPER-REPAIR",) or "OA-DAMPER" in mid:
                out[mid] = {
                    "savings_kwh": 0.0,
                    "savings_therms": 0.0,
                    "basis": "scope_tbd",
                    "notes": "OA damper repair — needs site OA leak hours; cost-only until scoped",
                }
            elif "SENSOR" in mid:
                out[mid] = {
                    "savings_kwh": 0.0,
                    "savings_therms": 0.0,
                    "basis": "scope_tbd",
                    "notes": "Sensor work enables other ECMs — cost-only; not an energy claim",
                }
            elif "SAT" in mid or "DAT" in mid:
                res = get("dat_reset_bins")(
                    {
                        "total_cfm": supply_cfm,
                        "oa_cfm": oa_cfm,
                        "return_enthalpy": 28.3,
                        "supply_enthalpy": 23.2,
                        "kw_per_ton": kw_per_ton,
                        "schedule": existing,
                        "bins": bins,
                        "reset": [
                            {"temp": t, "proposed_supply_enthalpy": h, "vav_fraction": v}
                            for t, h, v in [
                                (92, 23.63, 0.925),
                                (87, 24.03, 0.8),
                                (82, 24.5, 0.7),
                                (77, 25.0, 0.7),
                                (72, 25.5, 0.7),
                                (67, 26.0, 0.7),
                            ]
                        ],
                    }
                )
                out[mid] = {"savings_kwh": round(float(res["savings_kwh"]), 1), "savings_therms": 0.0}
            elif mid == "ECM-OCC-STANDBY-DCV" or ("OCC-STANDBY" in mid and "DCV" in mid):
                out[mid] = _occ_standby_dcv_proxy(
                    get, oa_cfm=oa_cfm, kw_per_ton=kw_per_ton, bins=bins, occupied=proposed
                )
            elif "DCV" in mid or mid in ("ECM-OA-RESET",) or "OA-RESET" in mid:
                res = get("dcv_bins")(
                    {
                        "baseline_oa_cfm": oa_cfm,
                        "proposed_oa_cfm": oa_cfm * 0.65,
                        "kw_per_ton": kw_per_ton,
                        "boiler_efficiency": PROXY_ASSUMPTIONS["boiler_efficiency"],
                        "schedule": proposed,
                        "bins": bins,
                    }
                )
                out[mid] = {
                    "savings_kwh": round(float(res.get("savings_kwh") or 0.0), 1),
                    "savings_therms": round(float(res.get("savings_therms") or 0.0), 1),
                    "calculators": ["dcv_bins"],
                }
            elif "BOILER-RESET" in mid or mid == "ECM-BOILER-RESET":
                res = get("hydronic_reset_bins")(
                    {
                        "mode": "hot_water",
                        "capacity_mbh": capacity_mbh,
                        "on_point_f": 55.0,
                        "design_temp_f": 0.0,
                        "max_savings_fraction": 0.08,
                        "n_reset_bins": 8,
                        "boiler_efficiency": PROXY_ASSUMPTIONS["boiler_efficiency"],
                        "schedule": existing,
                        "bins": bins,
                    }
                )
                out[mid] = {
                    "savings_kwh": 0.0,
                    "savings_therms": round(float(res.get("savings_therms") or 0.0), 1),
                }
            elif "CONDENSING-BOILER" in mid:
                res = get("boiler_efficiency_improvement")(
                    {
                        "annual_heating_mmbtu": heating_mmbtu,
                        "baseline_efficiency": PROXY_ASSUMPTIONS["boiler_efficiency"],
                        "proposed_efficiency": PROXY_ASSUMPTIONS["condensing_boiler_efficiency"],
                    }
                )
                out[mid] = {
                    "savings_kwh": 0.0,
                    "savings_therms": round(float(res["savings_therms"]), 1),
                }
            elif mid == "ECM-DOAS-HP" or "DOAS-HP" in mid:
                # Mega package: ERV ventilation recovery + heat-pump electrification.
                # HP returns negative savings_kwh (elec added) — keep as elec_delta, not "savings".
                erv = _erv_proxy(
                    get, oa_cfm=oa_cfm, exhaust_cfm=oa_cfm, kw_per_ton=kw_per_ton, bins=bins, schedule=existing
                )
                hp = get("heat_pump_electrification")(
                    {
                        "annual_heating_mmbtu": heating_mmbtu,
                        "baseline_efficiency": PROXY_ASSUMPTIONS["boiler_efficiency"],
                        "proposed_cop": 2.8,
                    }
                )
                hp_kwh = float(hp["savings_kwh"])
                out[mid] = {
                    "savings_kwh": round(float(erv["savings_kwh"]) + hp_kwh, 1),
                    "elec_delta_kwh": round(float(erv["savings_kwh"]) + hp_kwh, 1),
                    "savings_therms": round(erv["savings_therms"] + float(hp["savings_therms"]), 1),
                    "basis": "fuel_switch",
                    "calculators": ["erv_bins", "heat_pump_electrification"],
                }
            elif "AWHP" in mid:
                hp = get("heat_pump_electrification")(
                    {
                        "annual_heating_mmbtu": heating_mmbtu,
                        "baseline_efficiency": PROXY_ASSUMPTIONS["boiler_efficiency"],
                        "proposed_cop": 2.8,
                    }
                )
                hp_kwh = float(hp["savings_kwh"])
                out[mid] = {
                    "savings_kwh": round(hp_kwh, 1),
                    "elec_delta_kwh": round(hp_kwh, 1),
                    "savings_therms": round(float(hp["savings_therms"]), 1),
                    "basis": "fuel_switch",
                    "calculators": ["heat_pump_electrification"],
                }
            elif "BOILER-TUNE" in mid:
                res = get("boiler_efficiency_improvement")(
                    {
                        "annual_heating_mmbtu": heating_mmbtu,
                        "baseline_efficiency": PROXY_ASSUMPTIONS["boiler_efficiency"],
                        "proposed_efficiency": PROXY_ASSUMPTIONS["boiler_tune_efficiency"],
                    }
                )
                out[mid] = {
                    "savings_kwh": 0.0,
                    "savings_therms": round(float(res["savings_therms"]), 1),
                }
            elif "CHW-RESET" in mid or "CW-RESET" in mid:
                mode = "chilled_water"
                res = get("hydronic_reset_bins")(
                    {
                        "mode": mode,
                        "capacity_mbh": capacity_mbh,
                        "on_point_f": 55.0,
                        "design_temp_f": 95.0,
                        "max_savings_fraction": 0.05,
                        "n_reset_bins": 8,
                        "kw_per_ton": kw_per_ton,
                        "schedule": existing,
                        "bins": bins,
                    }
                )
                out[mid] = {
                    "savings_kwh": round(float(res.get("savings_kwh") or 0.0), 1),
                    "savings_therms": 0.0,
                }
            elif "CHILLER-REPLACE" in mid or "HIEFF" in mid:
                res = get("kw_per_ton_improvement")(
                    {
                        "annual_ton_hours": ton_hours,
                        "baseline_kw_per_ton": 0.70,
                        "proposed_kw_per_ton": 0.55,
                    }
                )
                out[mid] = {
                    "savings_kwh": round(float(res["savings_kwh"]), 1),
                    "savings_therms": 0.0,
                }
            elif mid == "ECM-WINDOW-HP-GLAZING" or "WINDOW-HP-GLAZING" in mid:
                # Conceptual simple-glazing proxy — ~3% site elec + ~6% heating therms at typical WWR
                wwr = float(profile.get("wwr") or profile.get("window_to_wall_ratio") or 0.45)
                wwr = max(0.15, min(wwr, 0.75))
                est_kwh = area * 12.0  # rough site kWh/ft² screening
                est_therms = heating_mmbtu * 9.8  # MMBtu → therms order-of-magnitude
                out[mid] = {
                    "savings_kwh": round(est_kwh * 0.03 * wwr / 0.45, 1),
                    "savings_therms": round(est_therms * 0.06 * wwr / 0.45, 1),
                    "basis": "envelope_proxy",
                    "calculators": ["envelope_glazing_screening"],
                    "notes": "Conceptual HP glazing — E+ via high_performance_glazing patch when cascaded",
                }
            elif mid == "ECM-ENVELOPE-INSUL-CODE" or "ENVELOPE-INSUL" in mid:
                # Opaque envelope to code — screening ~10% gas / ~2% elec (not investment-grade)
                est_kwh = area * 12.0
                est_therms = heating_mmbtu * 9.8
                out[mid] = {
                    "savings_kwh": round(est_kwh * 0.02, 1),
                    "savings_therms": round(est_therms * 0.10, 1),
                    "basis": "envelope_proxy",
                    "calculators": ["envelope_insulation_screening"],
                    "notes": "Conceptual wall/roof R upgrade — ESCO/proxy screening only (no EnergyPlus patch yet)",
                }
            else:
                out[mid] = {"savings_kwh": 0.0, "savings_therms": 0.0}
        except Exception:
            out[mid] = {"savings_kwh": 0.0, "savings_therms": 0.0}
    return out


__all__ = ["DEFAULT_MEASURE_COSTS", "PROXY_ASSUMPTIONS", "estimate_proxy_savings"]
