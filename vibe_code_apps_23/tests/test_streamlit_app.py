"""Streamlit AppTest smoke for residential DSM studio features."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ["VIBE23_STUDIO_PLAY_ONCE"] = "1"

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_app.py"


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
        "step",
        "dr_step",
        "cand_step",
        "capacity_kwh",
        "max_power_kw",
        "eta",
        "soc_min",
        "soc_max",
        "initial_soc",
        "comfort_wtp",
        "econ_target",
        "grid_max_candidates",
        "comfort_low_f",
        "comfort_high_f",
    }
    assert at.get("select_slider") or any(getattr(s, "key", None) == "dsm_minutes" for s in at.select_slider), (
        "expected DSM interval select_slider"
    )
    assert "session_id" in at.session_state and at.session_state["session_id"], "expected per-browser session id"
    assert at.get("plotly_chart"), "expected plotly charts"
    assert at.metric, "expected metrics"
    assert at.file_uploader, "expected IDF/EPW/tariff uploads on Inputs tab"
    assert at.get("data_editor") or at.get("dataframe"), "expected hourly weather + tariff spreadsheet editor"
    assert "trace" not in {r.key for r in at.radio}, "trace radio must stay removed"

    tab_labels = [getattr(t, "label", None) for t in at.tabs]
    assert tab_labels == ["Inputs", "Grid search", "Twin replay", "Grid flex calculator", "Economics"], tab_labels

    # Seed independent axis values, then advance twin only.
    at.session_state.dr_step = 7
    at.session_state.cand_step = 3
    at.session_state.step = 10
    at.session_state.playing_twin = True
    at.session_state._do_advance_twin = True
    at.session_state._stop_after_advance_twin = True
    at.run()
    _assert_no_exceptions(at, "twin-only advance")
    assert int(at.session_state["step"]) == 11
    assert int(at.session_state["dr_step"]) == 7, "DR playhead must not move when Twin advances"
    assert int(at.session_state["cand_step"]) == 3, "cand playhead must not move when Twin advances"
    assert at.session_state["playing_twin"] is False

    dsm = None
    for item in at.select_slider:
        if item.key == "dsm_minutes":
            dsm = item
            break
    assert dsm is not None
    dsm.set_value(60).run()
    _assert_no_exceptions(at, "dsm 1 hour")
    assert int(at.session_state["dsm_minutes"]) == 60
    assert int(at.session_state["step"]) == 0
    assert int(at.session_state["dr_step"]) == 0

    clears = [b for b in at.button if b.label == "Clear session"]
    assert clears
    old_sid = str(at.session_state["session_id"])
    clears[0].click().run()
    _assert_no_exceptions(at, "Clear session")
    assert str(at.session_state["session_id"]) != old_sid
    assert int(at.session_state["dsm_minutes"]) == 5
    assert int(at.session_state["cand_step"]) == 0

    _radio(at, "season").set_value("Winter design cold (Jan 3)").run()
    _assert_no_exceptions(at, "winter season")
    assert "Winter" in str(at.session_state["season"])

    _radio(at, "season").set_value("Summer hot day (Jul 15)").run()
    _assert_no_exceptions(at, "summer season")

    assert at.toggle and any(t.key == "attach_battery" for t in at.toggle)
    batt = next(t for t in at.toggle if t.key == "attach_battery")
    batt.set_value(False).run()
    _assert_no_exceptions(at, "battery off")
    batt.set_value(True).run()
    _assert_no_exceptions(at, "battery on")

    _slider(at, "capacity_kwh").set_value(20.0).run()
    _assert_no_exceptions(at, "capacity slider")
    _slider(at, "step").set_value(100).run()
    _assert_no_exceptions(at, "timestep slider")
    assert int(at.session_state["step"]) == 100

    # Run search advances cand_step only.
    before_twin = int(at.session_state["step"])
    before_dr = int(at.session_state["dr_step"])
    at.session_state.cand_step = 0
    at.session_state.playing_cand = True
    at.session_state._do_advance_cand = True
    at.session_state._stop_after_advance_cand = True
    at.run()
    _assert_no_exceptions(at, "cand advance")
    assert int(at.session_state["cand_step"]) == 1
    assert int(at.session_state["step"]) == before_twin
    assert int(at.session_state["dr_step"]) == before_dr

    run_btns = [b for b in at.button if b.label == "Run search"]
    assert run_btns, "expected Run search button on Grid search tab"
    run_btns[0].click().run()
    _assert_no_exceptions(at, "Run search click")

    promotes = [b for b in at.button if b.label == "Promote winner to Twin"]
    assert promotes, "expected Promote winner to Twin button on Grid search tab"

    plays = [b for b in at.button if b.label == "Play" and getattr(b, "key", None) == "btn_play_twin"]
    if not plays:
        plays = [b for b in at.button if b.label == "Play"]
    assert plays
    plays[0].click().run()
    _assert_no_exceptions(at, "Play twin")

    resets = [b for b in at.button if "Reset" in str(b.label)]
    assert resets
    # Prefer twin reset
    twin_reset = next((b for b in resets if getattr(b, "key", None) == "btn_reset_twin"), resets[0])
    twin_reset.click().run()
    _assert_no_exceptions(at, "Reset twin")
    assert int(at.session_state["step"]) == 0


def test_fixture_replay_is_labelled_synthetic() -> None:
    """With no live run loaded, the studio must not present fixtures as EnergyPlus days."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=90)
    at.run()
    _assert_no_exceptions(at, "initial run")

    assert at.session_state["session_ranking_path"] is None, "no live run in a fresh session"
    warnings = " | ".join(str(w.value) for w in at.warning)
    assert "ILLUSTRATIVE_PHYSICS_PROXY" in warnings, warnings
    assert "not EnergyPlus simulations" in warnings, warnings

    captions = " | ".join(str(c.value) for c in at.caption)
    assert "not a simulation" in captions, "expected the iteration prose to distinguish fixture replay"
    assert "synthetic proxy baseline" in captions, "expected the flex tab to disclaim its traces"

    # Reveal some Q-table cells so the heatmap (and its caption) render.
    at.session_state.cand_step = 12
    at.run()
    _assert_no_exceptions(at, "fixture cells revealed")
    captions = " | ".join(str(c.value) for c in at.caption)
    assert "proxy scores" in captions, "expected the Q-table caption to disclaim proxy cells"


