"""AppTest / browser-caps validation for real BUILDING_100.zip upload path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TADCO_DIR = Path(
    r"C:\Users\ben\OneDrive\Desktop\testing\tadco_openfdd_sidecar"
    r"\workspace\imports\hvac_systems_CLEANED"
)
TADCO_ZIP = TADCO_DIR / "BUILDING_100.zip"


@pytest.fixture(scope="module")
def tadco_zip() -> Path:
    if not TADCO_ZIP.is_file():
        pytest.skip(f"TADCO zip not present: {TADCO_ZIP}")
    return TADCO_ZIP


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


def test_streamlit_bootstrap_loads_building_100_zip(
    tadco_zip: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Cloud-style auto-load (same package bytes a human uploads)."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    boot = {
        "schema_version": "openfdd_bootstrap_v1",
        "package_path": str(tadco_zip.resolve()),
        "auto_run_rules": False,
        "session_config": {
            "schema_version": "openfdd_session_v1",
            "unit_system": "imperial",
            "prefer_web_oat": True,
        },
    }
    boot_path = tmp_path / "streamlit_bootstrap.json"
    boot_path.write_text(json.dumps(boot), encoding="utf-8")
    monkeypatch.setenv("VIBE19_BOOTSTRAP", str(boot_path))
    monkeypatch.setenv("VIBE19_BOOTSTRAP_SKIP_RULES", "1")
    monkeypatch.setenv("APP_MODE", "cloud")

    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=300)
    at.run()
    assert not at.exception, f"AppTest exceptions: {list(at.exception)}"

    def _ss(key, default=None):
        try:
            return at.session_state[key]
        except Exception:
            return default

    frames = _ss("equipment_frames") or {}
    assert len(frames) >= 40, (
        f"bootstrap failed; frames={len(frames)} status={_ss('bootstrap_status')!r} "
        f"errors={[getattr(e, 'value', e) for e in at.sidebar.error]}"
    )
    assert (_ss("package_report") or {}).get("has_weather") or _ss("weather_frame") is not None


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
    monkeypatch.delenv("VIBE19_BOOTSTRAP", raising=False)
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
