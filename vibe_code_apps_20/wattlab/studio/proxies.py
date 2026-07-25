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
    "ECM-ECON-REPAIR": 15000.0,
    "ECM-VAV-MIN-RESET": 20000.0,
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


def estimate_proxy_savings(profile: dict[str, Any], measure_ids: list[str]) -> dict[str, dict[str, float]]:
    """Screening proxy savings per measure from the ESCO bin calculators."""
    from wattlab.bench import runner  # noqa: F401  (registers calculators)
    from wattlab.bench.registry import get
    from wattlab.weather.bins import washington_dc_noaa

    area = float(
        profile.get("conditioned_floor_area_ft2")
        or profile.get("floor_area_ft2")
        or 50000.0
    )
    supply_cfm = area * PROXY_ASSUMPTIONS["supply_cfm_per_ft2"]
    oa_cfm = supply_cfm * PROXY_ASSUMPTIONS["oa_fraction"]
    toilet_cfm = max(0.05 * supply_cfm, 500.0)
    fan_kw = supply_cfm * PROXY_ASSUMPTIONS["fan_w_per_cfm"] / 1000.0
    pump_kw = fan_kw * PROXY_ASSUMPTIONS["pump_kw_fraction_of_fan"]
    kw_per_ton = PROXY_ASSUMPTIONS["kw_per_ton"]
    heating_mmbtu = area * PROXY_ASSUMPTIONS["heating_mmbtu_per_ft2_year"]
    ton_hours = area * PROXY_ASSUMPTIONS["cooling_ton_hours_per_ft2_year"]
    bins = washington_dc_noaa()
    existing = PROXY_ASSUMPTIONS["existing_schedule"]
    proposed = PROXY_ASSUMPTIONS["proposed_schedule"]
    capacity_mbh = max(area * 0.03, 500.0)  # screening plant capacity

    out: dict[str, dict[str, float]] = {}
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
            elif "SCHED" in mid or "RCX-SETPOINT" in mid:
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
            elif "LOCKOUT" in mid or "ECON" in mid:
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
                out[mid] = {
                    "savings_kwh": round(erv["savings_kwh"] + float(hp["savings_kwh"]), 1),
                    "savings_therms": round(erv["savings_therms"] + float(hp["savings_therms"]), 1),
                }
            elif "AWHP" in mid:
                hp = get("heat_pump_electrification")(
                    {
                        "annual_heating_mmbtu": heating_mmbtu,
                        "baseline_efficiency": PROXY_ASSUMPTIONS["boiler_efficiency"],
                        "proposed_cop": 2.8,
                    }
                )
                out[mid] = {
                    "savings_kwh": round(float(hp["savings_kwh"]), 1),
                    "savings_therms": round(float(hp["savings_therms"]), 1),
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
            else:
                out[mid] = {"savings_kwh": 0.0, "savings_therms": 0.0}
        except Exception:
            out[mid] = {"savings_kwh": 0.0, "savings_therms": 0.0}
    return out


__all__ = ["DEFAULT_MEASURE_COSTS", "PROXY_ASSUMPTIONS", "estimate_proxy_savings"]
