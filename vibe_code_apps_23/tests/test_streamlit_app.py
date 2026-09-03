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
    at = AppTest.from_file(str(APP_PATH), default_timeout=60)
    at.run()
    _assert_no_exceptions(at, "initial run")

    assert {s.key for s in at.slider} >= {
        "step",
        "capacity_kwh",
        "max_power_kw",
        "eta",
        "soc_min",
        "soc_max",
        "initial_soc",
    }
    assert at.get("select_slider") or any(getattr(s, "key", None) == "dsm_minutes" for s in at.select_slider), (
        "expected DSM interval select_slider"
    )
    assert "session_id" in at.session_state and at.session_state["session_id"], "expected per-browser session id"
    assert at.get("plotly_chart"), "expected plotly charts"
    assert at.metric, "expected metrics"
    assert at.file_uploader, "expected IDF/EPW/tariff uploads on Inputs tab"
    assert at.get("data_editor") or at.get("dataframe"), "expected hourly weather + tariff spreadsheet editor"

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

    clears = [b for b in at.button if b.label == "Clear session"]
    assert clears
    old_sid = str(at.session_state["session_id"])
    clears[0].click().run()
    _assert_no_exceptions(at, "Clear session")
    assert str(at.session_state["session_id"]) != old_sid
    assert int(at.session_state["dsm_minutes"]) == 5

    _radio(at, "season").set_value("Winter extreme (Jan 15)").run()
    _assert_no_exceptions(at, "winter season")
    assert "Winter" in str(at.session_state["season"])

    _radio(at, "season").set_value("Summer extreme (Jul 15)").run()
    _assert_no_exceptions(at, "summer season")

    _radio(at, "trace").set_value("Baseline").run()
    _assert_no_exceptions(at, "baseline trace")
    _radio(at, "trace").set_value("DR event").run()
    _assert_no_exceptions(at, "dr trace")

    assert at.toggle and at.toggle[0].key == "attach_battery"
    at.toggle[0].set_value(False).run()
    _assert_no_exceptions(at, "battery off")
    at.toggle[0].set_value(True).run()
    _assert_no_exceptions(at, "battery on")

    _slider(at, "capacity_kwh").set_value(20.0).run()
    _assert_no_exceptions(at, "capacity slider")
    _slider(at, "step").set_value(100).run()
    _assert_no_exceptions(at, "timestep slider")
    assert int(at.session_state["step"]) == 100

    at.session_state.playing = True
    at.session_state._do_advance = True
    at.session_state._stop_after_advance = True
    at.run()
    _assert_no_exceptions(at, "playhead advance")
    assert int(at.session_state["step"]) == 101

    plays = [b for b in at.button if b.label == "Play"]
    assert plays
    plays[0].click().run()
    _assert_no_exceptions(at, "Play")

    resets = [b for b in at.button if b.label == "Reset"]
    assert resets
    resets[0].click().run()
    _assert_no_exceptions(at, "Reset")
    assert int(at.session_state["step"]) == 0
