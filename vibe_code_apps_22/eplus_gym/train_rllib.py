"""Optional RLlib training stub — not required for rule DR.

Install extras later: pip install 'ray[rllib]' gymnasium
Then wire LakesideIdealLoadsEnv into an RLlib algorithm (see airboxlab/rllib-energyplus).

This module deliberately does not import ray at module load.
"""
from __future__ import annotations


def train_ppo_stub(*, env_config: dict, timesteps: int = 10_000) -> dict:
    """Placeholder. Raises with install / wiring instructions."""
    raise NotImplementedError(
        "RLlib training is scaffolded, not shipped. "
        "1) pip install 'ray[rllib]'  "
        "2) register LakesideIdealLoadsEnv  "
        "3) follow https://github.com/airboxlab/rllib-energyplus train/rllib.py  "
        f"(requested timesteps={timesteps}, keys={list(env_config)})"
    )


if __name__ == "__main__":
    train_ppo_stub(env_config={})
