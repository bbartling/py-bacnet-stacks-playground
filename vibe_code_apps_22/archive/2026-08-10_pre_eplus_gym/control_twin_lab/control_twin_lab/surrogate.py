"""W2A plant-electric surrogate — SYNTHETIC provenance only."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from .seed import HONESTY_LAB, PROMOTE, PROVENANCE

FEATURE_COLS = [
    "oat_f",
    "hdd65",
    "timestamp_step",
    "sin_step",
    "cos_step",
    "pre_roll_days",
    "steps_per_hour",
    "strategy_baseline",
    "strategy_stagger_preheat",
    "strategy_deep_setback",
    "strategy_flat_24_7",
    "strategy_prbs",
]


def _featurize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["hdd65"] = np.maximum(0.0, 65.0 - out["oat_f"].to_numpy(dtype=float))
    step = out["timestamp_step"].to_numpy(dtype=float)
    out["sin_step"] = np.sin(2 * np.pi * step / 96.0)
    out["cos_step"] = np.cos(2 * np.pi * step / 96.0)
    for s in (
        "baseline",
        "stagger_preheat",
        "deep_setback",
        "flat_24_7",
        "prbs",
    ):
        out[f"strategy_{s}"] = (out["strategy"].astype(str) == s).astype(float)
    return out


def train_surrogate(frames: list[pd.DataFrame]) -> tuple[Any, dict[str, Any]]:
    if not frames:
        raise ValueError("no frames for surrogate")
    df = _featurize(pd.concat(frames, ignore_index=True))
    for c in FEATURE_COLS:
        if c not in df.columns:
            df[c] = 0.0
    X = df[FEATURE_COLS].to_numpy(dtype=float)
    y = df["p_hvac_kw"].to_numpy(dtype=float)
    n = len(y)
    split = max(1, int(n * 0.8))
    model = GradientBoostingRegressor(random_state=0, max_depth=3, n_estimators=80)
    model.fit(X[:split], y[:split])
    pred = model.predict(X[split:]) if split < n else model.predict(X)
    y_te = y[split:] if split < n else y
    mae = float(mean_absolute_error(y_te, pred))
    card = {
        "run_id": f"w2a_plant_surr_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "honesty": HONESTY_LAB,
        "provenance": PROVENANCE,
        "promote": PROMOTE,
        "physics_family": "W2A_PHYSICAL_DSM",
        "n_rows": int(n),
        "n_train": int(split),
        "holdout_mae_kw": mae,
        "feature_cols": FEATURE_COLS,
        "note": (
            "SYNTHETIC_W2A_PROVENANCE — trained on Control Twin Lab trajectories "
            "(staged A04 / smoke synthesizer). NOT Lakeside field compressor kW. "
            "NON_PROMOTABLE."
        ),
    }
    return model, card


def write_surrogate_card(path: Path, card: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(card, indent=2), encoding="utf-8")
