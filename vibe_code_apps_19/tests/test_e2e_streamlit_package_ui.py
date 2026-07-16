"""Pytest wrapper for scripts/e2e_streamlit_package_ui.py (Streamlit AppTest E2E)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "e2e_streamlit_package_ui.py"


def _load_e2e():
    spec = importlib.util.spec_from_file_location("e2e_streamlit_package_ui", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_e2e_synthetic_upload_run_results(monkeypatch: pytest.MonkeyPatch):
    """CI-stable: synthetic zips cover building / weather reject / both / dup + Run + Results."""
    e2e = _load_e2e()
    summary = e2e.run_upload_variants(prefer_real=False, monkeypatch=monkeypatch)
    assert summary["real"] is False
    assert "building_alone" in summary["variants"]
    assert "weather_alone_reject" in summary["variants"]
    assert "building_plus_weather" in summary["variants"]
    assert "duplicate_building" in summary["variants"] or "duplicate_building_warned" in summary["variants"]
    e2e.run_rules_and_results(summary["at"])


@pytest.mark.optional_zip
def test_e2e_optional_real_package(monkeypatch: pytest.MonkeyPatch):
    """When VIBE19_TEST_PACKAGE_DIR / local BUILDING_100.zip exists, exercise real UI path."""
    from tests.test_upload_building_weather_combos import _optional_real_package_dir

    d = _optional_real_package_dir()
    if d is None or not (d / "BUILDING_100.zip").is_file():
        pytest.skip("optional real BUILDING_100.zip not available")
    e2e = _load_e2e()
    summary = e2e.run_upload_variants(prefer_real=True, monkeypatch=monkeypatch)
    assert summary["real"] is True
    e2e.run_rules_and_results(summary["at"])
