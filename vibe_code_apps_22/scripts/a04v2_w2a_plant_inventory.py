"""Nine W2A unit inventory from immutable A04 + 67 vs 79 HP-count contracts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.idf_objects import field_by_comment, find_named_object, iter_objects
from eplus_native.idf_inspect import NINE_ZONES

# BAS 67-HP map (thermal_zone_model.json). Library/Cafe/Gym are subsets of area counts.
BAS_SIX_HP = {
    "1F_Area_A": 15,
    "1F_Area_B": 10,
    "1F_Area_C": 11,
    "1F_Area_D": 10,
    "2F_Area_A": 11,
    "2F_Area_B": 10,
}
# Split special banks out of parent areas so nine units sum to 67.
HP_COUNT_67 = {
    "1F_Library_IMC": 2,
    "1F_Cafe_Kitchen": 3,
    "1F_Gym": 4,
    "1F_Area_A": 13,  # 15 − 2 library
    "1F_Area_B": 10,
    "1F_Area_C": 8,  # 11 − 3 cafe
    "1F_Area_D": 6,  # 10 − 4 gym
    "2F_Area_A": 11,
    "2F_Area_B": 10,
}
TON_W = 3516.8525
CFM_PER_TON = 400.0
CFM_TO_M3S = 0.00047194745
W_PER_HP_3TON = 3.0 * TON_W

HTG_TYPE = "Coil:Heating:WaterToAirHeatPump:EquationFit"
CLG_TYPE = "Coil:Cooling:WaterToAirHeatPump:EquationFit"


def _num(raw: str | None) -> float | str | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return raw


def inventory_from_idf(src: str, agg: dict) -> dict:
    n_htg = len(iter_objects(src, HTG_TYPE))
    units = []
    agg_hp = agg.get("default_hp_counts") or {}
    for z in NINE_ZONES:
        htg = find_named_object(src, HTG_TYPE, f"{z} WAHP Heating Coil")
        clg = find_named_object(src, CLG_TYPE, f"{z} WAHP Cooling Coil")
        fan = find_named_object(src, "Fan:OnOff", f"{z} WAHP Supply Fan")
        zone = find_named_object(src, "Zone", z) or find_named_object(src, "ZONE", z)
        units.append(
            {
                "zone": z,
                "hp_count_67_split": HP_COUNT_67[z],
                "hp_count_agg_v1": agg_hp.get(z),
                "rated_heating_capacity_w": _num(field_by_comment(htg, "Rated Heating Capacity") if htg else None),
                "rated_heating_cop": _num(field_by_comment(htg, "Rated Heating Coefficient of Performance") if htg else None),
                "rated_htg_airflow": _num(field_by_comment(htg, "Rated Air Flow Rate") if htg else None),
                "rated_htg_waterflow": _num(field_by_comment(htg, "Rated Water Flow Rate") if htg else None),
                "rated_cooling_capacity_w": _num(field_by_comment(clg, "Rated Total Cooling Capacity") if clg else None),
                "rated_cooling_cop": _num(field_by_comment(clg, "Rated Cooling Coefficient of Performance") if clg else None),
                "fan_max_flow": _num(field_by_comment(fan, "Maximum Flow Rate") if fan else None),
                "zone_floor_area_m2": _num(field_by_comment(zone, "Floor Area") if zone else None),
                "zone_volume_m3": _num(field_by_comment(zone, "Volume") if zone else None),
                "suggested_htg_w_3ton_per_hp": HP_COUNT_67[z] * W_PER_HP_3TON,
                "suggested_airflow_m3s_400cfm_per_ton": HP_COUNT_67[z] * 3.0 * CFM_PER_TON * CFM_TO_M3S,
            }
        )
    caps = [u["rated_heating_capacity_w"] for u in units]
    return {
        "schema": "vibe22.a04v2.w2a_plant_inventory.v1",
        "n_units": len(units),
        "n_heating_coil_objects": n_htg,
        "bas_six_hp_sum": sum(BAS_SIX_HP.values()),
        "hp_count_67_split_sum": sum(HP_COUNT_67.values()),
        "agg_v1_hp_sum": sum(float(v) for v in agg_hp.values()),
        "conflict": (
            "agg default_hp_counts sums to 79 because Library/Cafe/Gym are stacked on area "
            "counts and 2F is 12/12 vs BAS 11/10"
        ),
        "sizing_rule": (
            "Use 67-HP split. Do not silently use 79. 149430 W is 87900×1.70 A04 dial, "
            "identical on all nine coils, airflow autosize. Child IDFs may autosize both "
            "capacity and airflow together, or scale capacity+airflow by HP-count × 3 ton × 400 cfm/ton."
        ),
        "identical_hardcoded_heating_w": all(c == 149430.0 for c in caps),
        "w2a_low_airflow_note": (
            "Identical rated heating with autosized airflow is the physical cause of "
            "'air mass flow < 25% of rated' warnings. Recurring coil warning remains fail. "
            "No allowlist without this inventory note."
        ),
        "units": units,
    }


def main() -> int:
    idf = _APP / "models" / "eplus" / A04_IDF_NAME
    agg = json.loads((_APP / "contracts" / "eplus_nine_to_six_zone_agg_v1.json").read_text(encoding="utf-8"))
    src = idf.read_text(encoding="utf-8", errors="replace")
    inv = inventory_from_idf(src, agg)
    out = _APP / "docs" / "audits" / "figures" / "a04v2" / "w2a_plant_inventory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inv, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "n_units": inv["n_units"],
                "n_heating_coil_objects": inv["n_heating_coil_objects"],
                "sum67": inv["hp_count_67_split_sum"],
                "sum79": inv["agg_v1_hp_sum"],
                "identical_149430": inv["identical_hardcoded_heating_w"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
