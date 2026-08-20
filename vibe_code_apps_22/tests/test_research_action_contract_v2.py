"""research_action_contract_v2: normalized PPO Box(9), frozen v1, no dishonest packs."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eplus_gym.control_v2 import ACTION_KEYS, build_six_schedules_f
from eplus_gym.rl.obs_v3 import N_OBS_V3
from eplus_gym.rl.research_spaces import (
    RESEARCH_ACTION_CONTRACT,
    RESEARCH_ACTION_CONTRACT_V2,
    RESEARCH_UNOCC_F_LO,
    ActionContractMismatch,
    assert_research_v2_contract,
    continuous_action_space_research,
    continuous_action_space_research_v2,
    decode_continuous_research,
    decode_continuous_research_v2,
    decode_discrete_research_v2,
    discrete_n_research_v2,
    encode_continuous_research_v2,
    research_build_six_schedules_f,
    research_continuous_68,
    research_continuous_70,
)

APP = Path(__file__).resolve().parents[1]
SCHOOL_DAY = "2025-12-08"  # Monday
WEEKEND = "2025-12-13"  # Saturday


def test_v1_physical_box_is_frozen():
    space = continuous_action_space_research()
    assert space.shape == (9,)
    assert float(space.low[0]) == 68.0
    p = decode_continuous_research([68.0, 66.0, 0.0] + [0.0] * 6, day=SCHOOL_DAY)
    assert p.occupied_heating_f == pytest.approx(68.0)
    assert RESEARCH_UNOCC_F_LO >= 66.0
    assert RESEARCH_ACTION_CONTRACT == "research_action_contract_v1"


def test_v2_box_is_normalized_unit_interval():
    space = continuous_action_space_research_v2()
    assert space.shape == (9,)
    assert space.dtype == np.float32
    assert np.allclose(space.low, -1.0)
    assert np.allclose(space.high, 1.0)


def test_affine_round_trip_and_bounds():
    rng = np.random.default_rng(0)
    for _ in range(40):
        x = rng.uniform(-1.0, 1.0, size=9).astype(np.float32)
        params = decode_continuous_research_v2(x, day=SCHOOL_DAY)
        assert 68.0 - 1e-6 <= params.occupied_heating_f <= 72.0 + 1e-6
        assert 60.0 - 1e-6 <= params.unoccupied_heating_f <= params.occupied_heating_f + 1e-6
        assert params.recovery_lead_minutes % 15 == 0
        assert 0 <= params.recovery_lead_minutes <= 180
        for key in ACTION_KEYS:
            eff = params.unoccupied_heating_f + params.zone_offsets[key].setback_offset_f
            assert 60.0 - 1e-6 <= eff <= params.occupied_heating_f + 1e-6
        x2 = encode_continuous_research_v2(params)
        again = decode_continuous_research_v2(x2, day=SCHOOL_DAY)
        assert again.occupied_heating_f == pytest.approx(params.occupied_heating_f, abs=0.02)
        assert again.unoccupied_heating_f == pytest.approx(params.unoccupied_heating_f, abs=0.02)
        assert again.recovery_lead_minutes == params.recovery_lead_minutes


def test_continuous_68_and_70_reachable():
    c68 = decode_continuous_research_v2([-1.0, 1.0, -1.0] + [0.0] * 6, day=SCHOOL_DAY)
    c70 = decode_continuous_research_v2([0.0, 1.0, -1.0] + [0.0] * 6, day=SCHOOL_DAY)
    assert c68.continuous_conditioning
    assert c70.continuous_conditioning
    assert c68.occupied_heating_f == pytest.approx(68.0, abs=0.02)
    assert c70.occupied_heating_f == pytest.approx(70.0, abs=0.02)
    s68 = research_build_six_schedules_f(c68, SCHOOL_DAY)["1F_A"]
    s70 = research_build_six_schedules_f(c70, SCHOOL_DAY)["1F_A"]
    assert s68 == pytest.approx([68.0] * 96, abs=0.05)
    assert s70 == pytest.approx([70.0] * 96, abs=0.05)
    assert research_continuous_68().occupied_heating_f == 68.0
    assert research_continuous_70().occupied_heating_f == 70.0


def test_deep_setback_60_and_recovery_180():
    params = decode_continuous_research_v2([0.0, -1.0, 1.0] + [0.0] * 6, day=SCHOOL_DAY)
    assert params.occupied_heating_f == pytest.approx(70.0, abs=0.05)
    assert params.unoccupied_heating_f == pytest.approx(60.0, abs=0.05)
    assert params.recovery_lead_minutes == 180
    assert not params.continuous_conditioning


def test_weekend_is_all_unoccupied_unless_continuous():
    setback = decode_continuous_research_v2([0.0, -1.0, 0.0] + [0.0] * 6, day=WEEKEND)
    series = research_build_six_schedules_f(setback, WEEKEND)["1F_A"]
    assert len(series) == 96
    assert max(series) == pytest.approx(min(series), abs=0.05)
    assert min(series) == pytest.approx(60.0, abs=0.15)
    assert setback.heating_setpoint_start_step == 0
    assert setback.heating_setpoint_end_step == 0
    cont = decode_continuous_research_v2([0.0, 1.0, -1.0] + [0.0] * 6, day=WEEKEND)
    cseries = research_build_six_schedules_f(cont, WEEKEND)["1F_A"]
    assert cseries == pytest.approx([70.0] * 96, abs=0.05)


def test_heating_never_breaches_cooling_deadband():
    params = decode_continuous_research_v2([1.0, 1.0, -1.0] + [0.0] * 6, day=SCHOOL_DAY)
    series = research_build_six_schedules_f(params, SCHOOL_DAY)["1F_A"]
    assert max(series) <= 74.0 - 2.0 + 1e-6


def test_dqn_v2_no_wrap_and_cardinality():
    assert discrete_n_research_v2() == 38
    decode_discrete_research_v2(0, day=SCHOOL_DAY)
    decode_discrete_research_v2(37, day=SCHOOL_DAY)
    with pytest.raises(ValueError, match="wrap"):
        decode_discrete_research_v2(38, day=SCHOOL_DAY)
    with pytest.raises(ValueError, match="wrap"):
        decode_discrete_research_v2(-1, day=SCHOOL_DAY)
    deep = [decode_discrete_research_v2(i, day=SCHOOL_DAY) for i in range(38)]
    assert any(abs(p.unoccupied_heating_f - 60.0) < 1e-6 and not p.continuous_conditioning for p in deep)


def test_untrained_ppo_samples_interior_not_physical_floor():
    pytest.importorskip("stable_baselines3")
    import gymnasium as gym
    from stable_baselines3 import PPO

    space = continuous_action_space_research_v2()

    class _Stub(gym.Env):
        metadata = {"render_modes": []}

        def __init__(self):
            super().__init__()
            self.action_space = space
            self.observation_space = gym.spaces.Box(
                low=-np.inf, high=np.inf, shape=(N_OBS_V3,), dtype=np.float32
            )

        def reset(self, *, seed=None, options=None):
            super().reset(seed=seed)
            return np.zeros(N_OBS_V3, dtype=np.float32), {}

        def step(self, action):
            return np.zeros(N_OBS_V3, dtype=np.float32), 0.0, True, False, {}

    model = PPO("MlpPolicy", _Stub(), seed=0, n_steps=8, batch_size=8)
    occs, unoccs, recs = [], [], []
    obs = np.zeros(N_OBS_V3, dtype=np.float32)
    for i in range(64):
        obs[0] = float(i) / 64.0
        action, _ = model.predict(obs, deterministic=False)
        params = decode_continuous_research_v2(action, day=SCHOOL_DAY)
        occs.append(params.occupied_heating_f)
        unoccs.append(params.unoccupied_heating_f)
        recs.append(params.recovery_lead_minutes)
    assert not all(abs(x - 68.0) < 0.05 for x in occs)
    assert not all(abs(x - 60.0) < 0.05 for x in unoccs)
    assert not all(x == 0 for x in recs)
    assert len({round(x, 1) for x in occs}) >= 2


def test_refuse_v1_contract_load():
    with pytest.raises(ActionContractMismatch, match="research_action_contract_v2"):
        assert_research_v2_contract({"action_contract_version": RESEARCH_ACTION_CONTRACT})
    assert_research_v2_contract({"action_contract_version": RESEARCH_ACTION_CONTRACT_V2})


def test_v1_decode_rejects_v2_normalized_vector_as_physical():
    """v1 must not silently reinterpret a [-1,1] vector."""
    p = decode_continuous_research([-1.0, -1.0, -1.0] + [-1.0] * 6, day=SCHOOL_DAY)
    assert p.occupied_heating_f == pytest.approx(68.0)
    assert p.unoccupied_heating_f == pytest.approx(66.0)
