"""Phases 12–13: multi-seed training configuration (≥5 seeds each)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

MEGA_MIN_SEEDS = 5
Algo = Literal["DQN", "PPO"]


@dataclass
class MultiSeedPlan:
    algo: Algo
    seeds: list[int] = field(default_factory=lambda: list(range(MEGA_MIN_SEEDS)))
    transitions_per_seed: int = 8192
    contract: str = "research_action_contract_v2"

    def validate(self) -> None:
        if len(self.seeds) < MEGA_MIN_SEEDS:
            raise ValueError(f"{self.algo} requires ≥{MEGA_MIN_SEEDS} seeds, got {len(self.seeds)}")

    def policy_ids(self) -> list[str]:
        return [f"trained_{self.algo.lower()}_seed{s}" for s in self.seeds]

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema": "vibe22.mega.multi_seed.v1",
            "algo": self.algo,
            "seeds": self.seeds,
            "n_seeds": len(self.seeds),
            "transitions_per_seed": self.transitions_per_seed,
            "policy_ids": self.policy_ids(),
            "traceability": {
                "contract": self.contract,
                "full_episode_provenance": True,
            },
        }


def mega_training_bundle() -> dict[str, Any]:
    dqn = MultiSeedPlan("DQN")
    ppo = MultiSeedPlan("PPO")
    return {
        "schema": "vibe22.mega.multi_seed_bundle.v1",
        "dqn": dqn.to_dict(),
        "ppo": ppo.to_dict(),
        "min_seeds": MEGA_MIN_SEEDS,
    }
