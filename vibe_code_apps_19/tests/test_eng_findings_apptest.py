"""AppTest: Run Rules Engineering Findings panel renders without Streamlit errors."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _pkg_zip(path: Path, *, with_sidecar: bool = False) -> None:
    hist = "timestamp_utc,fan_status,oa_t,sat\n"
    for i in range(12):
        hist += f"2024-06-01T12:{i:02d}:00Z,1,70,55\n"
    session = {
        "schema_version": "openfdd_session_v1",
        "unit_system": "imperial",
        "prefer_web_oat": False,
        "role_map": {
            "AHU_1": {
                "supply-fan-status": "fan_status",
                "outside-air-temp": "oa_t",
                "discharge-air-temp": "sat",
            }
        },
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "schema_version": "openfdd_package_v1",
                    "building_id": "UI_B1",
                    "grid_minutes": 5,
                    "timezone": "UTC",
                }
            ),
        )
        zf.writestr("session_config.json", json.dumps(session))
        zf.writestr("AHU_1/history_wide.csv", hist)
        if with_sidecar:
            zf.writestr(
                "AHU_1/column_map.json",
                json.dumps(
                    {
                        "equipType": "ahu",
                        "points": {
                            "fan-status": "fan_status",
                            "outside-air-temp": "oa_t",
                            "discharge-air-temp": "sat",
                        },
                    }
                ),
            )


def test_run_rules_eng_findings_panel_no_streamlit_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    zpath = tmp_path / "ui_pkg.zip"
    _pkg_zip(zpath, with_sidecar=True)
    monkeypatch.setenv("APP_MODE", "cloud")
    monkeypatch.setenv("VIBE19_BROWSER_AUTOLOAD", "0")
    monkeypatch.chdir(ROOT)

    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=120)
    at.run()
    from tests.apptest_zip import load_zip_via_uploader

    load_zip_via_uploader(at, zpath)
    assert not at.exception, f"Streamlit exception on load: {at.exception}"

    # Switch to Run Rules if section radio exists
    for radio in at.radio:
        labels = list(getattr(radio, "options", []) or [])
        if "Run Rules" in labels:
            radio.set_value("Run Rules")
            at.run()
            break
    assert not at.exception, f"Streamlit exception on Run Rules: {at.exception}"

    # Generate Engineering Findings if the button is present
    clicked = False
    for btn in at.button:
        label = str(getattr(btn, "label", "") or "")
        if "Engineering Findings" in label or "Generate FDD" in label:
            btn.click()
            at.run(timeout=180)
            clicked = True
            break
    assert not at.exception, f"Streamlit exception on generate: {at.exception}"
    if clicked:
        # Soft assert success message / download availability — no Traceback text
        page = " ".join(str(x) for x in at.markdown) + " ".join(str(x) for x in at.success)
        assert "Traceback" not in page
