"""Paired baseline provenance. Raw dicts without TEST_DOUBLE/hashes are rejected."""
from __future__ import annotations

import pytest

from eplus_gym.control_v2 import build_six_schedules_f, continuous_params
from eplus_gym.rl.multiday_env import (
    FakeContinuityPlant,
    MultiDayDailyEnv,
    validate_baseline_payload,
)
from eplus_gym.rl.reward_v2 import MissingBaselineError
from eplus_gym.rl.spaces_v2 import encode_continuous_v2


def test_raw_payload_without_provenance_is_rejected():
    with pytest.raises(MissingBaselineError, match="provenance"):
        validate_baseline_payload(
            {"facility_kw": [1.0] * 96, "zone_temps_series_f": {}},
            live_energyplus=False,
            expected_day="2026-01-12",
        )


def test_test_double_payload_accepted_only_when_not_live():
    plant = FakeContinuityPlant()
    plant.start_episode()
    rec = plant.simulate_day(build_six_schedules_f(continuous_params(70.0)), oat_c=[-10.0] * 24)
    rec["TEST_DOUBLE"] = True
    validate_baseline_payload(rec, live_energyplus=False, expected_day="2026-01-12")
    with pytest.raises(MissingBaselineError, match="TEST DOUBLE"):
        validate_baseline_payload(rec, live_energyplus=True, expected_day="2026-01-12")


def test_literal_paired_baseline_is_not_a_fingerprint():
    env = MultiDayDailyEnv(
        {
            "n_days": 1,
            "start_day": "2026-01-12",
            "plant": FakeContinuityPlant(),
            "hourly_oat": {"2026-01-12": [-10.0] * 24},
            "baseline_cache": {"paired_baseline": {"facility_kw": [1.0] * 96}},
        }
    )
    env.reset()
    with pytest.raises(MissingBaselineError):
        env.step(encode_continuous_v2(continuous_params(68.0)))
