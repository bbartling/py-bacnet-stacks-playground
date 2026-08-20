"""Lookback index off-by-one, start vs final temps, TEST DOUBLE label."""
from __future__ import annotations

from eplus_gym.control_v2 import ACTION_KEYS, build_six_schedules_f, continuous_params
from eplus_gym.rl.continuity_plant import lookback_local_indices, weather_steps_after_reset
from eplus_gym.rl.multiday_env import FakeContinuityPlant


def test_lookback_indices_skip_reset_slot_and_include_95():
    idx = lookback_local_indices(lookback_days=1)
    assert weather_steps_after_reset(lookback_days=1) == 95
    assert idx[0] == 1
    assert idx[-1] == 95
    assert 0 not in idx
    naive = [t % 96 for t in range(95)]
    assert naive[0] == 0
    assert naive[-1] == 94
    assert idx != naive


def test_fake_plant_start_temps_differ_from_final_on_nonflat_day():
    plant = FakeContinuityPlant(zone_temps_f=[60.0] * 6)
    plant.start_episode()
    sched = build_six_schedules_f(continuous_params(70.0))
    payload = plant.simulate_day(sched, oat_c=[-18.0] * 24)
    assert payload["TEST_DOUBLE"] is True
    assert payload["live_energyplus"] is False
    assert payload["start_zone_temps_f"] != payload["zone_temps_f"]
    assert payload["start_zone_temps_f"] == [60.0] * 6
    assert all(k in payload["zone_temps_series_f"] for k in ACTION_KEYS)
    assert payload.get("first_runtime_timestamp") is not None
    assert payload.get("last_runtime_timestamp") is not None
