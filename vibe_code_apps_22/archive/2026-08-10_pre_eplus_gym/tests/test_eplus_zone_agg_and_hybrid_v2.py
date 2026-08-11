"""Tests for nine→six aggregation + hybrid_dsm_96_v2 contract shape."""
from __future__ import annotations

import json
from pathlib import Path

from eplus_native.zone_agg import aggregate_zone_temps_row, load_agg_contract

_ROOT = Path(__file__).resolve().parents[1]


def test_agg_library_cafe_gym_into_bas():
    cal = load_agg_contract()
    temps = {z: 70.0 for z in cal["eplus_zones_nine"]}
    temps["1F_Library_IMC"] = 60.0
    temps["1F_Area_A"] = 70.0
    out = aggregate_zone_temps_row(temps, cal, mode="hp_count")
    # library pulls 1F_A down below 70
    assert out["zone_temp_1F_A_f"] < 70.0
    assert out["zone_temp_1F_B_f"] == 70.0


def test_hybrid_v2_immutable_sibling_of_v1():
    v1 = json.loads((_ROOT / "contracts" / "hybrid_dsm_96_v1.json").read_text(encoding="utf-8"))
    v2 = json.loads((_ROOT / "contracts" / "hybrid_dsm_96_v2.json").read_text(encoding="utf-8"))
    assert v1["contract_version"] == "hybrid_dsm_96_v1"
    assert v2["contract_version"] == "hybrid_dsm_96_v2"
    assert v2["steps"] == 96
    assert v2["architecture"]["never_concat_real_and_eplus_tables"] is True
    assert v2["pytorch_causal_sequence_requirements"]["tensor_layout"] == "[B,T,F]"
    assert v2["dsm_default"].startswith("NO-GO")


def test_provisional_plant_card_honesty():
    from eplus_native.provisional_plant import plant_design_card

    card = plant_design_card()
    assert "NOT ZoneHVAC:WaterToAirHeatPump" in card["honesty"]
    assert card["topology_provisional"]["no_supplemental_electric_heat_without_evidence"] is True
