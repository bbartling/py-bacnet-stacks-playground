"""Grey-box translator unit tests (no future-target leakage)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "ml"))

from eplus_greybox_plant_translator import FEATURE_COLS, build_greybox_frame, run_greybox_bakeoff  # noqa: E402


def test_features_exclude_future_measured_targets():
    assert "target_kw" not in FEATURE_COLS
    assert "observed_kw" not in FEATURE_COLS


def test_greybox_bakeoff_runs_on_synthetic():
    idx = pd.date_range("2025-08-01", periods=200 * 24, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "interval_end_utc": idx,
            "observed_kw": 40 + (idx.hour * 2) + (idx.dayofweek >= 5) * -10,
            "simulated_kw": 30 + (idx.hour * 3),
        }
    )
    out = run_greybox_bakeoff(df, evaluate_winter=True)
    assert out["family_label"] == "EPLUS_GREYBOX_PLANT_TRANSLATOR"
    assert out["operational_dsm_readiness"] == "NO-GO"
    assert out["champion"] is not None
    assert out["leaderboard_chrono_val"]
