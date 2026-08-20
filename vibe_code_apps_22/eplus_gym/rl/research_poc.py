"""Bounded simulation-only research PoC. Never sets long_campaign_allowed."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from eplus_gym.rl.multiday_env import FakeContinuityPlant, assert_live_campaign_plant
from eplus_gym.rl.research_model import ResearchModelError, verify_research_model

CLAIM_LABELS = (
    "SIMULATION_ONLY_RESEARCH_POC",
    "NOT VALIDATED FOR OPERATIONAL DSM",
    "NO BACNET COMMAND AUTHORITY",
    "A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED",
)
CHECKPOINT_KEYS = ("rng", "valid_transition_count", "idf_sha256", "epw_sha256", "episode_block")


class ResearchPocError(ValueError):
    """Research PoC refused."""


def reject_candidate_as_baseline(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> None:
    c = str(candidate.get("sha") or candidate.get("trajectory_sha256") or "")
    b = str(baseline.get("sha") or baseline.get("trajectory_sha256") or "")
    if not c or not b or c == b:
        raise ValueError("candidate-as-baseline is forbidden")


def new_checkpoint(
    *,
    seed: int,
    valid_transition_count: int,
    idf_sha256: str,
    epw_sha256: str,
    episode_block: str = "research_poc",
) -> dict[str, Any]:
    rng = hashlib.sha256(f"research-poc:{int(seed)}:{idf_sha256}:{epw_sha256}".encode("utf-8")).hexdigest()
    return {
        "rng": rng,
        "valid_transition_count": int(valid_transition_count),
        "idf_sha256": str(idf_sha256),
        "epw_sha256": str(epw_sha256),
        "episode_block": str(episode_block),
        "seed": int(seed),
        "utc": datetime.now(timezone.utc).isoformat(),
    }


def checkpoint_complete(ckpt: Mapping[str, Any] | None) -> bool:
    if not isinstance(ckpt, Mapping):
        return False
    return all(ckpt.get(k) not in (None, "", []) for k in CHECKPOINT_KEYS)


def refuse_fake_plant(plant: Any) -> None:
    if isinstance(plant, FakeContinuityPlant) or getattr(plant, "TEST_DOUBLE", False):
        raise ValueError("campaign paths refuse FakeContinuityPlant; EnergyPlusContinuityPlant required")
    assert_live_campaign_plant(plant)


def run_research_poc(
    *,
    app_root: Path,
    site_root: Path,
    confirm_simulation_only_physics_limits: bool,
    max_wall_hours: float,
    seed: int = 0,
) -> dict[str, Any]:
    if not confirm_simulation_only_physics_limits:
        raise ResearchPocError("missing --confirm-simulation-only-physics-limits")
    if float(max_wall_hours) > 6.0 + 1e-9:
        raise ResearchPocError("research PoC wall clock cap is 6 hours")
    manifest = verify_research_model(app_root)
    if manifest.get("long_campaign_allowed") is True:
        raise ResearchModelError("research contract must not set long_campaign_allowed=true")
    return {
        "command": "research-poc",
        "allowed": True,
        "research_poc_allowed": True,
        "simulation_training_ready": False,
        "operational_dsm_ready": False,
        "long_campaign_allowed": False,
        "max_wall_hours": float(max_wall_hours),
        "claim_labels": list(CLAIM_LABELS),
        "model_id": manifest.get("model_id"),
        "site_root": str(site_root),
        "seed": int(seed),
        "bacnet_commands": 0,
    }
