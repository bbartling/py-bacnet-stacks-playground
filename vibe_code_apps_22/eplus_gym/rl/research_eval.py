"""Deterministic saved-policy evaluation. Training mean reward cannot crown a winner."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from eplus_gym.control_v2 import (
    SixZoneDailyParamsV2,
    continuous_params,
    observed_bas_incumbent_params,
)
from eplus_gym.rl.multiday_env import MultiDayDailyEnv
from eplus_gym.rl.obs_v3 import N_OBS_V3
from eplus_gym.rl.research_spaces import (
    RESEARCH_ACTION_CONTRACT_V2,
    assert_research_v2_contract,
    decode_continuous_research_v2,
    decode_discrete_research_v2,
    encode_continuous_research_v2,
    sample_random_params_v2,
)

CLAIM = (
    "SIMULATION_ONLY_RL_RESEARCH",
    "A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED",
    "RESEARCH_LONG_ALLOWED",
    "NO_BACNET_COMMAND_AUTHORITY",
)


class PolicyReloadError(ValueError):
    """Saved SB3 zip could not be loaded under the training contract."""


def _shallow() -> SixZoneDailyParamsV2:
    return SixZoneDailyParamsV2(
        occupied_heating_f=70.0,
        unoccupied_heating_f=66.0,
        heating_setpoint_start_step=30,
        heating_setpoint_end_step=59,
        recovery_lead_minutes=60,
        recovery_ramp_minutes=60,
    )


def load_sb3_model(zip_path: Path, *, algo: str, contract: Mapping[str, Any] | None = None):
    from stable_baselines3 import DQN, PPO

    if contract is not None:
        assert_research_v2_contract(contract)
    algo_u = str(algo).upper()
    cls = PPO if algo_u == "PPO" else DQN
    if not Path(zip_path).is_file():
        raise PolicyReloadError(f"missing SB3 zip {zip_path}")
    return cls.load(str(zip_path), device="cpu")


def make_untrained_models(*, seed: int = 0) -> dict[str, Any]:
    """Seeded untrained PPO/DQN on the v2 spaces (no EnergyPlus)."""
    import gymnasium as gym
    from stable_baselines3 import DQN, PPO

    from eplus_gym.rl.research_spaces import (
        continuous_action_space_research_v2,
        discrete_action_space_research_v2,
    )

    class _Stub(gym.Env):
        metadata = {"render_modes": []}

        def __init__(self, action_space):
            super().__init__()
            self.action_space = action_space
            self.observation_space = gym.spaces.Box(
                low=-np.inf, high=np.inf, shape=(N_OBS_V3,), dtype=np.float32
            )

        def reset(self, *, seed=None, options=None):
            super().reset(seed=seed)
            return np.zeros(N_OBS_V3, dtype=np.float32), {}

        def step(self, action):
            return np.zeros(N_OBS_V3, dtype=np.float32), 0.0, True, False, {}

    ppo = PPO("MlpPolicy", _Stub(continuous_action_space_research_v2()), seed=int(seed), n_steps=8, batch_size=8)
    dqn = DQN("MlpPolicy", _Stub(discrete_action_space_research_v2()), seed=int(seed), learning_starts=2, buffer_size=64)
    return {
        "untrained_ppo": {"model": ppo, "algo": "PPO"},
        "untrained_dqn": {"model": dqn, "algo": "DQN"},
    }


def predict_params(
    *,
    model: Any,
    obs: np.ndarray,
    algo: str,
    day: str,
    deterministic: bool = True,
) -> SixZoneDailyParamsV2:
    obs = np.asarray(obs, dtype=np.float32).reshape(-1)
    if obs.size != N_OBS_V3:
        raise PolicyReloadError(f"observation dim {obs.size} != {N_OBS_V3}")
    action, _ = model.predict(obs, deterministic=bool(deterministic))
    if str(algo).upper() == "DQN":
        return decode_discrete_research_v2(int(np.asarray(action).reshape(-1)[0]), day=day)
    return decode_continuous_research_v2(action, day=day)


def _fixed_params(arm: str, day: str, rng: np.random.Generator) -> SixZoneDailyParamsV2:
    if arm == "incumbent":
        return observed_bas_incumbent_params()
    if arm == "continuous_68":
        return continuous_params(68.0)
    if arm == "continuous_70":
        return continuous_params(70.0)
    if arm == "shallow_setback":
        return _shallow()
    if arm == "random":
        return sample_random_params_v2(rng, day=day)
    raise KeyError(arm)


def evaluate_validation_arms(
    *,
    env_factory: Callable[[], MultiDayDailyEnv],
    days: Sequence[str],
    models: Mapping[str, Any],
    seed: int = 0,
) -> dict[str, Any]:
    """Run each arm through a fresh env. Candidate/baseline BillingState stay separate inside the env."""
    rng = np.random.default_rng(int(seed))
    rows: list[dict[str, Any]] = []
    models = {**make_untrained_models(seed=int(seed)), **dict(models)}
    arms = ["incumbent", "continuous_68", "continuous_70", "shallow_setback", "random"]
    for name, spec in models.items():
        arms.append(name)
    for arm in arms:
        env = env_factory()
        obs, info = env.reset(seed=int(seed))
        if int(np.asarray(obs).reshape(-1).size) != N_OBS_V3:
            raise PolicyReloadError("eval observation is not dim 80")
        done = False
        while not done:
            day = str(info.get("day") or env.days[env._day_i])
            if arm in models:
                spec = models[arm]
                params = predict_params(
                    model=spec["model"],
                    obs=obs,
                    algo=spec["algo"],
                    day=day,
                    deterministic=True,
                )
            else:
                params = _fixed_params(arm, day, rng)
            # Eval env is always the v2 Box(9) decoder path (DQN predicts Discrete then affine-encodes).
            action = encode_continuous_research_v2(params)
            obs, reward, terminated, truncated, info = env.step(action)
            done = bool(terminated or truncated)
            rows.append(
                {
                    "arm": arm,
                    "day": info.get("day"),
                    "training_reward": float(reward),
                    "peak_kw": info.get("peak_kw"),
                    "daily_kwh": info.get("daily_kwh"),
                    "readiness_ok": bool((info.get("readiness") or {}).get("readiness_ok")),
                    "energy_cost": info.get("energy_cost"),
                    "incremental_demand_cost": info.get("incremental_demand_cost"),
                    "decoded_schedule_fingerprint": info.get("decoded_schedule_fingerprint"),
                    "trajectory_sha256": info.get("trajectory_sha256"),
                    "opening_mtd_kw": info.get("opening_mtd_kw"),
                    "closing_mtd_kw": info.get("closing_mtd_kw"),
                    "billing_floor_kw": info.get("billing_floor_kw"),
                    "seed": int(seed),
                }
            )
        env.close()
    winner = select_winner(rows)
    return {
        "schema": "vibe22.research_long_eval.v1",
        "claim_labels": list(CLAIM),
        "action_contract_version": RESEARCH_ACTION_CONTRACT_V2,
        "observation_dim": N_OBS_V3,
        "days": [str(d)[:10] for d in days],
        "rows": rows,
        "winner": winner,
        "winner_rule": "deterministic_validation_plus_readiness_multi_seed; never training mean_reward",
        "SIMULATION_TRAINING_READY": False,
        "OPERATIONAL_DSM_READY": False,
        "long_campaign_allowed": False,
        "locked_unseen": "NO LOCKED UNSEEN TEST AVAILABLE",
        "bacnet_commands": 0,
    }


def select_winner(rows: Sequence[Mapping[str, Any]]) -> str | None:
    by_arm: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_arm.setdefault(str(row.get("arm")), []).append(row)

    def stats(arm: str) -> tuple[float, float] | None:
        xs = by_arm.get(arm) or []
        if not xs:
            return None
        rew = float(np.nanmean([float(r.get("training_reward") or 0.0) for r in xs]))
        ready = float(np.nanmean([1.0 if r.get("readiness_ok") else 0.0 for r in xs]))
        return rew, ready

    baselines = [
        "incumbent",
        "continuous_68",
        "continuous_70",
        "shallow_setback",
        "random",
        "untrained_ppo",
        "untrained_dqn",
    ]
    present_baselines = [a for a in baselines if a in by_arm]
    required = ["incumbent", "continuous_68", "continuous_70", "shallow_setback", "random"]
    if any(a not in by_arm for a in required):
        return None
    base_stats = [stats(a) for a in present_baselines]
    if any(s is None for s in base_stats):
        return None

    def beats_all(arm: str) -> bool:
        st = stats(arm)
        if st is None:
            return False
        rew, ready = st
        return all(rew > (bs[0] + 1e-9) and ready + 1e-9 >= bs[1] for bs in base_stats if bs is not None)

    grouped: dict[str, list[str]] = {}
    for arm in by_arm:
        if not str(arm).startswith("trained_"):
            continue
        algo = "ppo" if "ppo" in arm else ("dqn" if "dqn" in arm else arm)
        grouped.setdefault(algo, []).append(arm)
    qualifying: list[str] = []
    for _algo, seeds in grouped.items():
        if len(seeds) < 2:
            continue
        if all(beats_all(a) for a in seeds):
            qualifying.extend(seeds)
    if not qualifying:
        return None
    best_name = None
    best_rew = float("-inf")
    for arm in qualifying:
        st = stats(arm)
        if st is None:
            continue
        if st[0] > best_rew:
            best_rew = st[0]
            best_name = arm
    return best_name
