"""ARCHIVED — do not import. Legacy hybrid calendar features (pre-interval15).

Bug: hour_ending = step/4.0 → prediction step 0 encoded as 0.0 instead of 0.25.
"""
from __future__ import annotations

import numpy as np


def _calendar_features(step: int, meta: dict) -> dict[str, float]:
    hour = step / 4.0
    occupied = float(meta.get("occupied_schedule", [0.0] * 96)[step])
    return {
        "step_15": float(step),
        "sin_step": float(np.sin(2 * np.pi * step / 96.0)),
        "cos_step": float(np.cos(2 * np.pi * step / 96.0)),
        "hour_ending": float(hour),
        "month": float(meta.get("month", 1)),
        "doy": float(meta.get("doy", 1)),
        "is_weekend": float(meta.get("is_weekend", 0)),
        "occupied": occupied,
        "hours_to_occupy": float(max(0.0, (28 - step) / 4.0)),
    }
