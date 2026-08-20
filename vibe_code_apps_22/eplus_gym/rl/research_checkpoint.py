"""Block-boundary SB3 checkpoints. Metadata-only JSON is not resumable."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from eplus_gym.rl.obs_v3 import N_OBS_V3, OBS_SCHEMA_V3
from eplus_gym.rl.research_spaces import (
    DECODER_VERSION_V2,
    RESEARCH_ACTION_CONTRACT_V2,
    ActionContractMismatch,
    assert_research_v2_contract,
)
from eplus_gym.site_pins import sha256_file

SCHEMA = "vibe22.research_checkpoint.v2"
OBS_DIM = N_OBS_V3


class CheckpointError(ValueError):
    """Checkpoint is missing, mismatched, or metadata-only."""


def _sha256(path: Path) -> str:
    return sha256_file(Path(path))


def checkpoint_resumable(manifest: Mapping[str, Any] | None, *, root: Path | None = None) -> bool:
    if not isinstance(manifest, Mapping):
        return False
    if str(manifest.get("schema") or "") != SCHEMA:
        return False
    zip_name = manifest.get("model_zip")
    if not zip_name:
        return False
    base = Path(root) if root is not None else Path(str(manifest.get("root") or "."))
    zpath = base / str(zip_name)
    if not zpath.is_file():
        return False
    want = str(manifest.get("model_sha256") or "")
    if not want or _sha256(zpath) != want:
        return False
    try:
        assert_research_v2_contract(manifest)
    except ActionContractMismatch:
        return False
    if int(manifest.get("observation_dim") or 0) != OBS_DIM:
        return False
    if str(manifest.get("observation_contract") or "") != OBS_SCHEMA_V3:
        return False
    algo = str(manifest.get("algo") or "").upper()
    if algo == "DQN":
        replay = base / str(manifest.get("replay_buffer") or "replay_buffer.pkl")
        if not replay.is_file():
            return False
    return True


def write_block_checkpoint(
    *,
    root: Path,
    model: Any,
    algo: str,
    seed: int,
    valid_transition_count: int,
    block_id: str,
    day: str | None,
    idf_sha256: str,
    epw_sha256: str,
    rng_hex: str,
) -> dict[str, Any]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    algo_u = str(algo).upper()
    zip_name = f"{algo_u.lower()}_block.zip"
    zpath = root / zip_name
    model.save(str(zpath))
    replay_name = None
    if algo_u == "DQN":
        replay_name = "replay_buffer.pkl"
        model.save_replay_buffer(str(root / replay_name))
    resume = (
        f"python scripts/vibe22_rl.py research-long --resume {root.as_posix()} "
        "--confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated"
    )
    body = {
        "schema": SCHEMA,
        "algo": algo_u,
        "seed": int(seed),
        "valid_transition_count": int(valid_transition_count),
        "block_id": str(block_id),
        "day": None if day is None else str(day)[:10],
        "action_contract_version": RESEARCH_ACTION_CONTRACT_V2,
        "decoder_version": DECODER_VERSION_V2,
        "observation_contract": OBS_SCHEMA_V3,
        "observation_dim": OBS_DIM,
        "idf_sha256": str(idf_sha256),
        "epw_sha256": str(epw_sha256),
        "model_zip": zip_name,
        "model_sha256": _sha256(zpath),
        "replay_buffer": replay_name,
        "rng": str(rng_hex),
        "utc": datetime.now(timezone.utc).isoformat(),
        "resume_command": resume,
        "long_campaign_allowed": False,
        "SIMULATION_TRAINING_READY": False,
        "OPERATIONAL_DSM_READY": False,
        "metadata_only": False,
    }
    (root / "checkpoint.json").write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return body


def load_checkpoint_manifest(root: Path) -> dict[str, Any]:
    path = Path(root) / "checkpoint.json"
    if not path.is_file():
        raise CheckpointError("missing checkpoint.json")
    body = json.loads(path.read_text(encoding="utf-8"))
    if not checkpoint_resumable(body, root=Path(root)):
        raise CheckpointError("checkpoint is not resumable (missing zip, hash, or contract mismatch)")
    return body


def refuse_metadata_only(manifest: Mapping[str, Any]) -> None:
    if not manifest.get("model_zip") or manifest.get("metadata_only") is True:
        raise CheckpointError("refusing metadata-only JSON as a checkpoint")


def rng_hex(*, seed: int, idf_sha256: str, epw_sha256: str, algo: str) -> str:
    payload = f"research-long:{algo}:{int(seed)}:{idf_sha256}:{epw_sha256}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def restore_checkpoint(
    root: Path,
    *,
    idf_sha256: str | None = None,
    epw_sha256: str | None = None,
) -> tuple[dict[str, Any], Any]:
    """Load SB3 zip (+ DQN replay). Refuse metadata-only JSON or hash/contract mismatch."""
    body = load_checkpoint_manifest(root)
    refuse_metadata_only(body)
    if idf_sha256 is not None and str(body.get("idf_sha256")) != str(idf_sha256):
        raise CheckpointError("idf sha256 mismatch; refusing resume")
    if epw_sha256 is not None and str(body.get("epw_sha256")) != str(epw_sha256):
        raise CheckpointError("epw sha256 mismatch; refusing resume")
    from eplus_gym.rl.research_eval import load_sb3_model

    zpath = Path(root) / str(body["model_zip"])
    model = load_sb3_model(zpath, algo=str(body.get("algo") or "PPO"), contract=body)
    if str(body.get("algo") or "").upper() == "DQN":
        replay = Path(root) / str(body.get("replay_buffer") or "replay_buffer.pkl")
        if not replay.is_file():
            raise CheckpointError("DQN resume requires replay_buffer.pkl")
        if hasattr(model, "load_replay_buffer"):
            model.load_replay_buffer(str(replay))
    return body, model
