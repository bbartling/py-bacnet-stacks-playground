"""Canonical paths for vibe22 heating DSM artifacts + external Creekside data."""

from __future__ import annotations

import os
from pathlib import Path

_VIBE22 = Path(__file__).resolve().parents[1]
_ARTIFACTS = _VIBE22 / "ml" / "artifacts"

MODEL_STEM = "heating_dsm_hourly_v1"
JOBLIB_NAME = f"{MODEL_STEM}.joblib"
CARD_NAME = f"{MODEL_STEM}_model_card.json"
ONNX_NAME = f"{MODEL_STEM}.onnx"
FEATURE_META_NAME = f"{MODEL_STEM}_feature_meta.json"
CHAMPION_SUMMARY = "champion_summary.json"
BOOTSTRAP_PARQUET = "heating_dsm_bootstrap_hourly.parquet"
SAMPLE_PARQUET = "heating_dsm_bootstrap_sample.parquet"

# Default local historian / openfdd site (data stays outside this repo)
_DEFAULT_CREEKSIDE = Path(r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside")


def vibe22_root() -> Path:
    return _VIBE22


def default_artifact_dir() -> Path:
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    return _ARTIFACTS


def creekside_data_root() -> Path:
    """Resolve the site data directory (BAS reports, weather, E+ twin).

    Order:
      1. env ``VIBE22_CREEKSIDE_ROOT``
      2. sibling ``../sp_creekside`` if present
      3. default OneDrive testing path (author machine)
    """
    env = os.environ.get("VIBE22_CREEKSIDE_ROOT")
    if env:
        return Path(env)
    sibling = _VIBE22.parent.parent / "sp_creekside"
    # playground is Documents/...; sp_creekside is often under Desktop/testing
    candidates = [
        sibling,
        _VIBE22.parents[2] / "OneDrive" / "Desktop" / "testing" / "sp_creekside",
        _DEFAULT_CREEKSIDE,
    ]
    for c in candidates:
        if c.is_dir() and (c / "reports").is_dir():
            return c
    return Path(env) if env else _DEFAULT_CREEKSIDE


def demand_hourly_csv() -> Path:
    return creekside_data_root() / "reports" / "demand_vs_web_weather_hourly.csv"


def weather_history_csv() -> Path:
    return (
        creekside_data_root()
        / "clean_data"
        / "CREEKSIDE_ES"
        / "weather"
        / "history_wide.csv"
    )


def bootstrap_parquet_path(*, prefer_full: bool = True) -> Path:
    """Prefer full train parquet in artifacts; fall back to shipped sample."""
    full = default_artifact_dir() / BOOTSTRAP_PARQUET
    sample = _VIBE22 / "data" / "sample" / SAMPLE_PARQUET
    if prefer_full and full.is_file():
        return full
    # Also accept a full parquet copied from sp_creekside via env
    ext = os.environ.get("VIBE22_BOOTSTRAP_PARQUET")
    if ext and Path(ext).is_file():
        return Path(ext)
    creekside_full = creekside_data_root() / "ml" / "artifacts" / BOOTSTRAP_PARQUET
    if prefer_full and creekside_full.is_file():
        return creekside_full
    if sample.is_file():
        return sample
    return full


def artifact_paths(out_dir: Path | None = None) -> dict[str, Path]:
    d = out_dir or default_artifact_dir()
    d.mkdir(parents=True, exist_ok=True)
    return {
        "joblib": d / JOBLIB_NAME,
        "card": d / CARD_NAME,
        "onnx": d / ONNX_NAME,
        "feature_meta": d / FEATURE_META_NAME,
        "champion_summary": d / CHAMPION_SUMMARY,
        "bootstrap": d / BOOTSTRAP_PARQUET,
        "figures": d / "figures",
    }
