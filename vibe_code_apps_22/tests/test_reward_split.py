"""Occupied low/high DH and within-day vs between-day movement."""
from __future__ import annotations

import pytest

from eplus_gym.control_v2 import ACTION_KEYS, SixZoneDailyParamsV2, build_six_schedules_f
from eplus_gym.rl.reward_v2 import (
    action_movement,
    between_day_action_movement,
    occupied_zone_degree_hours,
    occupied_zone_high_degree_hours,
    score_day_v2,
)

SCHOOL = "2026-01-12"


def _zones(v: float) -> dict[str, list[float]]:
    return {k: [float(v)] * 96 for k in ACTION_KEYS}


def test_occupied_high_degree_hours_separate_from_low():
    hot = _zones(80.0)
    cold = _zones(60.0)
    assert occupied_zone_high_degree_hours(hot, day=SCHOOL) > 0
    assert occupied_zone_degree_hours(hot, day=SCHOOL) == pytest.approx(0.0)
    assert occupied_zone_degree_hours(cold, day=SCHOOL) > 0
    assert occupied_zone_high_degree_hours(cold, day=SCHOOL) == pytest.approx(0.0)


def test_within_and_between_day_movement_reported_separately():
    params = SixZoneDailyParamsV2(
        occupied_heating_f=70.0,
        unoccupied_heating_f=58.0,
        heating_setpoint_start_step=28,
        heating_setpoint_end_step=68,
        recovery_lead_minutes=0,
    )
    sched = build_six_schedules_f(params)
    cc = build_six_schedules_f(SixZoneDailyParamsV2(70.0, 70.0, continuous_conditioning=True))
    within = action_movement(sched)
    between = between_day_action_movement(cc, sched)
    assert within > 0
    assert between > 0
    scored = score_day_v2(
        day=SCHOOL,
        candidate_facility_kw=[100.0] * 96,
        candidate_zone_temps_f=_zones(70.0),
        baseline_facility_kw=[110.0] * 96,
        baseline_zone_temps_f=_zones(70.0),
        candidate_schedules=sched,
        previous_schedules=cc,
    )
    assert scored.extras["within_day_schedule_movement"] == pytest.approx(within)
    assert scored.extras["between_day_action_movement"] == pytest.approx(between)
    assert scored.extras["training_movement_term"] == "within_day_schedule_movement"
