"""Proxy corrector diagnostic unit tests (no future-target leakage)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "ml"))

from eplus_proxy_corrector_diagnostic import (  # noqa: E402
    FEATURE_COLS,
    FAMILY,
    PRODUCT_CLAIM,
    build_greybox_frame,
    run_proxy_corrector_bakeoff,
)


def test_features_exclude_future_measured_targets():
    assert "target_kw" not in FEATURE_COLS
    assert "observed_kw" not in FEATURE_COLS


def test_proxy_corrector_bakeoff_forward_winter():
    idx = pd.date_range("2025-08-01", periods=300 * 24, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "interval_end_utc": idx,
            "observed_kw": 40 + (idx.hour * 2) + (idx.dayofweek >= 5) * -10,
            "simulated_kw": 30 + (idx.hour * 3),
        }
    )
    out = run_proxy_corrector_bakeoff(df, evaluate_winter=True)
    assert out["family_label"] == FAMILY == "EPLUS_PROXY_CORRECTOR_DIAGNOSTIC"
    assert out["product_claim"] == PRODUCT_CLAIM == "DIAGNOSTIC_ONLY"
    assert out["nested_chronological_cv"] is False
    assert out["is_plant_translator"] is False
    assert out["operational_dsm_readiness"] == "NO-GO"
    assert out["champion"] is not None
    assert out["leaderboard_chrono_val"]
    winter = out["locked_winter_holdout"]
    assert winter is not None
    assert winter.get("trained_on_feb_mar_before_january") is False
    assert "day_level_peaks" in winter
