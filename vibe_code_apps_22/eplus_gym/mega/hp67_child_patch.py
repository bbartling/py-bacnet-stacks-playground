"""Build a04_child_hp67_scaled_v1 — per-zone capacity + airflow + water flow scaling."""
from __future__ import annotations

import hashlib
from typing import Any

from eplus_gym.idf_objects import field_by_comment, find_named_object, normalize_idf, replace_comment_field
from eplus_native.idf_inspect import NINE_ZONES

HP_COUNT_67 = {
    "1F_Library_IMC": 2,
    "1F_Cafe_Kitchen": 3,
    "1F_Gym": 4,
    "1F_Area_A": 13,
    "1F_Area_B": 10,
    "1F_Area_C": 8,
    "1F_Area_D": 6,
    "2F_Area_A": 11,
    "2F_Area_B": 10,
}
TON_W = 3516.8525
CFM_PER_TON = 400.0
CFM_TO_M3S = 0.00047194745
W_PER_HP_3TON = 3.0 * TON_W
PARENT_NOMINAL_HTG_W = 149430.0

HTG_TYPE = "Coil:Heating:WaterToAirHeatPump:EquationFit"
CLG_TYPE = "Coil:Cooling:WaterToAirHeatPump:EquationFit"
FAN_TYPE = "Fan:OnOff"


def _num(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    low = raw.strip().lower()
    if low in {"autosize", "autocalculate"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def patch_hp67_scaled_v1(src: str) -> tuple[str, list[dict[str, Any]]]:
    """Scale rated capacity, airflow, and water flow together per 67-HP BAS split."""
    text = normalize_idf(src)
    patches: list[dict[str, Any]] = []
    for z in NINE_ZONES:
        n = HP_COUNT_67[z]
        cap = n * W_PER_HP_3TON
        air = n * 3.0 * CFM_PER_TON * CFM_TO_M3S
        htg = find_named_object(text, HTG_TYPE, f"{z} WAHP Heating Coil")
        if not htg:
            raise ValueError(f"missing heating coil for {z}")
        parent_wtr = _num(field_by_comment(htg, "Rated Water Flow Rate"))
        if parent_wtr is None or PARENT_NOMINAL_HTG_W <= 0:
            raise ValueError(
                f"{z}: missing parent rated water flow — refuse water=air*0.05 fallback"
            )
        water = parent_wtr * (cap / PARENT_NOMINAL_HTG_W)
        new_htg = replace_comment_field(htg, "Rated Heating Capacity", f"{cap:.6g}")
        new_htg = replace_comment_field(new_htg, "Rated Air Flow Rate", f"{air:.6g}")
        new_htg = replace_comment_field(new_htg, "Rated Water Flow Rate", f"{water:.6g}")
        text = text.replace(htg, new_htg, 1)
        clg = find_named_object(text, CLG_TYPE, f"{z} WAHP Cooling Coil")
        if clg:
            parent_clg_cap = _num(field_by_comment(clg, "Rated Total Cooling Capacity"))
            parent_clg_air = _num(field_by_comment(clg, "Rated Air Flow Rate"))
            parent_clg_wtr = _num(field_by_comment(clg, "Rated Water Flow Rate"))
            scale = cap / PARENT_NOMINAL_HTG_W
            new_clg = clg
            if parent_clg_cap is not None:
                new_clg = replace_comment_field(new_clg, "Rated Total Cooling Capacity", f"{parent_clg_cap * scale:.6g}")
            if parent_clg_air is not None:
                new_clg = replace_comment_field(new_clg, "Rated Air Flow Rate", f"{parent_clg_air * scale:.6g}")
            elif parent_clg_cap is None:
                new_clg = replace_comment_field(new_clg, "Rated Air Flow Rate", f"{air:.6g}")
            if parent_clg_wtr is not None:
                new_clg = replace_comment_field(new_clg, "Rated Water Flow Rate", f"{parent_clg_wtr * scale:.6g}")
            text = text.replace(clg, new_clg, 1)
        fan = find_named_object(text, FAN_TYPE, f"{z} WAHP Supply Fan")
        if fan:
            parent_fan = _num(field_by_comment(fan, "Maximum Flow Rate"))
            if parent_fan is not None and PARENT_NOMINAL_HTG_W > 0:
                fan_flow = parent_fan * (cap / PARENT_NOMINAL_HTG_W)
            else:
                fan_flow = air
            new_fan = replace_comment_field(fan, "Maximum Flow Rate", f"{fan_flow:.6g}")
            text = text.replace(fan, new_fan, 1)
        patches.append(
            {
                "zone": z,
                "hp_count_67": n,
                "rated_heating_capacity_w": cap,
                "rated_htg_airflow_m3_s": air,
                "rated_htg_waterflow_m3_s": water,
                "op": "scale_capacity_airflow_water_together",
            }
        )
    return text, patches


def child_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
