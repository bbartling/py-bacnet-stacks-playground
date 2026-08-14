"""Optional RLlib stub — shipped trainer is Stable-Baselines3.

See: eplus_gym/rl/train_sb3.py and scripts/vibe22_rl.py
Upstream shape inspiration: https://github.com/airboxlab/rllib-energyplus
"""
from __future__ import annotations


def train_ppo_stub(*, env_config: dict, timesteps: int = 10_000) -> dict:
    raise NotImplementedError(
        "RLlib is not the shipped trainer. "
        "Use: pip install -r requirements-rl.txt && "
        "python scripts/vibe22_rl.py train --algo PPO --days 2026-01-26 --timesteps 6 "
        f"(requested timesteps={timesteps}, keys={list(env_config)})"
    )


if __name__ == "__main__":
    train_ppo_stub(env_config={})
