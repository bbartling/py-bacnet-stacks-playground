"""Cloud mode must not restore another user's last upload."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_cloud_apptest_ignores_leftover_browser_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("APP_MODE", "cloud")
    monkeypatch.setenv("VIBE19_BROWSER_AUTOLOAD", "1")
    ptr = tmp_path / ".last_browser_session.json"
    fake_wd = tmp_path / "stolen_wd"
    fake_b = fake_wd / "STOLEN"
    fake_b.mkdir(parents=True)
    (fake_b / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "openfdd_package_v1",
                "building_id": "STOLEN",
                "grid_minutes": 5,
            }
        ),
        encoding="utf-8",
    )
    ptr.write_text(
        json.dumps(
            {
                "schema_version": "openfdd_browser_session_v1",
                "workdir": str(fake_wd),
                "building_root": str(fake_b),
                "building_id": "STOLEN",
                "source": "zip:STOLEN",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VIBE19_BROWSER_SESSION_PATH", str(ptr))
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=120)
    at.run()
    assert not at.exception, f"AppTest exceptions: {list(at.exception)}"

    def _ss(key, default=None):
        try:
            return at.session_state[key]
        except Exception:
            return default

    frames = _ss("equipment_frames") or {}
    assert frames == {}
    assert _ss("building_id") in ("", None)


def test_cloud_apptest_starts_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("APP_MODE", "cloud")
    monkeypatch.setenv("VIBE19_BROWSER_AUTOLOAD", "1")
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=120)
    at.run()
    assert not at.exception, f"AppTest exceptions: {list(at.exception)}"

    def _ss(key, default=None):
        try:
            return at.session_state[key]
        except Exception:
            return default

    assert (_ss("equipment_frames") or {}) == {}
    assert not _ss("restore_status")
