"""Canonical paths for heating DSM joblib / ONNX / model cards + site data.

Production train data: native EnergyPlus farm only (``ENERGYPLUS_NATIVE_RUN``).
No bootstrap / physics-proxy fallback.
"""
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
EPLUS_FARM_PARQUET = "heating_dsm_eplus_farm_hourly.parquet"

# Back-compat aliases
vibe22_root = app_root
lakeside_data_root = site_root
creekside_data_root = site_root  # legacy


def default_artifact_dir() -> Path:
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    return _ARTIFACTS


def train_parquet_path(*, prefer_eplus_farm: bool = True) -> Path:
    """Require native E+ farm parquet with ``ENERGYPLUS_NATIVE_RUN`` provenance."""
    art = default_artifact_dir()
    farm = art / EPLUS_FARM_PARQUET
    if prefer_eplus_farm and farm.is_file():
        summary = art / "eplus_farm_summary.json"
        if not summary.is_file():
            raise FileNotFoundError(
                f"missing {summary} — run scripts/eplus_heating_dsm_farm.py"
            )
        import json

        s = json.loads(summary.read_text(encoding="utf-8"))
        prov = str(s.get("provenance", ""))
        if prov != "ENERGYPLUS_NATIVE_RUN":
            raise FileNotFoundError(
                f"farm parquet present but provenance={prov!r}; need ENERGYPLUS_NATIVE_RUN"
            )
        return farm
    ext = os.environ.get("VIBE22_TRAIN_PARQUET") or os.environ.get("LAKESIDE_TRAIN_PARQUET")
    if ext and Path(ext).is_file():
        # Still require native stamp in the frame when an override path is set
        import pandas as pd

        df = pd.read_parquet(ext)
        if "provenance" in df.columns and len(df):
            src = str(df["provenance"].iloc[0])
            if src != "ENERGYPLUS_NATIVE_RUN":
                raise FileNotFoundError(
                    f"override parquet provenance={src!r}; need ENERGYPLUS_NATIVE_RUN"
                )
        return Path(ext)
    raise FileNotFoundError(
        f"missing native farm {farm} — run: python -u scripts/eplus_heating_dsm_farm.py --smoke|--medium"
    )


def artifact_paths(out_dir: Path | None = None) -> dict[str, Path]:
    d = out_dir or default_artifact_dir()
    d.mkdir(parents=True, exist_ok=True)
    return {
        "joblib": d / JOBLIB_NAME,
        "card": d / CARD_NAME,
        "onnx": d / ONNX_NAME,
        "feature_meta": d / FEATURE_META_NAME,
        "champion_summary": d / CHAMPION_SUMMARY,
        "eplus_farm": d / EPLUS_FARM_PARQUET,
        "figures": d / "figures",
    }


__all__ = [
    "artifact_paths",
    "train_parquet_path",
    "lakeside_data_root",
    "creekside_data_root",
    "default_artifact_dir",
    "demand_hourly_csv",
    "site_root",
    "vibe22_root",
    "weather_history_csv",
]
