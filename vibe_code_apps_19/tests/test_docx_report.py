"""Single Generic RCx DOCX contract tests (no python-docx)."""

from __future__ import annotations

import io
import zipfile

from app.docx_report import (
    GENERIC_RCX_DOCX,
    REPORTS_DIR,
    list_expected_report_files,
    load_generic_rcx_report,
    rcx_families,
)
from app.report_downloads import generic_rcx_bytes_for_tests


def test_exactly_one_committed_report_template():
    assert list_expected_report_files() == [GENERIC_RCX_DOCX]
    path = REPORTS_DIR / GENERIC_RCX_DOCX
    assert path.is_file()
    # No leftover multi-template assets
    extras = [
        p.name
        for p in REPORTS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".docx", ".zip"} and p.name != GENERIC_RCX_DOCX
    ]
    assert not extras, f"unexpected report assets: {extras}"


def test_generic_rcx_docx_is_valid_zip():
    blob = load_generic_rcx_report()
    assert blob[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        assert "word/document.xml" in zf.namelist()
    assert generic_rcx_bytes_for_tests() == blob


def test_overview_download_helper_and_streamlit_path():
    app_root = REPORTS_DIR.parents[1]
    src = (app_root / "streamlit_app.py").read_text(encoding="utf-8")
    assert "render_overview_rcx_download" in src
    assert "Download Generic RCx Report" in src or "overview_generic_rcx_docx" in src
    assert "Download FDD DOCX" not in src
    assert "render_central_template_pack_section" not in src
    assert "build_equipment_fdd_docx" not in src
    rcx_ui = (app_root / "app" / "ui_rcx_tab.py").read_text(encoding="utf-8")
    assert "render_rcx_family_downloads" not in rcx_ui


def test_rcx_families_still_include_chart_families():
    fams = rcx_families()
    assert "AHU / air" in fams
    assert "Heat pump" in fams
    assert "Weather" in fams
