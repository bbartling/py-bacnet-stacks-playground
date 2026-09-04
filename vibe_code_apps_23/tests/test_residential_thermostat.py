from __future__ import annotations

import pytest

from vibe23.residential.thermostat import (
    action_to_setpoints_f,
    baseline_setpoints_f,
    build_schedule_action,
    c_to_f,
    comfort_ok,
    enforce_heat_below_cool,
    f_to_c,
)


def test_f_c_roundtrip():
    assert f_to_c(32.0) == pytest.approx(0.0)
    assert c_to_f(0.0) == pytest.approx(32.0)
    assert c_to_f(f_to_c(72.0)) == pytest.approx(72.0)


def test_baseline_length_288():
    heat, cool = baseline_setpoints_f()
    assert len(heat) == 288
    assert len(cool) == 288
    assert heat[0] == 71.5
    assert cool[0] == 72.5


def test_summer_action_raises_cool_during_event():
    action = build_schedule_action(
        mode="summer_dr",
        pre_start_hour=13.0,
        event_start=15.0,
        event_end=20.0,
        recover_end=23.0,
        event_cool_f=74.5,
        pre_cool_f=70.5,
    )
    heat, cool = action_to_setpoints_f(action)
    # Hour ending 16:00 is inside the 15-20 event window.
    idx = int(16 * 12) - 1
    assert cool[idx] == pytest.approx(74.5)
    # Hour ending 14:00 is inside precool 13-15.
    pre_idx = int(14 * 12) - 1
    assert cool[pre_idx] == pytest.approx(70.5)
    assert heat[pre_idx] < cool[pre_idx]
    assert comfort_ok([72.0] * 10)
    assert not comfort_ok([80.0] * 10)


def test_enforce_deadband():
    heat, cool = enforce_heat_below_cool([71.5], [70.5], min_gap_f=1.0)
    assert heat[0] == pytest.approx(69.5)
    assert cool[0] == pytest.approx(70.5)
