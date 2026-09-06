"""Streamlit AppTest smoke for residential DSM studio features."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ["VIBE23_STUDIO_PLAY_ONCE"] = "1"
os.environ.setdefault("EPLUS_BACKEND", "worker")

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_app.py"
MODEL_IDF = Path(__file__).resolve().parents[1] / "model" / "residential_heat_pump_home.idf"


def _assert_no_exceptions(at: AppTest, label: str) -> None:
    if at.exception:
        details = "\n".join(repr(e) for e in at.exception)
        raise AssertionError(f"{label}: {details}")


def _slider(at: AppTest, key: str):
    for item in at.slider:
        if item.key == key:
            return item
    raise AssertionError(f"missing slider key={key!r}; have={[s.key for s in at.slider]}")


def _radio(at: AppTest, key: str):
    for item in at.radio:
        if item.key == key:
            return item
    raise AssertionError(f"missing radio key={key!r}; have={[r.key for r in at.radio]}")


def test_studio_app_features() -> None:
    at = AppTest.from_file(str(APP_PATH), default_timeout=90)
    at.run()
    _assert_no_exceptions(at, "initial run")

    assert {s.key for s in at.slider} >= {
        "capacity_kwh",
        "max_power_kw",
        "eta",
        "soc_min",
        "soc_max",
        "initial_soc",
        "comfort_wtp",
        "econ_target",
        "comfort_low_f",
        "comfort_high_f",
    }
    assert "grid_max_candidates" not in {s.key for s in at.slider}
    assert at.get("select_slider") or any(getattr(s, "key", None) == "dsm_minutes" for s in at.select_slider)
    assert "session_id" in at.session_state and at.session_state["session_id"]
    assert at.file_uploader

    tab_labels = [getattr(t, "label", None) for t in at.tabs]
    assert tab_labels == ["Inputs", "Twin replay", "Grid flex calculator", "Economics"], tab_labels

    blob = " | ".join(
        [
            *(str(e.value) for e in at.error),
            *(str(i.value) for i in at.info),
            *(str(c.value) for c in at.caption),
        ]
    )
    assert "ILLUSTRATIVE_PHYSICS_PROXY" not in blob
    assert "Grid search" not in tab_labels
    assert "Legacy" not in blob
    assert "vibe23-energyplus-worker.onrender.com" in blob or any(
        "onrender.com" in str(getattr(m, "value", m)) for m in at.markdown
    )
    assert "Upload an IDF" in blob or "Upload an EnergyPlus" in blob

    assert any("169-cell" in str(b.label) for b in at.button)

    clears = [b for b in at.button if b.label == "Clear session"]
    assert clears
    old_sid = str(at.session_state["session_id"])
    clears[0].click().run()
    _assert_no_exceptions(at, "Clear session")
    assert str(at.session_state["session_id"]) != old_sid

    _radio(at, "season").set_value("Winter design cold (Jan 3)").run()
    _assert_no_exceptions(at, "winter season")
    _radio(at, "season").set_value("Summer hot day (Jul 15)").run()
    _assert_no_exceptions(at, "summer season")

    batt = next(t for t in at.toggle if t.key == "attach_battery")
    batt.set_value(False).run()
    _assert_no_exceptions(at, "battery off")
    batt.set_value(True).run()
    _assert_no_exceptions(at, "battery on")
    _slider(at, "capacity_kwh").set_value(20.0).run()
    _assert_no_exceptions(at, "capacity slider")


def test_no_proxy_and_idf_required() -> None:
    at = AppTest.from_file(str(APP_PATH), default_timeout=90)
    at.run()
    _assert_no_exceptions(at, "initial run")
    assert at.session_state["idf_uploaded"] is False
    errors = " | ".join(str(e.value) for e in at.error)
    assert "Upload an IDF" in errors
    assert "ILLUSTRATIVE_PHYSICS_PROXY" not in errors


def test_grid_config_fingerprint_tracks_sidebar() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("_vibe23_studio_app", APP_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    import streamlit as stlib

    state = {
        "attach_battery": True,
        "capacity_kwh": 13.5,
        "max_power_kw": 5.0,
        "eta": 0.95,
        "soc_min": 0.10,
        "soc_max": 0.95,
        "initial_soc": 0.50,
        "comfort_low_f": 69.5,
        "comfort_high_f": 74.5,
        "grid_max_candidates": 169,
        "idf_text": None,
        "idf_uploaded": False,
    }
    for key, value in state.items():
        stlib.session_state[key] = value

    fp1 = module._grid_config_fingerprint("summer")
    stlib.session_state.capacity_kwh = 20.0
    fp2 = module._grid_config_fingerprint("summer")
    assert fp1 != fp2
