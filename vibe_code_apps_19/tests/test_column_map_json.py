"""Tests for Haystack-like + legacy JSON column map."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.column_map_json import (
    LLM_COLUMN_MAP_PROMPT,
    build_column_map_from_equipment_frames,
    build_llm_prompt_for_frames,
    column_map_to_role_map,
    haystack_point_to_cookbook,
    load_column_map_json,
    merge_column_map_into_role_map,
    natural_key,
    normalize_column_map,
    save_column_map_json,
    to_haystack_document,
    validate_column_map_against_frames,
)


def test_natural_key_orders_fc_numbers():
    ids = ["FC10", "FC2", "FC1", "ECON-2", "ECON-10"]
    assert sorted(ids, key=natural_key) == ["ECON-2", "ECON-10", "FC1", "FC2", "FC10"]


def test_haystack_point_aliases():
    assert haystack_point_to_cookbook("discharge-air-temp") == "sat"
    assert haystack_point_to_cookbook("zoneAirTemp") == "zone_t"
    assert haystack_point_to_cookbook("outside_air_temp") == "oa_t"
    assert haystack_point_to_cookbook("sat") == "sat"


def test_normalize_haystack_equip_points(tmp_path: Path):
    haystack = {
        "version": 1,
        "siteRef": "campus_a",
        "building": "HQ_NORTH",
        "generated_by": "llm",
        "equip": {
            "AHU_1": {
                "equipType": "ahu",
                "device": "AHU-1",
                "points": {
                    "discharge-air-temp": "discharge_air_temp_f",
                    "outside-air-temp": "outside_air_temp_f",
                },
            }
        },
    }
    norm = normalize_column_map(haystack)
    assert norm["building"] == "HQ_NORTH"
    assert norm["siteRef"] == "campus_a"
    assert norm["equipment"]["AHU_1"]["equipment_type"] == "AHU"
    assert norm["equipment"]["AHU_1"]["device"] == "AHU-1"
    assert norm["equipment"]["AHU_1"]["column_roles"]["sat"] == "discharge_air_temp_f"
    assert norm["equipment"]["AHU_1"]["column_roles"]["oa_t"] == "outside_air_temp_f"

    p = tmp_path / "m.json"
    save_column_map_json(p, haystack, haystack=True)
    loaded = load_column_map_json(p)
    assert loaded["equipment"]["AHU_1"]["column_roles"]["sat"] == "discharge_air_temp_f"
    exported = to_haystack_document(loaded)
    assert "equip" in exported
    assert exported["equip"]["AHU_1"]["points"]["discharge-air-temp"] == "discharge_air_temp_f"
    assert exported["equip"]["AHU_1"]["equipType"] == "ahu"


def test_normalize_legacy_still_works():
    flat = {"AHU_1": {"sat": "discharge_air_temp_f", "oa_t": "outside_air_temp_f"}}
    nested = normalize_column_map(
        {"building_id": "B1", "equipment": {"AHU_1": {"column_roles": flat["AHU_1"]}}}
    )
    assert column_map_to_role_map(normalize_column_map(flat))["AHU_1"]["sat"] == "discharge_air_temp_f"
    assert nested["equipment"]["AHU_1"]["column_roles"]["oa_t"] == "outside_air_temp_f"
    assert nested["building"] == "B1"


def test_merge_and_validate():
    df = pd.DataFrame({"discharge_air_temp_f": [55.0], "outside_air_temp_f": [40.0]})
    df.attrs["equipment_type"] = "AHU"
    frames = {"AHU_1": df}
    cmap = build_column_map_from_equipment_frames(frames, building_id="B1")
    assert "AHU_1" in cmap["equipment"]
    assert not validate_column_map_against_frames(cmap, frames)
    rm = merge_column_map_into_role_map({}, cmap)
    assert "sat" in rm["AHU_1"] or "oa_t" in rm["AHU_1"]


def test_bad_column_flagged():
    df = pd.DataFrame({"a": [1.0]})
    frames = {"AHU_1": df}
    cmap = {
        "equip": {"AHU_1": {"points": {"discharge-air-temp": "missing_col"}}},
    }
    issues = validate_column_map_against_frames(cmap, frames)
    assert any("missing_col" in i for i in issues)
    assert any("discharge-air-temp" in i for i in issues)


def test_build_llm_prompt_includes_multi_equipment():
    ahu = pd.DataFrame({"discharge_air_temp_f": [55.0]})
    ahu.attrs["equipment_type"] = "AHU"
    ahu.attrs["building_id"] = "SITE_A"
    ahu.attrs["columns_path"] = r"C:\Users\someone\data\SITE_A\AHU_1\columns.csv"
    vav = pd.DataFrame({"zone_temp_f": [72.0]})
    vav.attrs["equipment_type"] = "VAV"
    vav.attrs["building_id"] = "SITE_A"
    prompt = build_llm_prompt_for_frames({"AHU_1": ahu, "VAV_10": vav}, site_ref="campus")
    assert "Haystack" in LLM_COLUMN_MAP_PROMPT or "Haystack" in prompt
    assert "siteRef: campus" in prompt
    assert "building: SITE_A" in prompt
    assert "building_id: BUILDING_100" not in prompt
    assert "equip=AHU_1" in prompt
    assert "equipType=ahu" in prompt
    assert "equip=VAV_10" in prompt
    assert "equipType=vav" in prompt
    assert "discharge_air_temp_f" in prompt
    assert "zone_temp_f" in prompt
    assert "SITE_A/AHU_1/columns.csv" in prompt or "AHU_1/columns.csv" in prompt
    assert r"C:\Users\someone" not in prompt
    assert "discharge-air-temp" in prompt
    assert "Return ONLY valid JSON" in prompt


def test_build_llm_prompt_infers_building_from_attrs():
    df = pd.DataFrame({"sat_raw": [1.0]})
    df.attrs["building_id"] = "MY_CAMPUS_HQ"
    prompt = build_llm_prompt_for_frames({"AHU_9": df}, building_id="")
    assert "building: MY_CAMPUS_HQ" in prompt
