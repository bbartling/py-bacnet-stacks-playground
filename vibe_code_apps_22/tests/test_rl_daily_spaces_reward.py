"""Unit tests for RL daily spaces + reward (no EnergyPlus)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from eplus_gym.objective import BAS_ZONE_COLS
from eplus_gym.rl import SCHOOL_START_STEP
from eplus_gym.rl.reward import FAIL_REWARD, compute_daily_reward
from eplus_gym.rl.spaces import (
    N_CONT,
    decode_continuous,
    decode_discrete,
    discrete_n,
    encode_continuous,
)


def test_school_start_step_is_8am():
    assert SCHOOL_START_STEP == 32


def test_continuous_roundtrip():
    params = decode_continuous(
        [70.0, 62.0, 28.0, 68.0, 60.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    )
    assert params.unoccupied_heating_f == pytest.approx(62.0)
    assert params.recovery_start_minutes_before_occupancy == 60
    assert params.zone_offsets["1F_A"].setback_offset_f == pytest.approx(-1.0)
    enc = encode_continuous(params)
    assert enc.shape == (N_CONT,)
    again = decode_continuous(enc)
    assert again.occupied_heating_f == pytest.approx(params.occupied_heating_f)


def test_continuous_clips_bounds():
    params = decode_continuous([99.0, 40.0, 5.0, 90.0, 999.0] + [-9.0] * 6)
    assert 68.0 <= params.occupied_heating_f <= 72.0
    assert 58.0 <= params.unoccupied_heating_f <= 68.0
    assert 20 <= params.occupancy_start_step <= 40


def test_discrete_cardinality():
    assert discrete_n() == 64
    p0 = decode_discrete(0)
    p1 = decode_discrete(1)
    assert p0.occupied_heating_f == 70.0
    assert p0.unoccupied_heating_f in (60.0, 62.0, 64.0, 66.0)


def _toy_df(*, zone_f: float, kw: float = 100.0) -> pd.DataFrame:
    rows = []
    for s in range(96):
        row = {"step": s, "local_step": s, "facility_kw": kw}
        for c in BAS_ZONE_COLS:
            row[c] = zone_f
        rows.append(row)
    return pd.DataFrame(rows)


def test_reward_penalizes_cold_at_school_start():
    warm = compute_daily_reward(_toy_df(zone_f=70.0, kw=100.0))
    cold = compute_daily_reward(_toy_df(zone_f=60.0, kw=100.0))
    assert warm.reward > cold.reward
    assert cold.pre8_violations > 0


def test_reward_penalizes_higher_energy():
    low = compute_daily_reward(_toy_df(zone_f=70.0, kw=50.0))
    high = compute_daily_reward(_toy_df(zone_f=70.0, kw=200.0))
    assert low.reward > high.reward


def test_reward_fail_closed_empty():
    br = compute_daily_reward(pd.DataFrame())
    assert br.failed
    assert br.reward == FAIL_REWARD
