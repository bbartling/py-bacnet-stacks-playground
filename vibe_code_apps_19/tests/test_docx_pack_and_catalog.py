"""Catalog summary parity + simplified Plots FDD DOCX template."""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from app.charts import bas_vs_web_oat_histogram
from app.docx_report import PLACE_PLOT_HERE, build_equipment_fdd_docx
from app.rule_card import build_rule_card
from app.rules.cookbook_catalog import RULES, RULES_BY_ID
from app.rcx_plots import pump_mode_summary_bundle
from app.analytics import plant_gated_summary_tables


def test_every_rule_has_summary():
    assert RULES
    for r in RULES:
        assert (r.summary or "").strip(), f"{r.id} missing summary"
        assert r.summary != r.equation or len(r.equation) < 200


def test_rule_card_uses_summary_not_equation_as_description():
    rule = RULES_BY_ID["VAV-AHU-LEAVE"]
    idx = pd.date_range("2024-06-01", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame(index=idx)
    df.attrs["equipment_id"] = "VAV_1"
    card = build_rule_card(
        equipment_id="VAV_1",
        rule=rule,
        result=None,
        role_map={},
        mapped_df=df,
    )
    assert card.description == rule.summary
    assert card.equation == rule.equation


def test_equipment_fdd_docx_is_simple_template():
    idx = pd.date_range("2024-06-01", periods=6, freq="5min", tz="UTC")
    ahu = pd.DataFrame({"sat": [55.0] * 6, "fan_status": [1] * 6}, index=idx)
    ahu.attrs["equipment_type"] = "AHU"
    role_map = {"AHU_1": {"equipment_type": "AHU", "sat": "sat", "fan_status": "fan_status"}}
    blob = build_equipment_fdd_docx(
        building_id="B1",
        equipment_id="AHU_1",
        equipment_type="AHU",
        results=[],
        role_map=role_map,
        mapped_df=ahu,
        plot_png_by_rule={},
    )
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "KEY FINDINGS" in xml
    assert "Description:" in xml
    assert "Equation:" in xml
    assert "PLACE PLOT HERE" in xml
    # Must stay dumb — no busy analytics / mapping dumps
    assert "Analytics" not in xml
    assert "Motor weekly" not in xml
    assert "Sliders" not in xml
    assert "Haystack" not in xml


def test_bas_vs_web_oat_histogram():
    idx = pd.date_range("2024-06-01", periods=20, freq="5min", tz="UTC")
    df = pd.DataFrame({"oa_t": [70.0 + i * 0.1 for i in range(20)], "wx_oa_t": [68.0] * 20}, index=idx)
    fig = bas_vs_web_oat_histogram({"AHU_1": df}, {"AHU_1": {"oa_t": "oa_t", "wx_oa_t": "wx_oa_t"}})
    assert fig is not None


def test_pump_mode_summary_bundle():
    idx = pd.date_range("2024-06-01", periods=10, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "chw_supply_t": [44.0] * 10,
            "chw_pump_status": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
        },
        index=idx,
    )
    df.attrs["equipment_type"] = "CHILLER"
    tables, caption = pump_mode_summary_bundle(
        {"CHILLER_1": df},
        {
            "CHILLER_1": {
                "equipment_type": "CHILLER",
                "chw_supply_t": "chw_supply_t",
                "chw_pump_status": "chw_pump_status",
            }
        },
        role="chw_supply_t",
        equipment_types=("CHILLER", "CHW_PLANT"),
    )
    assert "all" in tables and "on" in tables and "off" in tables
    assert not tables["all"].empty
    assert not tables["on"].empty
    assert not tables["off"].empty
    assert "pump" in caption.lower() or "chw_pump" in caption.lower()


def test_plant_gated_summary_tables_smoke():
    idx = pd.date_range("2024-06-01", periods=8, freq="5min", tz="UTC")
    ahu = pd.DataFrame({"sat": [55.0] * 8, "fan_status": [1] * 8}, index=idx)
    ahu.attrs["equipment_type"] = "AHU"
    fan, pump, fc, pc = plant_gated_summary_tables(
        {"AHU_1": ahu},
        {"AHU_1": {"equipment_type": "AHU", "sat": "sat", "fan_status": "fan_status"}},
    )
    assert "all" in fan
    assert fc
    assert pc
