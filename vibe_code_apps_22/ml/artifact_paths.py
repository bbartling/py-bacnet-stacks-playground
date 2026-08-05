"""Canonical paths for heating DSM joblib / ONNX / model cards + site data."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_VIBE22 = Path(__file__).resolve().parents[1]
if str(_VIBE22) not in sys.path:
    sys.path.insert(0, str(_VIBE22))

from lakeside.paths import (  # noqa: E402
    app_root,
    demand_hourly_csv,
    site_root,
    weather_history_csv,
)

_ARTIFACTS = _VIBE22 / "ml" / "artifacts"

MODEL_STEM = "heating_dsm_hourly_v1"
JOBLIB_NAME = f"{MODEL_STEM}.joblib"
CARD_NAME = f"{MODEL_STEM}_model_card.json"
ONNX_NAME = f"{MODEL_STEM}.onnx"
FEATURE_META_NAME = f"{MODEL_STEM}_feature_meta.json"
CHAMPION_SUMMARY = "champion_summary.json"
BOOTSTRAP_PARQUET = "heating_dsm_bootstrap_hourly.parquet"
EPLUS_FARM_PARQUET = "heating_dsm_eplus_farm_hourly.parquet"
SAMPLE_PARQUET = "heating_dsm_bootstrap_sample.parquet"

# Back-compat aliases
vibe22_root = app_root
lakeside_data_root = site_root
creekside_data_root = site_root  # legacy


def default_artifact_dir() -> Path:
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    return _ARTIFACTS


def train_parquet_path(*, prefer_eplus_farm: bool = True, allow_demo: bool | None = None) -> Path:
    """Prefer native E+ farm parquet. Bootstrap only when DEMO / NOT ENERGYPLUS is set."""
    if allow_demo is None:
        allow_demo = os.environ.get("LAKESIDE_DEMO_NOT_ENERGYPLUS", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
    art = default_artifact_dir()
    farm = art / EPLUS_FARM_PARQUET
    if prefer_eplus_farm and farm.is_file():
        summary = art / "eplus_farm_summary.json"
        if summary.is_file():
            import json

            s = json.loads(summary.read_text(encoding="utf-8"))
            prov = str(s.get("provenance", ""))
            if prov != "ENERGYPLUS_NATIVE_RUN" and not allow_demo:
                raise FileNotFoundError(
                    f"farm parquet present but provenance={prov!r}; "
                    "need ENERGYPLUS_NATIVE_RUN (or set LAKESIDE_DEMO_NOT_ENERGYPLUS=1)"
                )
        return farm
    ext = os.environ.get("VIBE22_TRAIN_PARQUET") or os.environ.get("LAKESIDE_TRAIN_PARQUET")
    if ext and Path(ext).is_file() and allow_demo:
        return Path(ext)
    if allow_demo:
        return bootstrap_parquet_path(prefer_full=True)
    raise FileNotFoundError(
        f"missing native farm {farm} — run: python -u scripts/eplus_heating_dsm_farm.py --smoke|--medium "
        "(bootstrap disabled in production; set LAKESIDE_DEMO_NOT_ENERGYPLUS=1 for DEMO only)"
    )


def bootstrap_parquet_path(*, prefer_full: bool = True) -> Path:
    """Prefer full train parquet in artifacts; fall back to shipped sample."""
    full = default_artifact_dir() / BOOTSTRAP_PARQUET
    sample = _VIBE22 / "data" / "sample" / SAMPLE_PARQUET
    if prefer_full and full.is_file():
        return full
    ext = os.environ.get("VIBE22_BOOTSTRAP_PARQUET") or os.environ.get("LAKESIDE_BOOTSTRAP_PARQUET")
    if ext and Path(ext).is_file():
        return Path(ext)
    site_full = site_root() / "ml" / "artifacts" / BOOTSTRAP_PARQUET
    if prefer_full and site_full.is_file():
        return site_full
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
        "eplus_farm": d / EPLUS_FARM_PARQUET,
        "figures": d / "figures",
    }


__all__ = [
    "artifact_paths",
    "bootstrap_parquet_path",
    "train_parquet_path",
    "lakeside_data_root",
    "creekside_data_root",
    "default_artifact_dir",
    "demand_hourly_csv",
    "site_root",
    "vibe22_root",
    "weather_history_csv",
]
