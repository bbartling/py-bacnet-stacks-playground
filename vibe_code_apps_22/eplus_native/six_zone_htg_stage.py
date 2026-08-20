"""Stage six independent heating DualSetpoints for W2A DSM (champion untouched)."""
from __future__ import annotations

import re
from typing import Any

from eplus_native.idf_inspect import NINE_ZONES
from eplus_native.zone_agg import load_agg_contract

# Stable action order — never rely on dict iteration.
ACTION_KEYS = (
    "1F_A",
    "1F_B",
    "1F_C",
    "1F_D",
    "2F_A",
    "2F_B",
)

ACTION_TO_BAS = {
    "1F_A": "1F_Area_A",
    "1F_B": "1F_Area_B",
    "1F_C": "1F_Area_C",
    "1F_D": "1F_Area_D",
    "2F_A": "2F_Area_A",
    "2F_B": "2F_Area_B",
}

SHARED_DUALSP = "Lakeside_AllZones_Tstat Dual SP Control"
DEFAULT_HTG_C = 21.11  # 70°F


def dsm_htg_schedule_name(action_key: str) -> str:
    if action_key not in ACTION_KEYS:
        raise ValueError(f"unknown action key {action_key}")
    return f"DSM_HTG_SP_{action_key}"


def dsm_dualsp_name(action_key: str) -> str:
    if action_key not in ACTION_KEYS:
        raise ValueError(f"unknown action key {action_key}")
    return f"DSM_DualSP_{action_key}"


def eplus_zone_to_action_key(contract: dict[str, Any] | None = None) -> dict[str, str]:
    """Map each of nine E+ zones → ACTION_KEYS using the nine-to-six contract."""
    cal = contract or load_agg_contract()
    out: dict[str, str] = {}
    for key in ACTION_KEYS:
        bas = ACTION_TO_BAS[key]
        members = list(cal["aggregation"][bas]["members"])
        for z in members:
            out[z] = key
    missing = [z for z in NINE_ZONES if z not in out]
    if missing:
        raise ValueError(f"zones not mapped to ACTION_KEYS: {missing}")
    return out


def _always_on_htg_schedule(name: str, value_c: float = DEFAULT_HTG_C) -> str:
    return (
        "SCHEDULE:COMPACT,\n"
        f"    {name},                !- Name\n"
        "    Temperature,              !- Schedule Type Limits Name\n"
        "    Through: 12/31,           !- Field 1\n"
        "    For: AllDays,             !- Field 2\n"
        "    Until: 24:00,             !- Field 3\n"
        f"    {value_c:.4g};                    !- Field 4\n"
    )


def _dualsp_block(action_key: str) -> str:
    return (
        "ThermostatSetpoint:DualSetpoint,\n"
        f"  {dsm_dualsp_name(action_key)},                 !- Name\n"
        f"  {dsm_htg_schedule_name(action_key)},                                               !- Heating Setpoint Temperature Schedule Name\n"
        "  SCH_ClgSP;                                               !- Cooling Setpoint Temperature Schedule Name\n"
    )


def stage_six_zone_heating_actuators(
    text: str, *, heating_c: float = DEFAULT_HTG_C
) -> tuple[str, dict[str, Any]]:
    """Rewrite staged IDF text for six independent heating schedule actuators.

    Does not modify the published champion — caller must write a staged copy.
    ``heating_c`` is the constant DualSP heating value (°C) written into each
    ``DSM_HTG_SP_*`` Schedule:Compact (default 21.11 °C = 70 °F).
    """
    zone_to_key = eplus_zone_to_action_key()
    sp = float(heating_c)
    # Insert six schedules + DualSPs after the shared DualSP block (or before first ZoneControl)
    schedules = "\n".join(
        _always_on_htg_schedule(dsm_htg_schedule_name(k), value_c=sp) for k in ACTION_KEYS
    )
    duals = "\n".join(_dualsp_block(k) for k in ACTION_KEYS)
    inject = (
        "\n! --- DSM six-zone heating actuators (staged only) ---\n"
        + schedules
        + "\n"
        + duals
        + "\n"
    )

    # Prefer inject immediately after shared DualSP object
    dual_pat = re.compile(
        rf"ThermostatSetpoint:DualSetpoint,\s*\n\s*{re.escape(SHARED_DUALSP)}\s*,.*?;",
        re.I | re.S,
    )
    m = dual_pat.search(text)
    if m:
        text = text[: m.end()] + inject + text[m.end() :]
    else:
        text = text.rstrip() + inject

    # Rewire each ZoneControl:Thermostat Control Name to the mapped DualSP
    for zone, key in zone_to_key.items():
        tstat = f"{zone} Thermostat"
        dual = dsm_dualsp_name(key)
        zc_pat = re.compile(
            rf"(ZoneControl:Thermostat,\s*\n\s*{re.escape(tstat)}\s*,.*?"
            rf"ThermostatSetpoint:DualSetpoint,[^\n]*\n\s*)"
            rf"{re.escape(SHARED_DUALSP)}\s*;",
            re.I | re.S,
        )
        text2, n = zc_pat.subn(rf"\g<1>{dual};", text, count=1)
        if n != 1:
            zc_pat2 = re.compile(
                rf"({re.escape(tstat)}\s*,[^\n]*\n(?:.*?\n)*?\s*ThermostatSetpoint:DualSetpoint,[^\n]*\n\s*)"
                rf"[^;\n]+;",
                re.I,
            )
            text2, n = zc_pat2.subn(rf"\g<1>{dual};", text, count=1)
        if n != 1:
            raise ValueError(f"could not rewire ZoneControl:Thermostat for {zone}")
        text = text2

    provenance = {
        "action_keys": list(ACTION_KEYS),
        "schedules": [dsm_htg_schedule_name(k) for k in ACTION_KEYS],
        "dualsps": [dsm_dualsp_name(k) for k in ACTION_KEYS],
        "zone_to_action_key": zone_to_key,
        "shared_dualsp_retained": SHARED_DUALSP,
        "contract": "eplus_nine_to_six_zone_agg_v1",
        "heating_c": sp,
    }
    return text, provenance


def verify_six_zone_staging(text: str) -> dict[str, Any]:
    """Fail-closed checks that six schedules + DualSPs + rewires exist."""
    issues: list[str] = []
    for k in ACTION_KEYS:
        sch = dsm_htg_schedule_name(k)
        dual = dsm_dualsp_name(k)
        if not re.search(rf"SCHEDULE:COMPACT,\s*\n\s*{re.escape(sch)}\s*,", text, re.I):
            issues.append(f"missing schedule {sch}")
        if not re.search(
            rf"ThermostatSetpoint:DualSetpoint,\s*\n\s*{re.escape(dual)}\s*,",
            text,
            re.I,
        ):
            issues.append(f"missing DualSP {dual}")
    zone_to_key = eplus_zone_to_action_key()
    for zone, key in zone_to_key.items():
        dual = dsm_dualsp_name(key)
        if not re.search(
            rf"{re.escape(zone)} Thermostat,[^\n]*\n(?:.*?\n)*?\s*{re.escape(dual)}\s*;",
            text,
            re.I,
        ):
            issues.append(f"thermostat {zone} not on {dual}")
    return {"ok": not issues, "issues": issues, "zone_to_action_key": zone_to_key}
