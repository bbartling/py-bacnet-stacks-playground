"""Machine-readable EnergyPlus calibration-readiness (operational evidence, not a model)."""

from __future__ import annotations

from typing import Any

import pandas as pd

# Fuel bills are not in the Vibe19 tree; Studio/vibe20 owns fuel dashboards.
FUEL_PACKAGE_NOTE = (
    "Building 100 fuel-use package is not bundled in this application. "
    "Link or attach utility fuel data from WattLab Studio / vibe_code_apps_20 "
    "before treating the seed as calibration-ready."
)


def _item(
    requirement: str,
    *,
    present: bool,
    value: Any = None,
    consequence: str,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "requirement": requirement,
        "present": bool(present),
        "value": value,
        "consequence": None if present else consequence,
        "note": note,
    }


def _consecutive_months(index: pd.DatetimeIndex | None) -> int:
    if index is None or len(index) == 0:
        return 0
    try:
        months = pd.PeriodIndex(index.tz_convert("UTC") if index.tz is not None else index, freq="M")
    except Exception:
        return 0
    uniq = sorted(set(months.astype(str)))
    if not uniq:
        return 0
    # Count longest consecutive YYYY-MM run
    best = cur = 1
    prev = pd.Period(uniq[0], freq="M")
    for label in uniq[1:]:
        p = pd.Period(label, freq="M")
        if p == prev + 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
        prev = p
    return best


def build_calibration_readiness(
    *,
    seed: dict[str, Any] | None,
    frames: dict[str, pd.DataFrame] | None = None,
    weather: pd.DataFrame | None = None,
    timezone: str | None = None,
    fuel_linked: bool = False,
    electric_bills: list[dict[str, Any]] | None = None,
    schedule_is_local: bool | None = None,
) -> dict[str, Any]:
    seed = seed or {}
    frames = frames or {}
    idx: pd.DatetimeIndex | None = None
    for df in frames.values():
        if isinstance(df.index, pd.DatetimeIndex) and len(df.index):
            if idx is None:
                idx = df.index
            else:
                idx = idx.union(df.index)
    months = _consecutive_months(idx if isinstance(idx, pd.DatetimeIndex) else None)
    tz = timezone or seed.get("timezone") or (seed.get("data_window") or {}).get("timezone")
    city = seed.get("city")
    lat, lon = seed.get("lat"), seed.get("lon")
    floor = seed.get("floor_area_ft2")
    btype = seed.get("building_type")
    hints = seed.get("schedule_hints") or {}
    inferred = seed.get("inferred_parameters") or []
    has_wx = weather is not None and isinstance(weather, pd.DataFrame) and not weather.empty
    has_elec = bool(electric_bills) or bool(seed.get("utility_bills"))
    local_ok = bool(schedule_is_local) if schedule_is_local is not None else (
        bool(tz) and str(tz).upper() not in {"UTC", "ETC/UTC", "Z"}
    )

    items = [
        _item(
            "local_standard_timezone",
            present=local_ok,
            value=tz,
            consequence="EnergyPlus schedules will be wrong if UTC historian hours are treated as local civil time.",
            note="Never treat UTC transition hours as local EnergyPlus schedules.",
        ),
        _item(
            "city_and_coordinates",
            present=bool(city) and lat is not None and lon is not None,
            value={"city": city, "lat": lat, "lon": lon},
            consequence="Weather file selection and design-day climate cannot be fixed.",
        ),
        _item(
            "floor_area_and_building_type",
            present=floor is not None and bool(btype),
            value={"floor_area_ft2": floor, "building_type": btype},
            consequence="EUI and load-intensity checks cannot be normalized.",
        ),
        _item(
            "geometry_and_envelope",
            present=False,
            consequence="This seed is operational evidence only — no calibrated geometry/envelope.",
        ),
        _item(
            "hvac_capacity_and_efficiency",
            present=False,
            consequence="Plant/coil sizes and COPs must be supplied or measured before calibration.",
        ),
        _item(
            "lighting_and_plug_loads",
            present=False,
            consequence="Internal gains remain unknown; energy match will be under-constrained.",
        ),
        _item(
            "thermostat_and_occupancy_schedules",
            present=bool(hints) or bool(inferred),
            value={"schedule_hints": bool(hints), "inferred_parameter_count": len(inferred)},
            consequence="Occupied/unoccupied setpoints and schedules cannot be seeded.",
            note="Inferred hours are evidence, not an EnergyPlus schedule object.",
        ),
        _item(
            "electric_utility_data",
            present=has_elec,
            value={"bill_rows": len(electric_bills or seed.get("utility_bills") or [])},
            consequence="Monthly electric calibration target is missing.",
        ),
        _item(
            "fuel_utility_data",
            present=fuel_linked,
            consequence="Gas/steam calibration cannot be performed.",
            note=FUEL_PACKAGE_NOTE,
        ),
        _item(
            "twelve_consecutive_months",
            present=months >= 12,
            value={"longest_consecutive_months": months},
            consequence="ASHRAE Guideline 14-style calibration typically needs ≥12 consecutive months.",
        ),
        _item(
            "actual_year_weather_or_epw",
            present=has_wx,
            consequence="No observed weather/EPW — cannot build an actual-year weather file from this bundle.",
        ),
    ]
    missing = [i["requirement"] for i in items if not i["present"]]
    return {
        "schema": "openfdd_calibration_readiness_v1",
        "model_seed_is_calibrated_model": False,
        "ready": len(missing) == 0,
        "missing_requirements": missing,
        "items": items,
    }
