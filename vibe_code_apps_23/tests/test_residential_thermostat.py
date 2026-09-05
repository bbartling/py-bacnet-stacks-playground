from __future__ import annotations

import pytest

from vibe23.residential.thermostat import (
    action_to_setpoints_f,
    baseline_setpoints_f,
    build_schedule_action,
    c_to_f,
    center_search_values,
    center_to_heat_cool,
    comfort_ok,
    enforce_heat_below_cool,
    f_to_c,
)


def test_f_c_roundtrip():
    assert f_to_c(32.0) == pytest.approx(0.0)
    assert c_to_f(0.0) == pytest.approx(32.0)
    assert c_to_f(f_to_c(72.0)) == pytest.approx(72.0)


def test_center_to_heat_cool_2f_deadband():
    heat, cool = center_to_heat_cool(72.0)
    assert heat == pytest.approx(71.0)
    assert cool == pytest.approx(73.0)


def test_center_search_values_13():
    vals = center_search_values()
    assert len(vals) == 13
    assert vals[0] == pytest.approx(69.0)
    assert vals[-1] == pytest.approx(75.0)
    assert 72.0 in vals


def test_baseline_length_288():
    heat, cool = baseline_setpoints_f()
    assert len(heat) == 288
    assert len(cool) == 288
    assert heat[0] == pytest.approx(71.0)
    assert cool[0] == pytest.approx(73.0)


def test_summer_action_centers_apply_both_bounds():
    action = build_schedule_action(
        mode="summer_dr",
        pre_start_hour=13.0,
        event_start=16.0,
        event_end=21.0,
        recover_end=23.0,
        pre_center_f=70.0,
        event_center_f=74.0,
    )
    assert action["pre_heat_f"] == pytest.approx(69.0)
    assert action["pre_cool_f"] == pytest.approx(71.0)
    assert action["event_heat_f"] == pytest.approx(73.0)
    assert action["event_cool_f"] == pytest.approx(75.0)
    heat, cool = action_to_setpoints_f(action)
    # Hour ending 14:00 is inside pre window 13–16.
    pre_idx = int(14 * 12) - 1
    assert heat[pre_idx] == pytest.approx(69.0)
    assert cool[pre_idx] == pytest.approx(71.0)
    # Hour ending 17:00 is inside event 16–21.
    ev_idx = int(17 * 12) - 1
    assert heat[ev_idx] == pytest.approx(73.0)
    assert cool[ev_idx] == pytest.approx(75.0)
    assert cool[pre_idx] - heat[pre_idx] == pytest.approx(2.0)
    assert comfort_ok([72.0] * 10)
    assert not comfort_ok([80.0] * 10)


def test_enforce_deadband_2f():
    heat, cool = enforce_heat_below_cool([71.5], [70.5], min_gap_f=2.0)
    assert cool[0] - heat[0] == pytest.approx(2.0)
    assert heat[0] < cool[0]
