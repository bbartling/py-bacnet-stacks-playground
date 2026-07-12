"""Prebuilt DOCX report smoke tests (no python-docx)."""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from app.data_model_tree import build_data_model_tree
from app.docx_report import (
    REPORTS_DIR,
    build_analytics_docx,
    build_building_data_model_docx,
    build_equipment_fdd_docx,
    build_rcx_catalog_docx,
    build_rcx_family_docx,
    fdd_report_filename,
    list_expected_report_files,
    rcx_family_report_filename,
)


def _xml(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        return zf.read("word/document.xml").decode("utf-8", errors="ignore")


def test_all_expected_report_files_exist():
    assert REPORTS_DIR.is_dir()
    missing = [n for n in list_expected_report_files() if not (REPORTS_DIR / n).is_file()]
    assert not missing, f"missing reports: {missing}"


def test_data_model_tree_and_static_docx(tmp_path):
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

    docx = build_building_data_model_docx(tree)
    assert docx[:2] == b"PK"
    assert "data model" in _xml(docx).lower() or "KEY FINDINGS" in _xml(docx)

    eq_docx = build_equipment_fdd_docx(equipment_type="AHU")
    assert eq_docx[:2] == b"PK"
    xml = _xml(eq_docx)
    assert "KEY FINDINGS" in xml
    assert "PLACE PLOT HERE" in xml
    assert "Description:" in xml
    assert "Equation:" in xml

    analytics = build_analytics_docx()
    assert analytics[:2] == b"PK"

    rcx_docx = build_rcx_catalog_docx()
    assert rcx_docx[:2] == b"PK"
    assert "PLACE RCX PLOT HERE" in _xml(rcx_docx)

    fam = build_rcx_family_docx("AHU / air")
    assert fam[:2] == b"PK"
    assert fam == (REPORTS_DIR / "rcx_ahu_air.docx").read_bytes()


def test_fdd_and_rcx_filename_maps():
    assert fdd_report_filename("AHU") == "fdd_ahu.docx"
    assert fdd_report_filename("CHW_PLANT") == "fdd_chiller.docx"
    assert fdd_report_filename("nope") == "fdd_generic.docx"
    assert rcx_family_report_filename("Zones / VAV") == "rcx_zones_vav.docx"
    assert rcx_family_report_filename("Metering") == "rcx_metering.docx"
