"""Drive the same Streamlit sidebar zip picker a human uses (file_uploader + Load zip)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TADCO_DIR = Path(
    r"C:\Users\ben\OneDrive\Desktop\testing\tadco_openfdd_sidecar"
    r"\workspace\imports\hvac_systems_CLEANED"
)
BUILDING_ZIP = TADCO_DIR / "BUILDING_100.zip"
WEATHER_ZIP = TADCO_DIR / "weather.zip"


@pytest.fixture
def tadco_building_zip() -> Path:
    if not BUILDING_ZIP.is_file():
        pytest.skip(f"missing {BUILDING_ZIP}")
    return BUILDING_ZIP


@pytest.fixture
def tadco_weather_zip() -> Path:
    if not WEATHER_ZIP.is_file():
        pytest.skip(f"missing {WEATHER_ZIP}")
    return WEATHER_ZIP


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


def test_ui_picker_loads_building_100_zip(tadco_building_zip: Path, monkeypatch: pytest.MonkeyPatch):
    """Same path as human: Data source Zip → Building package zip(s) → Load zip(s)."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("APP_MODE", "cloud")
    monkeypatch.delenv("VIBE19_BOOTSTRAP", raising=False)

    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=300)
    at.run()
    assert not at.exception, f"startup: {list(at.exception)}"

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
    # Caps caption on new builds must not still say the legacy 200-entry limit
    caps_text = " ".join(str(getattr(c, "value", c)) for c in at.sidebar.caption)
    assert "2000" in caps_text, f"expected zip-item limit 2000 in captions, got: {caps_text[:500]}"


def test_ui_picker_rejects_weather_only_zip(tadco_weather_zip: Path, monkeypatch: pytest.MonkeyPatch):
    """weather.zip alone must fail with a human message (not a raw Pydantic dump)."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("APP_MODE", "cloud")
    monkeypatch.delenv("VIBE19_BOOTSTRAP", raising=False)

    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=180)
    at.run()
    assert not at.exception

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
