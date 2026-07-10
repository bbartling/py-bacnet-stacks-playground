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
    df = pd.DataFrame(columns=["outside_air_temp_f", "discharge_air_temp_f", "fan_cmd"])
    roles = suggest_roles(df)
    assert roles.get("oa_t") == "outside_air_temp_f"
    assert roles.get("sat") == "discharge_air_temp_f"


def test_enrich_role_map_from_equipment():
    rm: dict = {}
    enrich_role_map_from_equipment(rm, "AHU_1", None, ["outside_air_temp_f", "discharge_air_temp_f"])
    assert rm["AHU_1"]["oa_t"] == "outside_air_temp_f"
    assert rm["AHU_1"]["sat"] == "discharge_air_temp_f"


def test_streamlit_app_imports_enrich():
    """Regression: Streamlit must import enrich_role_map_from_equipment without ImportError."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("streamlit_app.py", default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    assert any("Open FDD Vibe Coder" in t.value for t in at.title)


def test_apply_and_validate(tmp_path: Path):
    idx = pd.date_range("2024-01-01", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame({"zone_t_raw": [70, 80, 72]}, index=idx)
    role_map = {"VAV_1": {"zone_t": "zone_t_raw"}}
    mapped = apply_role_map(df, "VAV_1", role_map)
    assert "zone_t" in mapped.columns
    missing = validate_required_roles("VAV_1", mapped, role_map, ["zone_t", "fan_cmd"])
    assert "fan_cmd" in missing


def test_load_role_map(tmp_path: Path):
    p = tmp_path / "roles.yaml"
    p.write_text("AHU_1:\n  sat: discharge_air_temp_f\n", encoding="utf-8")
    m = load_role_map(p)
    assert m["AHU_1"]["sat"] == "discharge_air_temp_f"
