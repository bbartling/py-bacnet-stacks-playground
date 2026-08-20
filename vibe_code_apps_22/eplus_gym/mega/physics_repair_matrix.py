"""Phase 4: bounded physics-repair matrix with explicit caps."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from eplus_gym.mega._json import sha256_obj

SCHEMA = "vibe22.mega.physics_repair_matrix.v1"
MAX_PHYSICS_CANDIDATES = 12
MAX_REFINEMENT_ROUNDS = 3


@dataclass
class RepairAttempt:
    attempt_id: str
    child_name: str
    patch_summary: str
    idf_sha256: str
    outcome: str
    evidence_path: str | None = None
    registered_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "child_name": self.child_name,
            "patch_summary": self.patch_summary,
            "idf_sha256": self.idf_sha256,
            "outcome": self.outcome,
            "evidence_path": self.evidence_path,
            "registered_at_utc": self.registered_at_utc,
        }


@dataclass
class PhysicsRepairMatrix:
    max_candidates: int = MAX_PHYSICS_CANDIDATES
    max_refinement_rounds: int = MAX_REFINEMENT_ROUNDS
    attempts: list[RepairAttempt] = field(default_factory=list)

    def register_attempt(self, attempt: RepairAttempt) -> None:
        if len(self.attempts) >= self.max_candidates:
            raise ValueError(f"physics candidate cap {self.max_candidates} reached")
        self.attempts.append(attempt)

    @property
    def refinement_round(self) -> int:
        if not self.attempts:
            return 0
        return min(self.max_refinement_rounds, max(1, len(self.attempts) // 4))

    def promotion_eligible(self) -> bool:
        return any(a.outcome == "promotion_candidate" for a in self.attempts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "caps": {
                "max_physics_candidates": self.max_candidates,
                "max_refinement_rounds": self.max_refinement_rounds,
                "current_candidates": len(self.attempts),
                "refinement_round": self.refinement_round,
            },
            "attempts": [a.to_dict() for a in self.attempts],
            "retain_all_attempts": True,
        }

    def write(self, path: Path) -> dict[str, Any]:
        body = self.to_dict()
        body["matrix_sha256"] = sha256_obj(body)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        return body


def seed_matrix_from_phase2(
    *,
    phase2_diagnosis: dict[str, Any],
    child_campaign: dict[str, Any] | None = None,
) -> PhysicsRepairMatrix:
    matrix = PhysicsRepairMatrix()
    matrix.register_attempt(
        RepairAttempt(
            attempt_id="P4_BASELINE_A04",
            child_name="A04_IMMUTABLE_PARENT",
            patch_summary="No edits — Phase 2 root cause baseline",
            idf_sha256=str(phase2_diagnosis.get("parent_idf", {}).get("sha256", "")),
            outcome="baseline_structural_w2a_low_airflow",
            evidence_path="docs/audits/figures/vibe22_mega_phase2/phase2_w2a_diagnosis.json",
        )
    )
    hp67_sha = "pending_phase4_patch"
    hp67_outcome = "pending_energyplus_confirmation"
    hp67_evidence = None
    if child_campaign:
        hp67_sha = str(child_campaign.get("child_idf_sha256") or hp67_sha)
        hp67_evidence = "docs/audits/figures/a04_child_hp67_scaled_v1/campaign_summary.json"
        hp67_outcome = "LIVE_EPLUS_COMPLETE"
    matrix.register_attempt(
        RepairAttempt(
            attempt_id="P4_CAND_HP67_SCALE",
            child_name="a04_child_hp67_scaled_v1",
            patch_summary="Scale rated capacity+airflow+water by 67-HP split per zone",
            idf_sha256=hp67_sha,
            outcome=hp67_outcome,
            evidence_path=hp67_evidence,
        )
    )
    return matrix
