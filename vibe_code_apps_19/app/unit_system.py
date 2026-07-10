"""Imperial ↔ metric display conversion for Streamlit charts / tables.

Internal rule math stays in imperial (°F, in.w.c., cfm) — convert only at the UI edge.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

UnitSystem = Literal["imperial", "metric"]

# role → (imperial_unit, metric_unit, convert_fn imperial→metric)
_TEMP_ROLES = {
    "sat", "sat_sp", "mat", "rat", "oa_t", "wx_oa_t", "wx_oa_dewpoint", "wx_oa_wetbulb",
    "vav_disch_t", "vav_inlet_t", "chw_supply_t", "chw_return_t", "hw_supply_t", "hw_return_t",
    "zone_t", "cw_supply_t", "cw_return_t",
}
_STATIC_ROLES = {"duct_static", "duct_static_sp"}
_FLOW_ROLES = {"zone_flow", "min_flow_sp"}


def f_to_c(v: float) -> float:
    return (float(v) - 32.0) * 5.0 / 9.0


def c_to_f(v: float) -> float:
    return float(v) * 9.0 / 5.0 + 32.0


def inwc_to_pa(v: float) -> float:
    return float(v) * 249.0889


def cfm_to_ls(v: float) -> float:
    return float(v) * 0.47194745


def convert_series(role: str, series: pd.Series, system: UnitSystem) -> tuple[pd.Series, str]:
    """Return (converted series, display unit) for a cookbook role."""
    s = pd.to_numeric(series, errors="coerce")
    if system == "imperial":
        from app.units import DEFAULT_ROLE_UNITS

        return s, DEFAULT_ROLE_UNITS.get(role, "")
    if role in _TEMP_ROLES or role.endswith("_t") or "temp" in role.lower() or "dewpoint" in role or "wetbulb" in role:
        return (s - 32.0) * 5.0 / 9.0, "°C"
    if role in _STATIC_ROLES or "static" in role.lower():
        return s * 249.0889, "Pa"
    if role in _FLOW_ROLES or "flow" in role.lower() and "gpm" not in role.lower():
        return s * 0.47194745, "L/s"
    from app.units import DEFAULT_ROLE_UNITS

    return s, DEFAULT_ROLE_UNITS.get(role, "")


def convert_scalar_threshold(role_or_unit: str, value: float, system: UnitSystem) -> float:
    """Convert a numeric threshold for display (imperial stored → metric display)."""
    if system == "imperial":
        return float(value)
    u = role_or_unit.lower()
    if u in {"°f", "degf", "f"} or role_or_unit in _TEMP_ROLES:
        return f_to_c(value)
    if "w.c" in u or role_or_unit in _STATIC_ROLES:
        return inwc_to_pa(value)
    if u == "cfm" or role_or_unit in _FLOW_ROLES:
        return cfm_to_ls(value)
    return float(value)


def display_unit_for_role(role: str, system: UnitSystem) -> str:
    from app.units import DEFAULT_ROLE_UNITS

    if system == "imperial":
        return DEFAULT_ROLE_UNITS.get(role, "")
    if role in _TEMP_ROLES:
        return "°C"
    if role in _STATIC_ROLES:
        return "Pa"
    if role in _FLOW_ROLES:
        return "L/s"
    return DEFAULT_ROLE_UNITS.get(role, "")


def units_map_for_system(base: dict[str, str] | None, system: UnitSystem) -> dict[str, str]:
    """Rewrite a units map for the active display system."""
    from app.units import DEFAULT_ROLE_UNITS

    src = dict(DEFAULT_ROLE_UNITS)
    if base:
        src.update(base)
    if system == "imperial":
        return src
    out: dict[str, str] = {}
    for role, unit in src.items():
        out[role] = display_unit_for_role(role, "metric") or unit
    return out
