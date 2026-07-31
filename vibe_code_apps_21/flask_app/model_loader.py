"""Load trusted demand_hourly joblib + model card (no arbitrary uploads)."""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

_VIBE21 = Path(__file__).resolve().parents[1]
_ML = _VIBE21 / "ml"


def _workspace() -> Path:
    if Path("/data/runs").is_dir():
        return Path("/data")
    return Path.home() / "wattlab_workspace"


def default_artifact_paths() -> tuple[Path, Path]:
    env_art = os.environ.get("VIBE21_MODEL_ARTIFACT")
    env_card = os.environ.get("VIBE21_MODEL_CARD")
    if env_art and env_card:
        return Path(env_art), Path(env_card)
    ws = _workspace()
    return (
        ws / "models" / "demand_hourly_v1.joblib",
        ws / "models" / "demand_hourly_v1_model_card.json",
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@lru_cache(maxsize=1)
def load_bundle() -> dict[str, Any]:
    art, card_path = default_artifact_paths()
    if not art.is_file():
        raise FileNotFoundError(
            f"Model artifact missing: {art}. Set VIBE21_MODEL_ARTIFACT or train first."
        )
    if not card_path.is_file():
        raise FileNotFoundError(f"Model card missing: {card_path}")
    card = json.loads(card_path.read_text(encoding="utf-8"))
    digest = sha256_file(art)
    expected = card.get("artifact_sha256")
    if expected and expected.lower() != digest.lower():
        raise ValueError(
            f"Artifact hash mismatch: card={expected} file={digest}. Refusing load."
        )
    obj = joblib.load(art)
    # joblib may be {"model": ..., "feature_cols": ...} or bare estimator
    if isinstance(obj, dict) and "model" in obj:
        model = obj["model"]
        feature_cols = obj.get("feature_cols")
    else:
        model = obj
        feature_cols = None
    if feature_cols is None:
        import sys

        if str(_ML) not in sys.path:
            sys.path.insert(0, str(_ML))
        from feature_compile_dm import FEATURE_COLS  # noqa: WPS433

        feature_cols = list(FEATURE_COLS)
    return {
        "model": model,
        "feature_cols": list(feature_cols),
        "card": card,
        "artifact_path": str(art),
        "artifact_sha256": digest,
    }


def clear_bundle_cache() -> None:
    load_bundle.cache_clear()
