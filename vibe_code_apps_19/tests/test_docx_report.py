"""Prebuilt DOCX / template-pack smoke tests (no python-docx)."""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from app.data_model_tree import build_data_model_tree
from app.docx_report import (
    PORTFOLIO_EXECUTIVE_DOCX,
    REPORTS_DIR,
    TEMPLATE_PACK_ZIP,
    UNIVERSAL_FINDING_DOCX,
    build_analytics_docx,
    build_building_data_model_docx,
    build_equipment_fdd_docx,
    build_portfolio_executive_docx,
    build_rcx_catalog_docx,
    build_rcx_family_docx,
    build_universal_finding_docx,
    fdd_report_filename,
    list_expected_report_files,
    list_template_pack_members,
    load_template_pack_zip_bytes,
    rcx_families,
    rcx_family_report_filename,
)


def _xml(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        return zf.read("word/document.xml").decode("utf-8", errors="ignore")


def test_all_expected_report_files_exist():
    assert REPORTS_DIR.is_dir()
    missing = [n for n in list_expected_report_files() if not (REPORTS_DIR / n).is_file()]
    assert not missing, f"missing reports: {missing}"


def test_template_pack_zip_contains_expected_members():
    blob = load_template_pack_zip_bytes()
    assert blob[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = set(zf.namelist())
    for member in list_template_pack_members():
        assert member in names, member
    assert "rcx_heat_pump.docx" in names
    assert "rcx_weather.docx" in names
    assert UNIVERSAL_FINDING_DOCX in names
    assert PORTFOLIO_EXECUTIVE_DOCX in names


def test_rcx_families_include_heat_pump_and_weather():
    fams = rcx_families()
    assert "AHU / air" in fams
    assert "Heat pump" in fams
    assert "Weather" in fams
    assert rcx_family_report_filename("Heat pump") == "rcx_heat_pump.docx"
    assert rcx_family_report_filename("Weather") == "rcx_weather.docx"


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

    docx = build_building_data_model_docx(tree)
    assert docx[:2] == b"PK"

    eq_docx = build_equipment_fdd_docx(equipment_type="AHU")
    assert eq_docx[:2] == b"PK"

    assert build_analytics_docx()[:2] == b"PK"
    assert build_rcx_catalog_docx()[:2] == b"PK"
    fam = build_rcx_family_docx("AHU / air")
    assert fam[:2] == b"PK"
    assert fam == (REPORTS_DIR / "rcx_ahu_air.docx").read_bytes()
    assert "AHU" in _xml(fam) or "ahu" in _xml(fam).lower() or "RCx" in _xml(fam)

    assert build_universal_finding_docx()[:2] == b"PK"
    assert build_portfolio_executive_docx()[:2] == b"PK"


def test_fdd_and_rcx_filename_maps():
    assert fdd_report_filename("AHU") == "fdd_ahu.docx"
    assert fdd_report_filename("CHW_PLANT") == "fdd_chiller.docx"
    assert fdd_report_filename("nope") == "fdd_generic.docx"
    assert rcx_family_report_filename("Zones / VAV") == "rcx_zones_vav.docx"
    assert rcx_family_report_filename("Metering") == "rcx_metering.docx"
    assert TEMPLATE_PACK_ZIP.endswith(".zip")
