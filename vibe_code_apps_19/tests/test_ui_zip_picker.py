"""Drive the same Streamlit sidebar zip picker a human uses (file_uploader + Load zip).

Real BUILDING_100.zip / weather.zip are optional test fixtures only (see
``VIBE19_TEST_PACKAGE_DIR``); app code never hard-codes those paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_upload_building_weather_combos import (
    _building_zip_with_nested_weather,
    _optional_real_package_dir,
    _weather_only_zip,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tadco_building_zip() -> Path:
    d = _optional_real_package_dir()
    if d is None:
        pytest.skip("optional real BUILDING_100.zip not available")
    z = d / "BUILDING_100.zip"
    if not z.is_file():
        pytest.skip(f"missing {z}")
    return z


@pytest.fixture
def tadco_weather_zip() -> Path:
    d = _optional_real_package_dir()
    if d is None:
        pytest.skip("optional real weather.zip not available")
    z = d / "weather.zip"
    if not z.is_file():
        pytest.skip(f"missing {z}")
    return z


def _ss(at, key, default=None):
    try:
        return at.session_state[key]
    except Exception:
        return default


def _building_zip_uploader(at):
    for fu in at.sidebar.file_uploader:
        if (fu.label or "") == "Building package zip(s)":
            return fu
    raise AssertionError(
        "Building package zip(s) uploader missing — expected APP_MODE=cloud Zip package UI"
    )


def _load_zip_button(at):
    for b in at.sidebar.button:
        if (b.label or "") == "Load zip(s)":
            return b
    raise AssertionError("Load zip(s) button missing")


def _cloud_app(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("APP_MODE", "cloud")
    monkeypatch.setenv("VIBE19_BROWSER_AUTOLOAD", "0")
    monkeypatch.delenv("VIBE19_BOOTSTRAP", raising=False)
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=300)
    at.run()
    assert not at.exception, f"startup: {list(at.exception)}"
    return at


def test_ui_picker_loads_synthetic_building_zip(monkeypatch: pytest.MonkeyPatch):
    at = _cloud_app(monkeypatch)
    data = _building_zip_with_nested_weather()
    _building_zip_uploader(at).set_value(("SITE_A.zip", data, "application/zip"))
    at.run()
    _load_zip_button(at).click().run()
    assert not at.exception, f"after Load zip(s): {list(at.exception)}"
    frames = _ss(at, "equipment_frames") or {}
    assert "AHU_1" in frames
    assert _ss(at, "weather_frame") is not None or (_ss(at, "package_report") or {}).get("has_weather")


def test_ui_picker_loads_building_100_zip(tadco_building_zip: Path, monkeypatch: pytest.MonkeyPatch):
    """Same path as human: Data source Zip → Building package zip(s) → Load zip(s)."""
    at = _cloud_app(monkeypatch)
    data = tadco_building_zip.read_bytes()
    _building_zip_uploader(at).set_value(
        (tadco_building_zip.name, data, "application/zip")
    )
    at.run()
    assert not at.exception, f"after select file: {list(at.exception)}"

    _load_zip_button(at).click().run()
    assert not at.exception, f"after Load zip(s): {list(at.exception)}"

    frames = _ss(at, "equipment_frames") or {}
    assert len(frames) >= 40, (
        f"UI picker failed to load equipment; got {len(frames)}; "
        f"sidebar_errors={[getattr(e, 'value', e) for e in at.sidebar.error]}"
    )
    report = _ss(at, "package_report") or {}
    assert report.get("building_id") == "BUILDING_100" or _ss(at, "building_id") == "BUILDING_100"
    assert report.get("has_weather") or _ss(at, "weather_frame") is not None
    caps_text = " ".join(str(getattr(c, "value", c)) for c in at.sidebar.caption)
    assert "2000" in caps_text, f"expected zip-item limit 2000 in captions, got: {caps_text[:500]}"


def test_ui_picker_rejects_weather_only_zip(tadco_weather_zip: Path, monkeypatch: pytest.MonkeyPatch):
    at = _cloud_app(monkeypatch)
    data = tadco_weather_zip.read_bytes()
    _building_zip_uploader(at).set_value((tadco_weather_zip.name, data, "application/zip"))
    at.run()
    _load_zip_button(at).click().run()
    assert not at.exception, f"uncaught: {list(at.exception)}"

    errors = [str(getattr(e, "value", e)) for e in at.sidebar.error]
    assert errors, "expected sidebar error for weather-only zip"
    blob = " ".join(errors).lower()
    assert "weather" in blob
    assert "building" in blob
    assert not (_ss(at, "equipment_frames") or {}), "weather-only zip must not load equipment"


def test_ui_picker_building_plus_weather(
    tadco_building_zip: Path, tadco_weather_zip: Path, monkeypatch: pytest.MonkeyPatch
):
    """Human selects both zips — must still load the building (weather sidecar ignored/merged)."""
    at = _cloud_app(monkeypatch)
    _building_zip_uploader(at).set_value(
        [
            (tadco_building_zip.name, tadco_building_zip.read_bytes(), "application/zip"),
            (tadco_weather_zip.name, tadco_weather_zip.read_bytes(), "application/zip"),
        ]
    )
    at.run()
    _load_zip_button(at).click().run()
    assert not at.exception, f"after Load zip(s): {list(at.exception)}"
    frames = _ss(at, "equipment_frames") or {}
    assert len(frames) >= 40, (
        f"both-zip upload failed; frames={len(frames)}; "
        f"errors={[getattr(e, 'value', e) for e in at.sidebar.error]}"
    )


def test_ui_picker_synthetic_building_plus_weather(monkeypatch: pytest.MonkeyPatch):
    at = _cloud_app(monkeypatch)
    _building_zip_uploader(at).set_value(
        [
            ("SITE_A.zip", _building_zip_with_nested_weather(), "application/zip"),
            ("weather.zip", _weather_only_zip(), "application/zip"),
        ]
    )
    at.run()
    _load_zip_button(at).click().run()
    assert not at.exception
    frames = _ss(at, "equipment_frames") or {}
    assert "AHU_1" in frames, (
        f"synthetic both-zip failed; errors={[getattr(e, 'value', e) for e in at.sidebar.error]}"
    )
