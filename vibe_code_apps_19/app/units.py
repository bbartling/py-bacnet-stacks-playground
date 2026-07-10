"""Default engineering units for cookbook roles / Haystack points (no mixed-unit plots)."""

from __future__ import annotations

# Cookbook role → display unit
DEFAULT_ROLE_UNITS: dict[str, str] = {
    "sat": "°F",
    "sat_sp": "°F",
    "mat": "°F",
    "rat": "°F",
    "oa_t": "°F",
    "vav_disch_t": "°F",
    "vav_inlet_t": "°F",
    "chw_supply_t": "°F",
    "chw_return_t": "°F",
    "hw_supply_t": "°F",
    "hw_return_t": "°F",
    "zone_t": "°F",
    "oa_damper_pct": "%",
    "clg_valve_pct": "%",
    "htg_valve_pct": "%",
    "damper_pct": "%",
    "reheat_valve_pct": "%",
    "fan_cmd": "%",
    "control_output_pct": "%",
    "loop_enabled": "",
    "fan_status": "bool",
    "duct_static": "in. w.c.",
    "duct_static_sp": "in. w.c.",
    "zone_flow": "cfm",
    "min_flow_sp": "cfm",
    "occ_mode": "bool",
}

# Unit family key used to group series onto the same subplot (never mix families).
UNIT_FAMILY: dict[str, str] = {
    "°F": "temp_F",
    "degF": "temp_F",
    "F": "temp_F",
    "%": "pct",
    "percent": "pct",
    "in. w.c.": "static",
    "inWC": "static",
    "in_wc": "static",
    "cfm": "flow",
    "bool": "bool",
    "0/1": "bool",
}


def unit_family(unit: str) -> str:
    u = (unit or "").strip()
    return UNIT_FAMILY.get(u, UNIT_FAMILY.get(u.lower(), f"other:{u or 'unknown'}"))


def resolve_role_unit(role: str, units_map: dict[str, str] | None = None) -> str:
    if units_map and role in units_map and units_map[role]:
        return str(units_map[role])
    return DEFAULT_ROLE_UNITS.get(role, "")
