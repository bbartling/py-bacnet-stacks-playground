"""Streamlit AppTest smoke for residential DSM studio features."""
from __future__ import annotations

import os

import pytest

os.environ["VIBE23_STUDIO_PLAY_ONCE"] = "1"

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


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
    at = AppTest.from_file("streamlit_app.py", default_timeout=60)
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
    assert at.get("plotly_chart"), "expected plotly charts"
    assert at.metric, "expected metrics"
    assert at.get("link_button") or at.markdown, "expected Streamlit Cloud / Contribute controls"

    _radio(at, "ui_theme").set_value("Light").run()
    _assert_no_exceptions(at, "theme light")
    _radio(at, "ui_theme").set_value("Dark").run()
    _assert_no_exceptions(at, "theme dark")

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
