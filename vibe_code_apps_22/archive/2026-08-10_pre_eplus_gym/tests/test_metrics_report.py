"""Unit tests for metrics_report helpers."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ML = Path(__file__).resolve().parents[1] / "ml"
sys.path.insert(0, str(_ML))

from metrics_report import (  # noqa: E402
    cv_rmse,
    daily_peak_errors,
    mae,
    nmbe,
    per_target_table,
    rmse,
    scalar_block,
)


def test_mae_rmse_units():
    y = np.array([10.0, 20.0, 30.0])
    p = np.array([12.0, 18.0, 33.0])
    # |2|+|2|+|3| = 7 → MAE 7/3
    assert mae(y, p) == pytest.approx(7.0 / 3.0)
    assert rmse(y, p) == pytest.approx(np.sqrt((4 + 4 + 9) / 3))


def test_cv_rmse_and_nmbe():
    y = np.array([100.0, 100.0, 100.0])
    p = np.array([110.0, 90.0, 100.0])
    assert cv_rmse(y, p) == pytest.approx(rmse(y, p) / 100.0)
    assert nmbe(y, p) == pytest.approx(0.0)  # mean bias 0
    assert cv_rmse(np.zeros(3), p) is None


def test_daily_peak_and_kwh():
    yt = np.zeros(96)
    yt[40] = 200.0
    yp = np.zeros(96)
    yp[41] = 200.0
    d = daily_peak_errors(yt, yp)
    assert d["daily_peak_mag_error_kw"] == pytest.approx(0.0)
    assert d["peak_timing_abs_error_steps"] == pytest.approx(1.0)
    assert d["daily_kwh_error"] == pytest.approx(0.0)


def test_per_target_table_seven_rows():
    yt = np.random.default_rng(1).normal(size=(100, 7))
    yp = yt + 0.5
    df = per_target_table(yt, yp, n_days=2)
    assert len(df) == 7
    assert df.iloc[0]["target"] == "facility_kw"
    assert "1F_A" in df["target"].tolist()
    blk = scalar_block(yt[:, 0], yp[:, 0])
    assert blk["n_obs"] == 100