def test_grid_config_fingerprint_tracks_sidebar() -> None:
    """The live-run fingerprint must move when battery sizing or the comfort band moves."""
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
        "grid_max_candidates": 2,
        "idf_text": None,
    }

    class _State(dict):
        def __getattr__(self, name):
            return self[name]

    original = stlib.session_state
    try:
        stlib.session_state = _State(state)  # type: ignore[assignment]
        base = module._grid_config_fingerprint("summer")
        assert module._grid_config_fingerprint("summer") == base, "fingerprint must be stable"
        assert module._grid_config_fingerprint("winter") != base, "season must change identity"

        params = module._sidebar_battery_params()
        assert params.capacity_kwh == 13.5
        assert params.max_charge_kw == params.max_discharge_kw == 5.0
        assert params.eta_c == params.eta_d == 0.95
        assert params.initial_soc == 0.50

        stlib.session_state["capacity_kwh"] = 20.0
        assert module._grid_config_fingerprint("summer") != base, "battery capacity must change identity"

        stlib.session_state["capacity_kwh"] = 13.5
        stlib.session_state["comfort_high_f"] = 78.0
        assert module._grid_config_fingerprint("summer") != base, "comfort band must change identity"

        stlib.session_state["comfort_high_f"] = 74.5
        stlib.session_state["idf_text"] = "Version,26.1;"
        assert module._grid_config_fingerprint("summer") != base, "IDF identity must change identity"
    finally:
        stlib.session_state = original  # type: ignore[assignment]
