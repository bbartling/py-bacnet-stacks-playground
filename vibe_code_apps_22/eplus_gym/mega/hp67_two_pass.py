"""Two-pass hp67 child sizing: Autosize pass 1, hard-size pass 2 from EIO."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

from eplus_gym.idf_objects import find_named_object, normalize_idf, replace_comment_field
from eplus_gym.trackb_banks import parse_eio_component_sizing, sizing_totals_from_eio
from eplus_native.idf_inspect import NINE_ZONES

from .hp67_child_patch import HP_COUNT_67, W_PER_HP_3TON

HTG_TYPE = "Coil:Heating:WaterToAirHeatPump:EquationFit"
CLG_TYPE = "Coil:Cooling:WaterToAirHeatPump:EquationFit"
FAN_TYPE = "Fan:OnOff"

CapacitySensitivity = Literal["low", "base", "high"]
# Documented assumption: inventory counts × nominal 3-ton units unless field-proven otherwise.
CAPACITY_MULT = {"low": 0.85, "base": 1.0, "high": 1.15}


@dataclass(frozen=True)
class Hp67Pass1Spec:
    sensitivity: CapacitySensitivity
    label: str


def _autosize_fields(obj: str, fields: list[str]) -> str:
    out = obj
    for fld in fields:
        out = replace_comment_field(out, fld, "Autosize")
    return out


def patch_pass1_autosize(
    src: str,
    *,
    sensitivity: CapacitySensitivity = "base",
) -> tuple[str, list[dict[str, Any]]]:
    """Pass 1: documented capacity allocation; air/fan/water Autosize."""
    text = normalize_idf(src)
    mult = CAPACITY_MULT[sensitivity]
    patches: list[dict[str, Any]] = []
    for z in NINE_ZONES:
        n = HP_COUNT_67[z]
        cap = n * W_PER_HP_3TON * mult
        htg = find_named_object(text, HTG_TYPE, f"{z} WAHP Heating Coil")
        if not htg:
            raise ValueError(f"missing heating coil for {z}")
        new_htg = replace_comment_field(htg, "Rated Heating Capacity", f"{cap:.6g}")
        new_htg = replace_comment_field(new_htg, "Rated Air Flow Rate", "Autosize")
        new_htg = replace_comment_field(new_htg, "Rated Water Flow Rate", "Autosize")
        text = text.replace(htg, new_htg, 1)
        clg = find_named_object(text, CLG_TYPE, f"{z} WAHP Cooling Coil")
        if clg:
            new_clg = replace_comment_field(clg, "Rated Total Cooling Capacity", "Autosize")
            new_clg = replace_comment_field(new_clg, "Rated Air Flow Rate", "Autosize")
            new_clg = replace_comment_field(new_clg, "Rated Water Flow Rate", "Autosize")
            text = text.replace(clg, new_clg, 1)
        fan = find_named_object(text, FAN_TYPE, f"{z} WAHP Supply Fan")
        if fan:
            new_fan = replace_comment_field(fan, "Maximum Flow Rate", "Autosize")
            text = text.replace(fan, new_fan, 1)
        patches.append(
            {
                "zone": z,
                "hp_count_67": n,
                "capacity_sensitivity": sensitivity,
                "capacity_mult": mult,
                "assumption": "67-HP inventory × 3-ton nominal unless field-proven",
                "rated_heating_capacity_w": cap,
                "op": "pass1_capacity_autosize_air_water_fan",
            }
        )
    return text, patches


def extract_design_from_eio(eio_text: str) -> dict[str, dict[str, Any]]:
    return sizing_totals_from_eio(eio_text)


def patch_pass2_hardsize(
    pass1_text: str,
    *,
    eio_text: str,
    sensitivity: CapacitySensitivity,
) -> tuple[str, list[dict[str, Any]]]:
    """Pass 2: hard-size from Pass 1 EIO design values; record EIO sources."""
    text = normalize_idf(pass1_text)
    totals = sizing_totals_from_eio(eio_text)
    parsed = parse_eio_component_sizing(eio_text)
    patches: list[dict[str, Any]] = []
    for z in NINE_ZONES:
        row = totals[z]
        htg_name = f"{z} WAHP Heating Coil"
        clg_name = f"{z} WAHP Cooling Coil"
        fan_name = f"{z} WAHP Supply Fan"
        htg_cap = row["heating_capacity_w"]
        htg_air = row["heating_airflow_m3s"]
        htg_water = row.get("heating_water_m3s")
        if htg_water is None:
            raise ValueError(f"EIO missing heating water for {z}")
        htg = find_named_object(text, HTG_TYPE, htg_name)
        if not htg:
            raise ValueError(f"missing heating coil for {z}")
        new_htg = replace_comment_field(htg, "Rated Heating Capacity", f"{float(htg_cap):.6g}")
        new_htg = replace_comment_field(new_htg, "Rated Air Flow Rate", f"{float(htg_air):.6g}")
        new_htg = replace_comment_field(new_htg, "Rated Water Flow Rate", f"{float(htg_water):.6g}")
        text = text.replace(htg, new_htg, 1)
        clg = find_named_object(text, CLG_TYPE, clg_name)
        clg_patch: dict[str, Any] = {}
        if clg:
            new_clg = clg
            if row.get("cooling_capacity_w") is not None:
                new_clg = replace_comment_field(
                    new_clg, "Rated Total Cooling Capacity", f"{float(row['cooling_capacity_w']):.6g}"
                )
                clg_patch["Rated Total Cooling Capacity"] = float(row["cooling_capacity_w"])
            c_air = row.get("cooling_airflow_m3s") or htg_air
            new_clg = replace_comment_field(new_clg, "Rated Air Flow Rate", f"{float(c_air):.6g}")
            clg_patch["Rated Air Flow Rate"] = float(c_air)
            if row.get("cooling_water_m3s") is not None:
                new_clg = replace_comment_field(
                    new_clg, "Rated Water Flow Rate", f"{float(row['cooling_water_m3s']):.6g}"
                )
                clg_patch["Rated Water Flow Rate"] = float(row["cooling_water_m3s"])
            text = text.replace(clg, new_clg, 1)
        fan = find_named_object(text, FAN_TYPE, fan_name)
        fan_flow = None
        if fan:
            fan_key = f"FAN:ONOFF:{fan_name.upper()}"
            fan_sizing = parsed.get(fan_key) or {}
            fan_flow = fan_sizing.get("Design Maximum Flow Rate") or fan_sizing.get("Maximum Flow Rate")
            if fan_flow is not None:
                new_fan = replace_comment_field(fan, "Maximum Flow Rate", f"{float(fan_flow):.6g}")
                text = text.replace(fan, new_fan, 1)
        patches.append(
            {
                "zone": z,
                "capacity_sensitivity": sensitivity,
                "op": "pass2_hardsize_from_eio",
                "eio_sources": dict(row),
                "rated_heating_capacity_w": float(htg_cap),
                "rated_htg_airflow_m3_s": float(htg_air),
                "rated_htg_waterflow_m3_s": float(htg_water),
                "fan_max_flow_m3_s": fan_flow,
            }
        )
    return text, patches


def child_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
