"""IDF object counts, capacity totals, and invalid IdealLoads/district cleanup."""
from __future__ import annotations

import re
from typing import Any

from eplus_gym.idf_objects import field_by_comment, iter_objects
from eplus_gym.trackb_banks import EQUIP_LIST_TYPE, HTG_TYPE, ZONEHVAC_TYPE

IDEAL_RE = re.compile(r"^Output:Variable,[^;]*Ideal Loads[^;]*;", re.I | re.M)
DISTRICT_RE = re.compile(r"^Output:Meter,District(?:HeatingWater|Cooling):Facility,[^;]*;", re.I | re.M)


def count_w2a_objects(src: str) -> dict[str, int]:
    return {
        "n_heating_coils": len(iter_objects(src, HTG_TYPE)),
        "n_zonehvac": len(iter_objects(src, ZONEHVAC_TYPE)),
        "n_equipment_lists": len(iter_objects(src, EQUIP_LIST_TYPE)),
        "n_cooling_coils": len(iter_objects(src, "Coil:Cooling:WaterToAirHeatPump:EquationFit")),
        "n_fans": len(iter_objects(src, "Fan:OnOff")),
    }


def aggregate_heating_capacity_w(src: str) -> float:
    total = 0.0
    for block in iter_objects(src, HTG_TYPE):
        raw = field_by_comment(block, "Rated Heating Capacity") or ""
        if raw.strip().lower() == "autosize":
            continue
        total += float(raw)
    return total


def strip_invalid_ideal_loads_and_district(
    src: str,
    *,
    has_ideal_loads: bool,
    has_district: bool,
) -> str:
    text = src
    if not has_ideal_loads:
        text = IDEAL_RE.sub("", text)
    if not has_district:
        text = DISTRICT_RE.sub("", text)
    return text


def inject_output_variables(src: str, names: list[str], *, frequency: str = "Timestep") -> str:
    existing = {field_by_comment(b, "Variable Name") or "" for b in iter_objects(src, "Output:Variable")}
    blocks = []
    for name in names:
        if name in existing:
            continue
        blocks.append(
            f"Output:Variable,\n  *,\n  {name},\n  {frequency};\n"
        )
    if not blocks:
        return src
    return src.rstrip() + "\n\n" + "\n".join(blocks)


def model_capacity_card(src: str) -> dict[str, Any]:
    counts = count_w2a_objects(src)
    return {
        **counts,
        "aggregate_heating_capacity_w": aggregate_heating_capacity_w(src),
        "one_w2a_per_zone": counts["n_zonehvac"] == 9 and counts["n_heating_coils"] == 9,
    }
