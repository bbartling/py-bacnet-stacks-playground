"""AppTest / browser-caps validation for real BUILDING_100.zip upload path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_upload_building_weather_combos import _optional_real_package_dir

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def tadco_zip() -> Path:
    d = _optional_real_package_dir()
    if d is None:
        pytest.skip("No VIBE19_TEST_PACKAGE_DIR / local BUILDING_100.zip for optional real-zip tests")
    z = d / "BUILDING_100.zip"
    if not z.is_file():
        pytest.skip(f"TADCO zip not present: {z}")
    return z


@pytest.mark.optional_zip
def test_streamlit_browser_caps_match_uploader_path(tadco_zip: Path):
    """Exact call Streamlit makes: load_package_zip(bytes, caps=for_browser_upload)."""
    from app.package_io import effective_package_caps, load_package_zip, wipe_workdir

    caps = effective_package_caps(for_browser_upload=True)
    assert caps.max_entries >= 253
    result = load_package_zip(tadco_zip.read_bytes(), caps=caps)
    try:
        assert len(result.frames) == 48
        assert result.weather is not None
        assert result.manifest.building_id == "BUILDING_100"
    finally:
        wipe_workdir(result.workdir)


@pytest.mark.optional_zip
def test_streamlit_upload_loads_building_100_zip(
    tadco_zip: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Cloud-style widget upload (same package bytes a human uploads)."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    from tests.apptest_zip import load_zip_via_uploader

    monkeypatch.setenv("APP_MODE", "cloud")
    monkeypatch.setenv("VIBE19_BROWSER_AUTOLOAD", "0")

    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=300)
    at.run()
    assert not at.exception, f"AppTest exceptions: {list(at.exception)}"
    load_zip_via_uploader(at, tadco_zip)
    assert not at.exception, f"after upload: {list(at.exception)}"

    def _ss(key, default=None):
        try:
            return at.session_state[key]
        except Exception:
            return default

    frames = _ss("equipment_frames") or {}
    assert len(frames) >= 40, (
        f"upload failed; frames={len(frames)} "
        f"errors={[getattr(e, 'value', e) for e in at.sidebar.error]}"
    )
    assert (_ss("package_report") or {}).get("has_weather") or _ss("weather_frame") is not None


@pytest.mark.optional_zip
def test_streamlit_local_path_load_building_100(
    tadco_zip: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Local sidebar path load (human/agent alternative to file_uploader)."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    data = tmp_path / "hvac"
    data.mkdir()
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("HVAC_DATA_ROOT", str(data))
    monkeypatch.delenv("VIBE19_DOCKER", raising=False)
    monkeypatch.setattr("app.config.running_in_docker", lambda: False)

    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=300)
    at.run()
    assert not at.exception, f"startup: {list(at.exception)}"

    # Switch to Zip package if Folder is default
    radios = [r for r in at.sidebar.radio if "source" in (r.label or "").lower() or "Data" in (r.label or "")]
    for r in at.sidebar.radio:
        opts = list(r.options) if hasattr(r, "options") else []
        if "Zip package" in opts:
            r.set_value("Zip package")
            at.run()
            break

    path_inputs = [t for t in at.sidebar.text_input if "zip path" in (t.label or "").lower()]
    if not path_inputs:
        pytest.skip("Package zip path widget not shown")
    path_inputs[0].set_value(str(tadco_zip))
    at.run()

    load_btns = [b for b in at.sidebar.button if "load zip from path" in (b.label or "").lower()]
    assert load_btns, "Load zip from path button missing"
    load_btns[0].click().run()
    assert not at.exception, f"after load: {list(at.exception)}"

    def _ss(key, default=None):
        try:
            return at.session_state[key]
        except Exception:
            return default

    frames = _ss("equipment_frames") or {}
    assert len(frames) >= 40, (
        f"path load failed; frames={len(frames)}; "
        f"sidebar_errors={[getattr(e, 'value', e) for e in at.sidebar.error]}"
    )
