"""Tests for role_map."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.role_map import (
    apply_role_map,
    enrich_role_map_from_equipment,
    load_role_map,
    suggest_roles,
    validate_required_roles,
)


def test_suggest_roles():
    df = pd.DataFrame(columns=["outside_air_temp_f", "discharge_air_temp_f", "fan-cmd"])
    roles = suggest_roles(df)
    assert roles.get("outside-air-temp") == "outside_air_temp_f"
    assert roles.get("discharge-air-temp") == "discharge_air_temp_f"


def test_suggest_roles_prefers_supply_fan():
    df = pd.DataFrame(
        columns=[
            "return_fan_speed_pct",
            "return_fan_status",
            "supply_fan_speed_pct",
            "supply_fan_status",
        ]
    )
    roles = suggest_roles(df)
    assert roles["fan-cmd"] == "supply_fan_speed_pct"
    assert roles["fan-status"] == "supply_fan_status"


def test_enrich_maps_chiller_plant_points():
    rm: dict = {}
    cols = [
        "chiller_2_command",
        "chiller_2_amps_a",
        "chws_t_f",
        "chwr_t_f",
        "meter_power_sum_kw",
        "hwp1_c",
        "hwp1_s",
    ]
    enrich_role_map_from_equipment(rm, "CHILLER_2", None, cols)
    assert rm["CHILLER_2"]["chiller-status"] == "chiller_2_command"
    assert rm["CHILLER_2"]["chilled-water-supply-temp"] == "chws_t_f"
    assert rm["CHILLER_2"]["hw-pump-cmd"] == "hwp1_c"
    assert rm["CHILLER_2"]["pump-status"] == "hwp1_s"


def test_enrich_role_map_from_equipment():
    rm: dict = {}
    enrich_role_map_from_equipment(rm, "AHU_1", None, ["outside_air_temp_f", "discharge_air_temp_f"])
    assert rm["AHU_1"]["outside-air-temp"] == "outside_air_temp_f"
    assert rm["AHU_1"]["discharge-air-temp"] == "discharge_air_temp_f"


def test_streamlit_app_imports_enrich():
    """Regression: Streamlit must import enrich_role_map_from_equipment without ImportError."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("streamlit_app.py", default_timeout=90)
    at.run()
    assert not at.exception, at.exception
    assert any("OpenFDD Vibe 19" in t.value for t in at.title)


def test_apply_and_validate(tmp_path: Path):
    idx = pd.date_range("2024-01-01", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame({"zone_t_raw": [70, 80, 72]}, index=idx)
    role_map = {"VAV_1": {"zone-air-temp": "zone_t_raw"}}
    mapped = apply_role_map(df, "VAV_1", role_map)
    assert "zone-air-temp" in mapped.columns
    missing = validate_required_roles("VAV_1", mapped, role_map, ["zone-air-temp", "fan-cmd"])
    assert "fan-cmd" in missing


def test_load_role_map(tmp_path: Path):
    p = tmp_path / "roles.yaml"
    p.write_text("AHU_1:\n  discharge-air-temp: discharge_air_temp_f\n", encoding="utf-8")
    m = load_role_map(p)
    assert m["AHU_1"]["discharge-air-temp"] == "discharge_air_temp_f"
