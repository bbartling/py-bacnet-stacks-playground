"""Data-model tree + DOCX report smoke tests."""

from __future__ import annotations

import pandas as pd

from app.data_model_tree import build_data_model_tree
from app.docx_report import (
    build_analytics_docx,
    build_building_data_model_docx,
    build_equipment_fdd_docx,
    build_rcx_catalog_docx,
)
from app.rules import run_rule


def test_data_model_tree_and_docx(tmp_path):
    idx = pd.date_range("2024-06-01", periods=6, freq="5min", tz="UTC")
    ahu = pd.DataFrame(
        {
            "discharge_air_temp_f": [55.0] * 6,
            "sat_sp_f": [55.0] * 6,
            "clg_v": [0.0] * 6,
            "fan_s": [1.0] * 6,
        },
        index=idx,
    )
    ahu.attrs["equipment_type"] = "AHU"
    role_map = {
        "AHU_1": {
            "equipment_type": "AHU",
            "sat": "discharge_air_temp_f",
            "sat_sp": "sat_sp_f",
            "clg_valve_pct": "clg_v",
            "fan_status": "fan_s",
        }
    }
    tree = build_data_model_tree({"AHU_1": ahu}, role_map, building_id="B1")
    assert tree.equipment
    assert tree.equipment[0].equipment_id == "AHU_1"
    roles = {b.cookbook_role for b in tree.equipment[0].bindings}
    assert "sat" in roles
    # Haystack-like tag present for mapped SAT
    sat_bind = next(b for b in tree.equipment[0].bindings if b.cookbook_role == "sat")
    assert "discharge" in sat_bind.haystack_tag or "temp" in sat_bind.haystack_tag
    assert sat_bind.present_in_history is True

    flat = pd.DataFrame(tree.to_rows())
    assert not flat.empty
    assert {"equipment_id", "cookbook_role", "haystack_tag", "csv_column"} <= set(flat.columns)

    docx = build_building_data_model_docx(tree)
    assert docx[:2] == b"PK"  # zip/docx magic

    from app.role_map import apply_role_map

    mapped = apply_role_map(ahu, "AHU_1", role_map)
    results = [run_rule("VLV-1", mapped, {"confirm_min": 0}, 300.0)]
    eq_docx = build_equipment_fdd_docx(
        building_id="B1",
        equipment_id="AHU_1",
        equipment_type="AHU",
        results=results,
        role_map=role_map,
        mapped_df=mapped,
        plot_png_by_rule={},
    )
    assert eq_docx[:2] == b"PK"
    # Deflated XML — unzip and confirm rule content is present
    import zipfile
    from io import BytesIO

    with zipfile.ZipFile(BytesIO(eq_docx)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    assert "VLV-1" in xml
    assert "Cooling valve" in xml or "leakage" in xml.lower() or "Description:" in xml
    assert "PLACE PLOT HERE" in xml
    assert "Equation:" in xml
    # Simple template — not a full card dump
    assert "confirm_min" not in xml
    assert "Operational gate" not in xml
    assert "PLACE PLOT HERE" in xml

    analytics = build_analytics_docx(
        building_id="B1",
        motor_weekly=pd.DataFrame(),
        cool_bins=pd.DataFrame(),
        rcx_coverage=pd.DataFrame({"preset_id": ["zone_temps"], "row_count": [0]}),
        tree=tree,
    )
    assert analytics[:2] == b"PK"

    rcx_docx = build_rcx_catalog_docx(
        building_id="B1",
        frames={"AHU_1": ahu},
        role_map=role_map,
        weather=None,
        results=results,
        params={},
        zone_lo_f=70.0,
        zone_hi_f=75.0,
    )
    assert rcx_docx[:2] == b"PK"
    with zipfile.ZipFile(BytesIO(rcx_docx)) as zf:
        rxml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    assert "RCx catalog" in rxml or "SV-SPIKE" in rxml or "VLV-1" in rxml
    assert "PLACE RCX PLOT HERE" in rxml or "ahu_sat_reset_scatter" in rxml or "duct_static_box" in rxml
