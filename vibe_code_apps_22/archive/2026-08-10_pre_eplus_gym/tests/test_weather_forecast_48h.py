"""48h forecast → 96-step weather contract."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP / "ml"))

from weather_forecast_48h import (  # noqa: E402
    STEPS_15,
    hourly_to_15min,
    synthetic_hourly_48,
    weather_forecast_from_hourly48,
)


def test_hourly_to_15min_length():
    h = list(range(24))
    out = hourly_to_15min(h, STEPS_15)
    assert len(out) == 96
    assert out[0] == 0 and out[3] == 0 and out[4] == 1


def test_synthetic_forecast_builds_96():
    hourly = synthetic_hourly_48(seed=1, mean_f=5.0)
    assert len(hourly["oat_f"]) == 48
    wx = weather_forecast_from_hourly48(hourly, hours=24)
    assert len(wx["oat_f"]) == 96
    assert len(wx["rh_pct"]) == 96
    assert wx["source"] == "synthetic"
    assert np.isfinite(wx["oat_f"]).all() if hasattr(np, "isfinite") else True


def test_48h_block_has_192_steps():
    hourly = synthetic_hourly_48(seed=2)
    wx = weather_forecast_from_hourly48(hourly, hours=48)
    assert wx["n_steps"] == 192
    assert len(wx["oat_f"]) == 192
