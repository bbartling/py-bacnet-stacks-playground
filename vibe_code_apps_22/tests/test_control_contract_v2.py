"""Control contract v2, 24/7 schedules, DQN/PPO v2, obs v3, fail-closed campaign."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from eplus_gym.control_v2 import (
    END_OF_DAY_STEP,
    SixZoneDailyParamsV2,
    ZoneOffsetsV2,
    build_six_schedules_f,
    build_zone_series_f_v2,
    continuous_params,
    deep_setback_params,
    first_change_step,
    observed_bas_incumbent_params,
    school_windows,
    shallow_setback_params,
    validate_params,
)
from eplus_gym.rl.active_model import ActiveModelError, load_active_model, verify_active_model
from eplus_gym.rl.obs_v3 import N_OBS_V3, PERFECT_EPISODE_FORECAST, build_observation_v3
from eplus_gym.rl.operator_pay_experiment import refuse_full_campaign
from eplus_gym.rl.spaces_v2 import (
    SETBACK_DEADBAND_F,
    decode_continuous_v2,
    decode_discrete_v2,
    discrete_n_v2,
    encode_continuous_v2,
)

APP = Path(__file__).resolve().parents[1]


def test_school_calendar_separated_from_control_schedule():
    thu = school_windows("2026-01-15")
    assert thu["thursday_early_dismissal"] is True
    assert thu["school_occupied_start_step"] == 30
    assert thu["school_occupied_end_step"] == 54
    assert thu["readiness_check_steps"] == [30, 31]
    weekend = school_windows("2026-01-17")
    assert weekend["school_occupied"] is False
    assert weekend["readiness_check_steps"] == []
    params = observed_bas_incumbent_params()
    assert params.heating_setpoint_start_step == 28
    assert params.heating_setpoint_start_step != thu["school_occupied_start_step"]


def test_end_step_96_does_not_wrap():
    p = SixZoneDailyParamsV2(
        occupied_heating_f=70.0,
        unoccupied_heating_f=64.0,
        heating_setpoint_start_step=28,
        heating_setpoint_end_step=96,
        recovery_lead_minutes=60,
    )
    series = build_zone_series_f_v2(p, "1F_A")
    assert len(series) == 96
    assert series[95] == pytest.approx(70.0)
    assert series[0] == pytest.approx(64.0)


def test_continuous_68_and_70_emit_constant_schedules():
    for sp in (68.0, 70.0):
        p = continuous_params(sp)
        sched = build_six_schedules_f(p)
        for series in sched.values():
            assert series == [sp] * 96
        assert p.mode_label() == "CONTINUOUS_CONDITIONING_THERMOSTATIC"


def test_setback_variants_and_recovery_bounds():
    deep = build_zone_series_f_v2(deep_setback_params(), "1F_A")
    shallow = build_zone_series_f_v2(shallow_setback_params(), "1F_A")
    assert min(deep) == pytest.approx(58.0)
    assert min(shallow) == pytest.approx(66.0)
    early = SixZoneDailyParamsV2(
        occupied_heating_f=70.0,
        unoccupied_heating_f=64.0,
        heating_setpoint_start_step=20,
        heating_setpoint_end_step=68,
        recovery_lead_minutes=180,
    )
    late = SixZoneDailyParamsV2(
        occupied_heating_f=70.0,
        unoccupied_heating_f=64.0,
        heating_setpoint_start_step=40,
        heating_setpoint_end_step=80,
        recovery_lead_minutes=0,
    )
    validate_params(early)
    validate_params(late)
    with pytest.raises(ValueError, match="invalid start/end"):
        build_zone_series_f_v2(
            SixZoneDailyParamsV2(
                occupied_heating_f=70.0,
                unoccupied_heating_f=64.0,
                heating_setpoint_start_step=40,
                heating_setpoint_end_step=20,
            ),
            "1F_A",
        )
    with pytest.raises(ValueError, match="offset"):
        validate_params(
            SixZoneDailyParamsV2(
                occupied_heating_f=70.0,
                unoccupied_heating_f=64.0,
                zone_offsets={"1F_A": ZoneOffsetsV2(setback_offset_f=-9.0)},
            )
        )


def test_recovery_lead_is_ramp_duration_four_distinct_schedules():
    series = []
    first = []
    for lead in (0, 60, 120, 180):
        p = SixZoneDailyParamsV2(
            occupied_heating_f=70.0,
            unoccupied_heating_f=64.0,
            heating_setpoint_start_step=28,
            heating_setpoint_end_step=68,
            recovery_lead_minutes=lead,
        )
        s = build_zone_series_f_v2(p, "1F_A")
        series.append(s)
        first.append(first_change_step(s))
    for a, b in zip(series, series[1:]):
        assert a != b
    assert first == [28, 24, 20, 16]
    assert first[0] > first[1] > first[2] > first[3]


def test_preheat_effective_sp_rejected():
    p = SixZoneDailyParamsV2(
        occupied_heating_f=70.0,
        unoccupied_heating_f=69.5,
        heating_setpoint_start_step=28,
        heating_setpoint_end_step=68,
        zone_offsets={"1F_A": ZoneOffsetsV2(setback_offset_f=1.0)},
    )
    with pytest.raises(ValueError, match="preheat"):
        validate_params(p)


def test_ppo_v2_round_trip_and_bounds():
    p = SixZoneDailyParamsV2(
        occupied_heating_f=70.0,
        unoccupied_heating_f=70.0,
        heating_setpoint_start_step=0,
        heating_setpoint_end_step=96,
        continuous_conditioning=True,
    )
    encoded = encode_continuous_v2(p)
    decoded = decode_continuous_v2(encoded)
    again = encode_continuous_v2(decoded)
    assert decoded.continuous_conditioning is True
    np.testing.assert_allclose(encoded, again, atol=1e-5)
    space = __import__("eplus_gym.rl.spaces_v2", fromlist=["continuous_action_space_v2"]).continuous_action_space_v2()
    assert float(space.high[1]) == pytest.approx(14.0)
    assert float(space.high[3]) == pytest.approx(96.0)

    shallow = decode_continuous_v2([70.0, 0.10, 28.0, 68.0, 60.0] + [0.0] * 6)
    assert shallow.continuous_conditioning is True
    assert shallow.mode_label() == "CONTINUOUS_CONDITIONING_THERMOSTATIC"
    deep = decode_continuous_v2([70.0, 6.0, 28.0, 68.0, 60.0] + [0.0] * 6)
    assert deep.continuous_conditioning is False
    assert deep.unoccupied_heating_f == pytest.approx(64.0)
    assert SETBACK_DEADBAND_F == pytest.approx(0.25)


def test_dqn_v2_has_explicit_continuous_actions():
    assert discrete_n_v2() == 110
    a0 = decode_discrete_v2(0)
    a1 = decode_discrete_v2(1)
    assert a0.occupied_heating_f == 68.0 and a0.unoccupied_heating_f == 68.0
    assert a1.occupied_heating_f == 70.0 and a1.unoccupied_heating_f == 70.0
    assert build_zone_series_f_v2(a1, "1F_A") == [70.0] * 96
    setback = decode_discrete_v2(2, day="2026-01-15")
    assert setback.heating_setpoint_end_step == 54
    with pytest.raises(ValueError, match="outside"):
        decode_discrete_v2(-1)
    with pytest.raises(ValueError, match="outside"):
        decode_discrete_v2(discrete_n_v2())
    from eplus_gym.rl.spaces import discrete_n

    assert discrete_n() == 64


def test_obs_v3_has_24_hourly_forecast_and_previous_action():
    oat = list(range(24))
    prev = [70.0, 64.0, 28.0, 68.0, 60.0] + [0.0] * 6
    vec, ctx = build_observation_v3(
        day="2026-01-12",
        hourly_oat_c=oat,
        zone_temps_f=[68.0] * 6,
        billing_floor_kw=200.0,
        mtd_peak_kw=210.0,
        previous_day_peak_kw=180.0,
        previous_day_kwh=1200.0,
        previous_action=prev,
        continuous_conditioning_state=1.0,
    )
    assert vec.shape == (N_OBS_V3,)
    assert N_OBS_V3 == 80
    assert ctx["hourly_oat_c"] == [float(x) for x in oat]
    assert ctx["forecast_source"] == PERFECT_EPISODE_FORECAST
    assert ctx["previous_action"] == prev
    assert ctx["mtd_peak_kw"] == pytest.approx(210.0)
    assert ctx["billing_floor_kw"] == pytest.approx(200.0)
    assert ctx["mtd_peak_distinct_from_billing_floor"] is True
    assert ctx["loop_entering_water_present"] is False
    assert ctx["previous_action_normalized"][0] == pytest.approx(0.70)
    assert ctx["no_future_weather_beyond_declared_forecast"] is True
    masked = build_observation_v3(
        day="2026-01-12",
        hourly_oat_c=oat,
        zone_temps_f=[68.0] * 6,
        billing_floor_kw=200.0,
        mtd_peak_kw=210.0,
        loop_entering_water_c=8.0,
        loop_leaving_water_c=None,
    )[1]
    assert masked["loop_entering_water_present"] is True
    assert masked["loop_leaving_water_present"] is False
    with pytest.raises(ValueError, match="24"):
        build_observation_v3(
            day="2026-01-12",
            hourly_oat_c=list(range(48)),
            zone_temps_f=[68.0] * 6,
            billing_floor_kw=0.0,
            mtd_peak_kw=0.0,
        )


def test_fail_closed_active_model_and_campaign():
    body = load_active_model(APP)
    assert body["long_campaign_allowed"] is False
    with pytest.raises(ActiveModelError):
        verify_active_model(APP)
    decision = refuse_full_campaign(APP)
    assert decision["allowed"] is False


def test_contracts_exist_and_observed_incumbent_is_not_sch_htgsp():
    names = [
        "control_contract_v2.json",
        "school_calendar_v2.json",
        "observation_contract_v3.json",
        "ppo_action_contract_v2.json",
        "dqn_action_contract_v2.json",
        "active_rl_model_v1.json",
        "reward_contract_v2.json",
        "observed_bas_incumbent_v2.json",
    ]
    for name in names:
        assert (APP / "contracts" / name).is_file()
    obs = json.loads((APP / "contracts" / "observed_bas_incumbent_v2.json").read_text(encoding="utf-8"))
    assert obs["replay_params"]["occupied_heating_f"] == 68.0
    assert "46" not in str(obs["replay_params"])
    assert obs["do_not_tune_to_utility_peak"] is True
