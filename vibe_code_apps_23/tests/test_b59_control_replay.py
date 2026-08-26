"""Unit tests for the Building 59 CONTROL_REPLAY 30-run candidate menu."""

from __future__ import annotations

from vibe23.b59_control_replay import (
    CLAIM_STATUS,
    CONTROL_REPLAY_BASE,
    MAX_CONTROL_REPLAY_RUNS,
    control_replay_candidates,
)
from vibe23.b59_model import build_b59_screening_seed_idf


def test_control_replay_has_exactly_thirty_preregistered_candidates() -> None:
    candidates = control_replay_candidates()
    assert len(candidates) == MAX_CONTROL_REPLAY_RUNS
    assert [c.run_id for c in candidates] == [f"R{i:02d}" for i in range(1, 31)]
    assert CLAIM_STATUS == "CONTROL_REPLAY_SCREENING_NOT_CALIBRATED"


def test_control_replay_axes_include_sat_and_published_capacity_direction() -> None:
    candidates = control_replay_candidates()
    sats = {c.parameters.supply_air_temperature_setpoint_c for c in candidates}
    assert 14.4 in sats
    assert 18.5 in sats
    assert max(sats) >= 19.0
    for candidate in candidates:
        sat = candidate.parameters.supply_air_temperature_setpoint_c
        cool = candidate.parameters.occupied_cooling_setpoint_c
        assert cool - sat >= 5.5
    capacities = {c.parameters.cooling_capacity_w for c in candidates}
    assert min(capacities) < CONTROL_REPLAY_BASE.cooling_capacity_w


def test_control_replay_idf_embeds_sat_setpoint() -> None:
    warm = next(
        c
        for c in control_replay_candidates()
        if c.parameters.supply_air_temperature_setpoint_c == 18.5
    )
    text = build_b59_screening_seed_idf(warm.parameters, output_profile="lean")
    assert "18.5" in text
    assert "OFFICE_SCREENING_SEED_UNCALIBRATED" in text
