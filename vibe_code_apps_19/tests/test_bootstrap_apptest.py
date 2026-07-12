"""AppTest: bootstrap zip load must survive full UI render (no NameError on caps)."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _tiny_zip(path: Path) -> None:
    hist = "timestamp_utc,fan_status,oa_t,sat\n"
    for i in range(6):
        hist += f"2024-06-01T12:{i:02d}:00Z,1,70,55\n"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "schema_version": "openfdd_package_v1",
                    "building_id": "BOOT_B1",
                    "grid_minutes": 5,
                    "timezone": "UTC",
                }
            ),
        )
        zf.writestr(
            "session_config.json",
            json.dumps(
                {
                    "schema_version": "openfdd_session_v1",
                    "unit_system": "imperial",
                    "prefer_web_oat": False,
                    "role_map": {
                        "AHU_1": {
                            "fan_status": "fan_status",
                            "oa_t": "oa_t",
                            "sat": "sat",
                        }
                    },
                }
            ),
        )
        zf.writestr("AHU_1/history_wide.csv", hist)
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
        zf.writestr(
            "AHU_1/columns.csv",
            "col,point_role\nfan_status,fan_status\noa_t,oa_t\nsat,sat\n",
        )


def test_bootstrap_zip_full_ui_render(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    zpath = tmp_path / "boot_pkg.zip"
    _tiny_zip(zpath)
    boot = {
        "schema_version": "openfdd_bootstrap_v1",
        "package_path": str(zpath.resolve()),
        "auto_run_rules": True,
        "session_config": {
            "schema_version": "openfdd_session_v1",
            "unit_system": "imperial",
        },
    }
    boot_path = tmp_path / "streamlit_bootstrap.json"
    boot_path.write_text(json.dumps(boot), encoding="utf-8")
    monkeypatch.setenv("VIBE19_BOOTSTRAP", str(boot_path))
    monkeypatch.setenv("VIBE19_BOOTSTRAP_SKIP_RULES", "0")
    monkeypatch.setenv("APP_MODE", "cloud")

    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"AppTest exceptions: {list(at.exception)}"

    def _ss(key, default=None):
        try:
            return at.session_state[key]
        except Exception:
            return default

    frames = _ss("equipment_frames") or {}
    assert "AHU_1" in frames, f"bootstrap frames missing; status={_ss('bootstrap_status')!r}"
    results = _ss("batch_results") or []
    assert len(results) >= 50, f"expected >=50 rule results, got {len(results)}; status={_ss('bootstrap_status')!r}"
