"""Tests for alignment contract, design-day filter, source separation, chrono splits."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "ml"))
sys.path.insert(0, str(_ROOT / "eplus_native"))
sys.path.insert(0, str(_ROOT))

from eplus_multires_metrics import (  # noqa: E402
    ShapeMismatchError,
    build_validation_document,
    nmbe_cvrmse_pct,
    resolution_block,
)
from eplus_validation_contract import (  # noqa: E402
    AlignmentError,
    chronological_splits,
    dedupe_eplus_stamps_keep_last,
    reject_shape_mismatch,
)


def test_shape_mismatch_rejects():
    with pytest.raises(ShapeMismatchError):
        nmbe_cvrmse_pct([1.0, 2.0, 3.0], [1.0, 2.0])


def test_reject_shape_mismatch_helper():
    with pytest.raises(AlignmentError):
        reject_shape_mismatch(np.array([1.0, 2.0]), np.array([1.0]))


def test_design_day_dedupe_keeps_last():
    df = pd.DataFrame(
        {
            "eplus_stamp": ["01/21  00:15:00", "01/21  00:30:00", "01/21  00:15:00"],
            "site_electric_proxy_kw": [10.0, 11.0, 99.0],
        }
    )
    out = dedupe_eplus_stamps_keep_last(df)
    assert len(out) == 2
    row = out[out["eplus_stamp"] == "01/21  00:15:00"].iloc[0]
    assert row["site_electric_proxy_kw"] == 99.0
    assert out.attrs["dedupe_dropped"] == 1


def test_utility_vs_interval_separation_in_document():
    util = resolution_block([100] * 10, [101] * 10, resolution="monthly", label_gl14=False)
    util["source_type"] = "utility_bill_monthly"
    interv = resolution_block([100] * 11, [103] * 11, resolution="monthly", label_gl14=False)
    interv["source_type"] = "interval_meter_monthly"
    hourly = resolution_block([50.0] * 100, [80.0] * 100, resolution="hourly")
    doc = build_validation_document(
        monthly_utility=util, monthly_interval=interv, hourly=hourly
    )
    assert doc["resolutions"]["monthly_utility"]["source_type"] == "utility_bill_monthly"
    assert doc["resolutions"]["monthly_interval"]["source_type"] == "interval_meter_monthly"
    assert doc["resolutions"]["monthly_interval"]["source_type"] != "utility_bill_monthly"
    assert doc["overall"]["recommendation_allowed"] is False
    assert doc["overall"]["operational_dsm_readiness"] == "BLOCKED"
    assert doc["resolutions"]["monthly_utility"]["labeled_as_gl14"] is False


def test_refuse_swapped_source_types():
    util = {"source_type": "interval_meter_monthly", "status": "pass", "n": 10}
    with pytest.raises(ValueError):
        build_validation_document(monthly_utility=util, hourly={"status": "fail", "n": 1})


def test_chronological_holdout_locked():
    idx = pd.date_range("2025-08-01", periods=330 * 24, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "interval_end_utc": idx,
            "observed_kw": 1.0,
            "simulated_kw": 1.1,
        }
    )
    periods = chronological_splits(df)
    assert periods["locked_winter_holdout"]["role"] == "locked_no_tuning_evaluate_once"
    assert periods["calibration_development"]["role"] == "tuning_allowed"
    assert periods["locked_winter_holdout"]["n"] > 0
    assert periods["annual_summer_generalization"]["n"] > 0
    assert periods["chronological_validation"]["excludes_post_january"] is True
    assert periods["post_holdout_generalization"]["role"] == "external_post_holdout_only"


def test_p_published_with_scores():
    stats = nmbe_cvrmse_pct([10, 20, 30], [12, 18, 27], p=1)
    assert stats["n"] == 3
    assert stats["p"] == 1
    assert "formula" in stats


def test_duplicate_utc_rejected_in_align(tmp_path):
    from eplus_validation_contract import align_interval

    m = pd.DataFrame(
        {
            "interval_end_utc": pd.to_datetime(
                ["2026-01-01T06:00:00Z", "2026-01-01T06:00:00Z"], utc=True
            ),
            "observed_kw": [1.0, 2.0],
        }
    )
    s = pd.DataFrame(
        {
            "interval_end_utc": pd.to_datetime(["2026-01-01T06:00:00Z"], utc=True),
            "simulated_kw": [1.5],
        }
    )
    with pytest.raises(AlignmentError):
        align_interval(m, s, meas_kw_col="observed_kw")
