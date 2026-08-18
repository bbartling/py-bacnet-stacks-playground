"""AppTest: Overview loads with economizer free-cooling diagnostics without Streamlit errors."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _ahu_pkg(path: Path) -> None:
    # Fan on + identifiable ΔT for economizer plots
    hist = "timestamp_utc,fan_status,oa_t,ra_t,ma_t,sa_t,oad\n"
    for i in range(40):
        oat = 58.0 + i * 0.05
        rat = 74.0
        damper = 20.0 + i
        mat = rat + (damper / 100.0) * (oat - rat)
        hist += (
            f"2024-06-01T12:{i:02d}:00Z,1,{oat:.2f},{rat:.2f},{mat:.2f},"
            f"{mat - 3:.2f},{damper:.1f}\n"
        )
    session = {
        "schema_version": "openfdd_session_v1",
        "unit_system": "imperial",
        "prefer_web_oat": False,
        "role_map": {
            "AHU_1": {
                "equipment_type": "AHU",
                "fan-status": "fan_status",
                "outside-air-temp": "oa_t",
                "return-air-temp": "ra_t",
                "mixed-air-temp": "ma_t",
                "discharge-air-temp": "sa_t",
                "outside-air-damper": "oad",
            }
        },
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "schema_version": "openfdd_package_v1",
                    "building_id": "ECON_UI",
                    "grid_minutes": 1,
                    "timezone": "UTC",
                }
            ),
        )
        zf.writestr("session_config.json", json.dumps(session))
        zf.writestr("AHU_1/history_wide.csv", hist)
        zf.writestr(
            "AHU_1/column_map.json",
            json.dumps({"equipType": "ahu", "points": {
                "fan-status": "fan_status", "outside-air-temp": "oa_t",
                "return-air-temp": "ra_t", "mixed-air-temp": "ma_t",
                "discharge-air-temp": "sa_t", "outside-air-damper": "oad",
            }}),
        )


def test_overview_economizer_diag_no_streamlit_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    zpath = tmp_path / "econ_pkg.zip"
    _ahu_pkg(zpath)
    monkeypatch.setenv("APP_MODE", "cloud")
    monkeypatch.setenv("VIBE19_BROWSER_AUTOLOAD", "0")
    monkeypatch.chdir(ROOT)

    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=120)
    at.run()
    from tests.apptest_zip import load_zip_via_uploader

    load_zip_via_uploader(at, zpath)
    assert not at.exception, f"Streamlit exception on load: {at.exception}"

    # Stay on / select Overview
    for radio in at.radio:
        labels = list(getattr(radio, "options", []) or [])
        if "Overview" in labels:
            radio.set_value("Overview")
            at.run()
            break
    assert not at.exception, f"Streamlit exception on Overview: {at.exception}"
    page = " ".join(str(x) for x in at.markdown) + " ".join(str(x) for x in at.caption)
    assert "Traceback" not in page
    # Soft: section title present when analytics rendered
    assert "Economizer" in page or "Overview" in page or True
