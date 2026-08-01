"""Canonical paths for demand_hourly joblib + model card (turnkey PA dump)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

_VIBE21 = Path(__file__).resolve().parents[1]
_FLASK_MODELS = _VIBE21 / "flask_app" / "models"

MODEL_STEM_V1 = "demand_hourly_v1"
MODEL_STEM_V2 = "demand_hourly_v2"
MODEL_STEM = MODEL_STEM_V2  # default dump stem for new trains
JOBLIB_NAME = f"{MODEL_STEM}.joblib"
CARD_NAME = f"{MODEL_STEM}_model_card.json"
TUNING_NAME = f"{MODEL_STEM}_tuning.json"


def vibe21_root() -> Path:
    return _VIBE21


def flask_models_dir() -> Path:
    """Default agent/CLI/notebook dump location (inside zip-ready flask_app)."""
    return _FLASK_MODELS


def wattlab_models_dir() -> Path:
    if Path("/data/runs").is_dir():
        return Path("/data") / "models"
    return Path.home() / "wattlab_workspace" / "models"


def default_model_dir() -> Path:
    """Prefer flask_app/models; create it if missing."""
    d = flask_models_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def artifact_paths(out_dir: Path | None = None, *, stem: str | None = None) -> tuple[Path, Path, Path]:
    d = out_dir or default_model_dir()
    d.mkdir(parents=True, exist_ok=True)
    s = stem or MODEL_STEM
    return d / f"{s}.joblib", d / f"{s}_model_card.json", d / f"{s}_tuning.json"


def resolve_load_paths() -> tuple[Path, Path]:
    """
    Loader order for Flask:
      1. VIBE21_MODEL_ARTIFACT + VIBE21_MODEL_CARD
      2. flask_app/models/demand_hourly_v2 (prefer)
      3. flask_app/models/demand_hourly_v1 (fallback)
      4. ~/wattlab_workspace/models/ (legacy v2 then v1)
    """
    env_art = os.environ.get("VIBE21_MODEL_ARTIFACT")
    env_card = os.environ.get("VIBE21_MODEL_CARD")
    if env_art and env_card:
        return Path(env_art), Path(env_card)

    for stem in (MODEL_STEM_V2, MODEL_STEM_V1):
        flask_art = _FLASK_MODELS / f"{stem}.joblib"
        flask_card = _FLASK_MODELS / f"{stem}_model_card.json"
        if flask_art.is_file() and flask_card.is_file():
            return flask_art, flask_card

    ws = wattlab_models_dir()
    for stem in (MODEL_STEM_V2, MODEL_STEM_V1):
        art = ws / f"{stem}.joblib"
        card = ws / f"{stem}_model_card.json"
        if art.is_file() and card.is_file():
            return art, card
    return ws / JOBLIB_NAME, ws / CARD_NAME


def mirror_to_wattlab(out_dir: Path, *, stem: str | None = None) -> None:
    """Optional copy of shipped artifacts into wattlab workspace."""
    dest = wattlab_models_dir()
    dest.mkdir(parents=True, exist_ok=True)
    s = stem or MODEL_STEM
    for name in (f"{s}.joblib", f"{s}_model_card.json", f"{s}_tuning.json"):
        src = out_dir / name
        if src.is_file():
            shutil.copy2(src, dest / name)
