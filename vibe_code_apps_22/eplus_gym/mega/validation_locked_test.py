"""Phase 15: validation-only checkpoint selection + locked test policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

NO_PRISTINE_LOCKED_TEST = "NO_PRISTINE_LOCKED_TEST_AVAILABLE"
SCHEMA = "vibe22.mega.validation_locked_test.v1"


@dataclass
class ValidationSelectionResult:
    selected_ppo: str | None
    selected_dqn: str | None
    locked_test_status: str
    locked_test_ran: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "selected_ppo_policy": self.selected_ppo,
            "selected_dqn_policy": self.selected_dqn,
            "one_per_algo": True,
            "locked_test_status": self.locked_test_status,
            "locked_test_ran": self.locked_test_ran,
            "locked_test_runs_allowed": 1,
        }


def select_validation_checkpoints(
    eval_rows: Sequence[Mapping[str, Any]],
    *,
    locked_test_status: str = NO_PRISTINE_LOCKED_TEST,
) -> ValidationSelectionResult:
    def _best(algo: str) -> str | None:
        rows = [r for r in eval_rows if str(r.get("algo", "")).upper() == algo]
        if not rows:
            return None
        rows = sorted(
            rows,
            key=lambda r: (
                float(r.get("readiness_rate") or 0.0),
                float(r.get("mean_reward") or float("-inf")),
            ),
            reverse=True,
        )
        return str(rows[0].get("policy_id") or rows[0].get("arm"))

    ppo_winner = _best("PPO")
    dqn_winner = _best("DQN")
    ran = locked_test_status != NO_PRISTINE_LOCKED_TEST
    return ValidationSelectionResult(
        selected_ppo=ppo_winner,
        selected_dqn=dqn_winner,
        locked_test_status=locked_test_status,
        locked_test_ran=ran,
    )
