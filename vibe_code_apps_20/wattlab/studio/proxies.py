"""ESCO screening proxy savings (shared by Studio ECM page)."""

from __future__ import annotations

from typing import Any

PROXY_ASSUMPTIONS = {
    "supply_cfm_per_ft2": 1.0,
    "oa_fraction": 0.20,
    "fan_w_per_cfm": 0.8,
    "kw_per_ton": 0.9,
    "existing_schedule": {"shifts": [8, 8, 8], "days_per_week": 7},
    "proposed_schedule": {"shifts": [1, 8, 3], "days_per_week": 5, "override_allowance": 0.10},
}

DEFAULT_MEASURE_COSTS = {
    "ECM-AHU-SCHED-ALIGN": 8000.0,
    "ECM-CHILLER-LOCKOUT": 6000.0,
    "ECM-SAT-RESET": 12000.0,
    "ECM-GL36-AIRSIDE": 45000.0,
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
    fan_kw = supply_cfm * PROXY_ASSUMPTIONS["fan_w_per_cfm"] / 1000.0
    kw_per_ton = PROXY_ASSUMPTIONS["kw_per_ton"]
    bins = washington_dc_noaa()
    existing = PROXY_ASSUMPTIONS["existing_schedule"]
    proposed = PROXY_ASSUMPTIONS["proposed_schedule"]

    out: dict[str, dict[str, float]] = {}
    for mid in measure_ids:
        try:
            if "SCHED" in mid:
                fan = get("scheduling_fan_bins")({
                    "fan_kw_total": fan_kw,
                    "existing_schedule": existing,
                    "proposed_schedule": proposed,
                    "bins": bins,
                })
                cool = get("scheduling_cooling_bins")({
                    "oa_cfm_total": oa_cfm,
                    "kw_per_ton": kw_per_ton,
                    "existing_schedule": existing,
                    "proposed_schedule": proposed,
                    "bins": bins,
                })
                heat = get("scheduling_heating_bins")({
                    "oa_cfm_total": oa_cfm,
                    "existing_schedule": existing,
                    "proposed_schedule": proposed,
                    "bins": bins,
                })
                out[mid] = {
                    "savings_kwh": round(fan["savings_kwh"] + cool["savings_kwh"], 1),
                    "savings_therms": round(heat["savings_therms"], 1),
                }
            elif "GL36" in mid or "STATIC" in mid:
                res = get("static_pressure_reset")({
                    "pressure_ratio": 0.7,
                    "units": [{
                        "tag": "supply fans",
                        "motor_kw": fan_kw,
                        "avg_speed_fraction": 0.75,
                        "annual_hours": 3289.0,
                    }],
                })
                out[mid] = {"savings_kwh": round(res["savings_kwh"], 1), "savings_therms": 0.0}
            elif "LOCKOUT" in mid or "ECON" in mid:
                res = get("dewpoint_economizer")({
                    "unit_cfm_total": supply_cfm,
                    "oa_cfm_total": oa_cfm,
                    "return_enthalpy": 28.3,
                    "discharge_enthalpy": 24.5,
                    "kw_per_ton": kw_per_ton,
                    "unit_type": "cv",
                    "schedule": existing,
                    "bins": bins,
                })
                out[mid] = {"savings_kwh": round(res["savings_kwh"], 1), "savings_therms": 0.0}
            elif "SAT" in mid or "DAT" in mid:
                res = get("dat_reset_bins")({
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
                            (92, 23.63, 0.925), (87, 24.03, 0.8), (82, 24.5, 0.7),
                            (77, 25.0, 0.7), (72, 25.5, 0.7), (67, 26.0, 0.7),
                        ]
                    ],
                })
                out[mid] = {"savings_kwh": round(res["savings_kwh"], 1), "savings_therms": 0.0}
            else:
                out[mid] = {"savings_kwh": 0.0, "savings_therms": 0.0}
        except Exception:
            out[mid] = {"savings_kwh": 0.0, "savings_therms": 0.0}
    return out


__all__ = ["DEFAULT_MEASURE_COSTS", "PROXY_ASSUMPTIONS", "estimate_proxy_savings"]
