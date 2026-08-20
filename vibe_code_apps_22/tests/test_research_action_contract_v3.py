"""research_action_contract_v3 + schedule proof."""
from __future__ import annotations

import numpy as np
import pytest

from eplus_gym.rl.research_spaces import (
    N_CONT_V3,
    RESEARCH_ACTION_CONTRACT_V3,
    continuous_action_space_research_v3,
    decode_continuous_research_v3,
    decode_discrete_research_v3,
    discrete_n_research_v3,
    emit_schedule_proof,
    encode_continuous_research_v3,
    research_build_six_schedules_f,
    research_continuous_68,
    research_continuous_70,
)


def test_v3_box_is_10d():
    space = continuous_action_space_research_v3()
    assert space.shape == (N_CONT_V3,)
    assert N_CONT_V3 == 10


def test_continuous_68_70_flat_schedules():
    day = "2026-01-12"
    for params, sp in ((research_continuous_68(), 68.0), (research_continuous_70(), 70.0)):
        sched = research_build_six_schedules_f(params, day)
        proof = emit_schedule_proof(params, day)
        assert proof["continuous_conditioning"] is True
        assert proof["post_occupancy_extension_minutes"] == 0
        assert proof["cooling_action_space"] is False
        for k, series in sched.items():
            assert len(series) == 96
            assert all(abs(v - sp) < 1e-6 for v in series)
            assert all(abs(v - sp) < 1e-6 for v in proof["heating_setpoints_f"][k])


def test_extension_extends_past_fixed_dismissal_not_calendar():
    day = "2026-01-12"
    # occ/unocc/rec/offsets + extension at +1 → 180 min
    x = np.zeros(10, dtype=np.float32)
    x[0] = 0.0  # ~70F
    x[1] = -1.0  # 60F unocc
    x[2] = 0.0
    x[9] = 1.0  # 180 min extension
    params = decode_continuous_research_v3(x, day=day)
    proof = emit_schedule_proof(params, day)
    assert proof["school_occupancy_window"]["end_step"] == proof["fixed_occupied_end_step"]
    assert params.post_occupancy_extension_minutes == 180
    assert params.heating_setpoint_end_step > int(proof["fixed_occupied_end_step"])
    assert proof["post_occupancy_extension_minutes"] == 180
    # Floor never below 60
    for series in proof["heating_setpoints_f"].values():
        assert min(series) >= 60.0 - 1e-6


def test_weekend_extension_does_not_invent_occupancy():
    day = "2026-01-25"
    x = np.ones(10, dtype=np.float32)
    params = decode_continuous_research_v3(x, day=day)
    assert params.post_occupancy_extension_minutes == 0
    proof = emit_schedule_proof(params, day)
    assert proof["school_occupancy_window"]["school_occupied"] is False


def test_dqn_v3_keeps_continuous_first_no_wrap():
    assert discrete_n_research_v3() > 38
    p0 = decode_discrete_research_v3(0, day="2026-01-12")
    p1 = decode_discrete_research_v3(1, day="2026-01-12")
    assert p0.continuous_conditioning and abs(p0.occupied_heating_f - 68) < 1e-6
    assert p1.continuous_conditioning and abs(p1.occupied_heating_f - 70) < 1e-6
    with pytest.raises(ValueError, match="wrap is forbidden"):
        decode_discrete_research_v3(discrete_n_research_v3(), day="2026-01-12")


def test_encode_decode_roundtrip_v3():
    day = "2026-01-12"
    x = np.linspace(-1, 1, 10).astype(np.float32)
    params = decode_continuous_research_v3(x, day=day)
    x2 = encode_continuous_research_v3(params)
    assert x2.shape == (10,)
    assert RESEARCH_ACTION_CONTRACT_V3.startswith("research_action_contract_v3")
