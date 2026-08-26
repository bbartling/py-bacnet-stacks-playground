"""Unit tests for the Building 59 LOAD_SCHEDULE dial-in candidate menu."""

from __future__ import annotations

from vibe23.b59_load_schedule_dialin import (
    CLAIM_STATUS,
    LOAD_SCHEDULE_BASE,
    MAX_LOAD_SCHEDULE_DIALIN_RUNS,
    MEASURED_MEL_WEEKEND,
    load_schedule_dialin_candidates,
)
from vibe23.b59_model import build_b59_screening_seed_idf


def test_load_schedule_dialin_has_exactly_twenty_four_candidates() -> None:
    candidates = load_schedule_dialin_candidates()
    assert len(candidates) == MAX_LOAD_SCHEDULE_DIALIN_RUNS
    assert [c.run_id for c in candidates] == [f"R{i:02d}" for i in range(1, 25)]
    assert CLAIM_STATUS == "LOAD_SCHEDULE_DIALIN_SCREENING_NOT_CALIBRATED"


def test_load_schedule_dialin_moves_toward_measured_loads_and_shapes() -> None:
    candidates = load_schedule_dialin_candidates()
    equips = {c.parameters.equipment_w_m2 for c in candidates}
    lights = {c.parameters.lighting_w_m2 for c in candidates}
    assert min(equips) < LOAD_SCHEDULE_BASE.equipment_w_m2
    assert min(lights) < LOAD_SCHEDULE_BASE.lighting_w_m2
    assert any(c.parameters.mel_weekend_fraction == MEASURED_MEL_WEEKEND for c in candidates)
    modes = {c.parameters.hvac_availability_mode for c in candidates}
    assert modes == {"continuous", "weekday_window"}


def test_load_schedule_dialin_idf_embeds_measured_mel_weekend() -> None:
    shaped = next(
        c
        for c in load_schedule_dialin_candidates()
        if c.parameters.mel_weekend_fraction == MEASURED_MEL_WEEKEND
        and c.parameters.equipment_w_m2 == LOAD_SCHEDULE_BASE.equipment_w_m2
    )
    text = build_b59_screening_seed_idf(shaped.parameters, output_profile="lean")
    assert "0.65" in text
    assert "OFFICE_SCREENING_SEED_UNCALIBRATED" in text


def test_load_schedule_dialin_mel_ladder_avoids_warmup_severe_combo() -> None:
    candidates = {c.run_id: c for c in load_schedule_dialin_candidates()}
    # 5.5 W/m2 MEL + 11 W/m2 lights + measured MEL standby caused warmup severes.
    assert candidates["R05"].parameters.equipment_w_m2 == 6.0
    assert candidates["R05"].parameters.lighting_w_m2 == 11.0
