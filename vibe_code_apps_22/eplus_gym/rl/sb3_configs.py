"""Named SB3 configs. Smoke values must not be used for long_poc."""
from __future__ import annotations

from typing import Any

PUBLIC_NOTE = (
    "PPO vs DQN is not a pure algorithm comparison; action spaces differ. "
    "Training mean reward cannot crown a winner."
)

SMOKE: dict[str, Any] = {
    "name": "smoke",
    "ppo": {"n_steps": 8, "batch_size": 8},
    "dqn": {"learning_starts": 2, "buffer_size": 64, "exploration_fraction": 0.5, "target_update_interval": 10},
    "timesteps": 8,
}

PILOT: dict[str, Any] = {
    "name": "pilot",
    "ppo": {"n_steps": 64, "batch_size": 32},
    "dqn": {
        "learning_starts": 32,
        "buffer_size": 2048,
        "exploration_fraction": 0.3,
        "target_update_interval": 50,
    },
    "timesteps": 64,
}

LONG_POC: dict[str, Any] = {
    "name": "long_poc",
    "label": "PRELIMINARY_SINGLE_SEED",
    "ppo": {"n_steps": 256, "batch_size": 64},
    "dqn": {
        "learning_starts": 256,
        "buffer_size": 50_000,
        "exploration_fraction": 0.2,
        "target_update_interval": 100,
    },
    "checkpoint_every_valid_transitions": 50,
    "checkpoint_every_s": 900,
    "obs_norm_train_only": True,
}

RESEARCH_POC: dict[str, Any] = {
    "name": "research_poc",
    "label": "SIMULATION_ONLY_RESEARCH_POC",
    "ppo": {"n_steps": 4, "batch_size": 4},
    "dqn": {
        "learning_starts": 2,
        "buffer_size": 256,
        "exploration_fraction": 0.5,
        "target_update_interval": 10,
    },
    "timesteps": 4,
    "max_wall_hours": 6,
}


def named_config(name: str) -> dict[str, Any]:
    key = str(name).strip().lower()
    table = {"smoke": SMOKE, "pilot": PILOT, "long_poc": LONG_POC, "research_poc": RESEARCH_POC}
    if key not in table:
        raise ValueError(f"unknown sb3 config {name!r}; expected smoke|pilot|long_poc|research_poc")
    return dict(table[key])
