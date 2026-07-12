"""Simple YAML role mapping — flat and nested multi-site (no Haystack/Oxigraph)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from app.mapping_wizard import (
    DEFAULT_BUILDING_ID,
    DEFAULT_SITE_ID,
    flat_role_map_from_sites,
    is_nested_role_map,
    load_site_mapping,
    save_site_mapping,
    sites_from_yaml,
    wrap_flat_role_map,
)

ROLE_ALIASES = {
    "outside_air_temp": "oa_t",
    "outside_air_temp_f": "oa_t",
    "discharge_air_temp": "sat",
    "discharge_air_temp_f": "sat",
    "return_air_temp": "rat",
    "mixed_air_temp": "mat",
    "zone_temp": "zone_t",
    "space_temp": "zone_t",
    "supply_fan_cmd": "fan_cmd",
    "cooling_valve": "clg_valve_pct",
    "outdoor_air_damper": "oa_damper_pct",
}

POINT_ROLE_CANONICAL: dict[str, str] = {
    "discharge_air_temp": "sat",
    "return_air_temp": "rat",
    "mixed_air_temp": "mat",
    "outside_air_temp": "oa_t",
    "oat": "oa_t",
    "zone_temp": "zone_t",
    "space_temp": "zone_t",
    "chw_valve": "clg_valve_pct",
    "cooling_valve": "clg_valve_pct",
    "heating_valve": "htg_valve_pct",
    "hw_valve": "htg_valve_pct",
    "reheat_valve": "reheat_valve_pct",
    "damper": "oa_damper_pct",
    "oa_damper": "oa_damper_pct",
    "airflow": "zone_flow",
    "fan_cmd": "fan_cmd",
    "fan_speed": "fan_cmd",
    "supply_fan": "fan_cmd",
    "fan_status": "fan_status",
    "occ_mode": "occ_mode",
    "chw_supply": "chw_supply_t",
    "chw_return": "chw_return_t",
    "chiller": "chiller_status",
    "chiller_command": "chiller_status",
    "power": "chiller_power_kw",
    "chw_pump_status": "chw_pump_status",
    "chw_pump": "chw_pump_cmd",
    "primary_chw_pump_status": "chw_pump_status",
    "primary_chw_pump": "chw_pump_status",
}

COL_PATTERN_ROLES: list[tuple[tuple[str, ...], str]] = [
    (("discharge_air_temp_f", "da-t"), "sat"),
    (("dat_reset", "sat_sp", "sat_setpoint"), "sat_sp"),
    (("return_air_temp", "ra-t"), "rat"),
    (("mixed_air_temp", "mat"), "mat"),
    # Prefer real OAT columns — not oat_*_setpoint / enable setpoints
    (("outside_air_temp", "oa-t", "oat_f"), "oa_t"),
    (("ex_dmpr", "oa_damper", "outdoor_air_damper"), "oa_damper_pct"),
    (("chw_valve", "clg_valve", "cooling_valve"), "clg_valve_pct"),
    (("hw_valve", "htg_valve", "heating_valve"), "htg_valve_pct"),
    # Supply fan before generic fan_speed (avoids return_fan_speed winning)
    (("supply_fan_speed", "supply_fan_cmd"), "fan_cmd"),
    (("supply_fan_status", "supplyfanstatus"), "fan_status"),
    (("fan_cmd",), "fan_cmd"),
    (("fan_status", "fan_proof"), "fan_status"),
    (("da_p_setpoint", "duct_static_sp"), "duct_static_sp"),
    (("da_p_inwc", "duct_static"), "duct_static"),
    (("space_temp", "spacetemp"), "zone_t"),
    (("reheat", "rht_valve"), "reheat_valve_pct"),
    (("vavactuator", "damper_pct", "damper_pos"), "damper_pct"),
    (("actflow", "airflow_cfm"), "zone_flow"),
    (("minflowsp", "min_airflow"), "min_flow_sp"),
    (("vav_disch", "dischargeairtemp"), "vav_disch_t"),
    (("ductintemp", "duct_in"), "vav_inlet_t"),
    # Central plant
    (("chws_t", "chw_supply", "chilled_water_supply"), "chw_supply_t"),
    (("chwr_t", "chw_return", "chilled_water_return"), "chw_return_t"),
    (("hws_t", "hw_supply"), "hw_supply_t"),
    (("hwr_t", "hw_return"), "hw_return_t"),
    (("chiller_1_command", "chiller_2_command", "chiller_command"), "chiller_status"),
    (("chiller_1_amps", "chiller_2_amps", "amps_a"), "chiller_amps"),
    (("power_demand_this_interval", "meter_power_sum_kw", "elec_kw", "building_kw"), "elec_power_kw"),
    (("chiller_power", "meter_chiller"), "chiller_power_kw"),
    (("gas_flow", "nat_gas", "gas_therm", "gas_cfh"), "gas_flow"),
    (("hwp1_c", "hwp2_c", "hwp3_c", "hw_pump_cmd"), "hw_pump_cmd"),
    (("hwp1_s", "hwp2_s", "hwp3_s", "pump_status"), "pump_status"),
    # Designated CHW pump for chiller runtime (data-model role; prefer over chiller cmd)
    (("chw_pump_status", "cwp1_s", "cwp2_s", "primary_chw_pump_status"), "chw_pump_status"),
    (("chw_pump_cmd", "cwp1_c", "cwp2_c", "primary_chw_pump_cmd", "chw_pump"), "chw_pump_cmd"),
]

ROLE_COLUMN_RANK: dict[str, tuple[str, ...]] = {
    "zone_t": ("spacetemp", "space_temp", "zone_temp"),
    "zone_flow": ("actflow", "flow_input", "airflow"),
    "min_flow_sp": ("minflowsp", "min_airflow"),
    "sat": ("discharge_air_temp_f", "da-t"),
    "sat_sp": ("dat_reset", "sat_sp"),
    "oa_damper_pct": ("ex_dmpr", "oa_damper"),
    "damper_pct": ("damper_pct", "vavactuator", "heatingdamper"),
    # Prefer supply fan over return fan for AHU runtime
    "fan_cmd": ("supply_fan_speed", "supply_fan", "sf_", "fan_cmd"),
    "fan_status": ("supply_fan_status", "supplyfanstatus", "supply_fan", "fan_status"),
    "oa_t": ("outside_air_temp", "oa_t", "oat_f"),
    "chw_supply_t": ("chws_t", "chw_supply"),
    "chw_return_t": ("chwr_t", "chw_return"),
    "chiller_status": ("chiller_1_command", "chiller_2_command", "chiller_command", "command"),
    "chiller_amps": ("amps_a", "current_sum", "amps"),
    "chiller_power_kw": ("power_demand_this_interval", "meter_power_sum", "power"),
    "hw_pump_cmd": ("hwp1_c", "hwp2_c", "hw_pump"),
    "pump_status": ("hwp1_s", "hwp2_s", "pump_status"),
    "chw_pump_status": ("chw_pump_status", "cwp1_s", "cwp2_s", "primary_chw_pump"),
    "chw_pump_cmd": ("chw_pump_cmd", "cwp1_c", "cwp2_c"),
}


def _canonical_role(point_role: str, col: str) -> str | None:
    pr = point_role.strip().lower()
    if pr in POINT_ROLE_CANONICAL:
        return POINT_ROLE_CANONICAL[pr]
    if pr in ROLE_ALIASES:
        return ROLE_ALIASES[pr]
    cl = col.lower()
    for patterns, role in COL_PATTERN_ROLES:
        if any(p in cl for p in patterns):
            return role
    return None


def _rank_column(role: str, col: str) -> int:
    cl = col.lower()
    # Hard demote return-fan columns when mapping supply fan roles
    if role in {"fan_cmd", "fan_status"} and "return" in cl:
        return 90
    # Demote setpoints masquerading as OAT
    if role == "oa_t" and ("setpoint" in cl or "enable" in cl or "reset" in cl):
        return 95
    prefs = ROLE_COLUMN_RANK.get(role, ())
    for i, p in enumerate(prefs):
        if p in cl:
            return i
    if "alarm" in cl or "limit" in cl or ("setpoint" in cl and role == "zone_t"):
        return 100
    return 50


def load_role_map(path: Path) -> dict[str, dict[str, str]]:
    """Load flat equipment→roles map (nested YAML is unwrapped)."""
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    if is_nested_role_map(data):
        return flat_role_map_from_sites(sites_from_yaml(data))
    return {str(k): {str(r): str(c) for r, c in v.items()} for k, v in data.items() if isinstance(v, dict)}


def load_role_map_nested(path: Path):
    return load_site_mapping(path)


def save_role_map(path: Path, mapping: dict[str, dict[str, str]], *, nested: bool = False) -> None:
    if nested:
        save_site_mapping(path, wrap_flat_role_map(mapping))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(mapping, sort_keys=True), encoding="utf-8")


def roles_from_columns_csv(columns_path: Path | None) -> dict[str, str]:
    if columns_path is None or not Path(columns_path).is_file():
        return {}
    df = pd.read_csv(columns_path)
    col_key = "column" if "column" in df.columns else "col" if "col" in df.columns else df.columns[0]
    role_key = next((c for c in ("point_role", "role") if c in df.columns), None)
    candidates: dict[str, list[tuple[int, str]]] = {}
    for _, row in df.iterrows():
        col = str(row[col_key]).strip()
        if not col or col in ("col", "column"):
            continue
        pr = str(row[role_key]).strip() if role_key else ""
        role = _canonical_role(pr, col) if pr else None
        if role is None:
            for patterns, r in COL_PATTERN_ROLES:
                if any(p in col.lower() for p in patterns):
                    role = r
                    break
        if role is None:
            continue
        candidates.setdefault(role, []).append((_rank_column(role, col), col))
    out: dict[str, str] = {}
    for role, opts in candidates.items():
        opts.sort(key=lambda x: x[0])
        # Skip demoted matches (return-fan, OAT setpoints, etc.) when nothing better exists
        if opts[0][0] >= 90:
            continue
        out[role] = opts[0][1]
    return out


def enrich_role_map_from_equipment(
    role_map: dict[str, dict[str, str]],
    equipment_id: str,
    columns_path: Path | None,
    history_columns: list[str] | None = None,
) -> dict[str, dict[str, str]]:
    """Fill missing roles only — never overwrite an existing mapping with a weaker heuristic."""
    merged = dict(role_map.get(equipment_id, {}))
    for role, col in roles_from_columns_csv(columns_path).items():
        if role not in merged:
            merged[role] = col
    if history_columns:
        for role, col in suggest_roles(pd.DataFrame(columns=history_columns)).items():
            if role not in merged:
                merged[role] = col
        # Re-pick best column among candidates when both supply+return exist
        for role in ("fan_cmd", "fan_status", "oa_t", "chw_supply_t", "chiller_status"):
            if role in merged:
                continue
        allowed = set(history_columns)
        # If fan roles point at return fan but supply exists, upgrade
        for role in ("fan_cmd", "fan_status"):
            col = merged.get(role)
            if col and "return" in col.lower():
                suggested = suggest_roles(pd.DataFrame(columns=history_columns)).get(role)
                if suggested and "supply" in suggested.lower():
                    merged[role] = suggested
        merged = {role: col for role, col in merged.items() if col in allowed}
    role_map[equipment_id] = merged
    return role_map


def suggest_roles(df: pd.DataFrame) -> dict[str, str]:
    out: dict[str, str] = {}
    for col in df.columns:
        for patterns, role in COL_PATTERN_ROLES:
            if any(p in col.lower() for p in patterns):
                if role not in out or _rank_column(role, col) < _rank_column(role, out[role]):
                    out[role] = col
                break
    return out


def apply_role_map(df: pd.DataFrame, equipment_id: str, role_map: dict[str, dict[str, str]]) -> pd.DataFrame:
    eq_map = role_map.get(equipment_id, {})
    out = df.copy()
    # Meta keys are equipment links / notes — not timeseries columns
    skip = {"chw_pump_equipment", "notes", "equipment_type", "plant_group"}
    for role, col in eq_map.items():
        if role in skip or not col or not isinstance(col, str):
            continue
        if col in out.columns:
            out[role] = pd.to_numeric(out[col], errors="coerce")
    return out


def resolve_role(df: pd.DataFrame, equipment_id: str, role_map: dict, role: str) -> pd.Series | None:
    mapped = apply_role_map(df, equipment_id, role_map)
    if role in mapped.columns:
        return mapped[role]
    return None


def validate_required_roles(equipment_id: str, df: pd.DataFrame, role_map: dict, required: list[str]) -> list[str]:
    mapped = apply_role_map(df, equipment_id, role_map)
    return [r for r in required if r not in mapped.columns or mapped[r].isna().all()]


__all__ = [
    "DEFAULT_BUILDING_ID",
    "DEFAULT_SITE_ID",
    "apply_role_map",
    "enrich_role_map_from_equipment",
    "load_role_map",
    "load_role_map_nested",
    "roles_from_columns_csv",
    "save_role_map",
    "suggest_roles",
    "validate_required_roles",
]
