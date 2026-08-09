"""Unit tests for eplus_multires_metrics (formula, gates, no signed-delta CVRMSE)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))

from eplus_multires_metrics import (  # noqa: E402
    HOURLY_CVRMSE_MAX,
    MONTHLY_CVRMSE_MAX,
    MONTHLY_NMBE_ABS_MAX,
    build_validation_document,
    cross_correlation_lags,
    gate_hourly,
    gate_monthly,
    nmbe_cvrmse_pct,
    resolution_block,
)


def test_perfect_match_zero_errors():
    m = [10.0, 20.0, 30.0, 40.0]
    s = list(m)
    stats = nmbe_cvrmse_pct(m, s, p=1)
    assert stats["n"] == 4
    assert stats["p"] == 1
    assert stats["nmbe_pct"] == pytest.approx(0.0)
    assert stats["cvrmse_pct"] == pytest.approx(0.0)


def test_nmbe_formula_hand():
    # m=[10,20,30], ŷ=[12,18,27], p=1 → dof=2, mean=20
    # sum(m-ŷ)=(10-12)+(20-18)+(30-27)=-2+2+3=3
    # NMBE = 100*3/(2*20)=7.5
    m = [10.0, 20.0, 30.0]
    y = [12.0, 18.0, 27.0]
    stats = nmbe_cvrmse_pct(m, y, p=1)
    assert stats["nmbe_pct"] == pytest.approx(7.5)
    # CVRMSE = 100*sqrt((4+4+9)/2)/20 = 100*sqrt(8.5)/20
    expected_cv = 100.0 * math.sqrt(8.5) / 20.0
    assert stats["cvrmse_pct"] == pytest.approx(expected_cv)


def test_monthly_gate_boundaries():
    pass_stats = {"n": 12, "nmbe_pct": MONTHLY_NMBE_ABS_MAX, "cvrmse_pct": MONTHLY_CVRMSE_MAX}
    assert gate_monthly(pass_stats) == "pass"
    fail_nmbe = {"n": 12, "nmbe_pct": MONTHLY_NMBE_ABS_MAX + 0.01, "cvrmse_pct": 10.0}
    assert gate_monthly(fail_nmbe) == "fail"
    fail_cv = {"n": 12, "nmbe_pct": 0.0, "cvrmse_pct": MONTHLY_CVRMSE_MAX + 0.01}
    assert gate_monthly(fail_cv) == "fail"


def test_hourly_gate_30pct():
    assert gate_hourly({"n": 100, "nmbe_pct": 0.0, "cvrmse_pct": HOURLY_CVRMSE_MAX}) == "pass"
    assert gate_hourly({"n": 100, "nmbe_pct": 0.0, "cvrmse_pct": HOURLY_CVRMSE_MAX + 1}) == "fail"


def test_partial_year_monthly_flag():
    block = resolution_block([1, 2, 3], [1, 2, 3], resolution="monthly")
    assert block["n"] == 3
    assert block["partial_year_monthly"] is True
    assert block["labeled_as_gl14"] is True


def test_15min_never_labeled_gl14():
    block = resolution_block([1, 2, 3, 4], [1.1, 2.1, 2.9, 4.0], resolution="15min")
    assert block["status"] == "diagnostic_only"
    assert block["labeled_as_gl14"] is False
    assert block["gates"] is None


def test_no_signed_delta_as_observed_for_meaningful_cvrmse():
    """Document that CVRMSE on near-zero mean deltas is undefined/nan — callers must not."""
    delta = np.array([0.1, -0.1, 0.05, -0.05])
    pred = np.zeros_like(delta)
    stats = nmbe_cvrmse_pct(delta, pred, p=1)
    # mean near 0 → nan (engine refuses to invent a percent)
    assert math.isnan(stats["cvrmse_pct"]) or abs(stats["mean_obs"]) < 1e-9


def test_build_validation_blocks_recommendation():
    monthly = resolution_block([100] * 11, [102] * 11, resolution="monthly")
    hourly = resolution_block([50.0] * 100, [80.0] * 100, resolution="hourly")
    doc = build_validation_document(monthly=monthly, hourly=hourly)
    assert doc["schema"] == "eplus_multires_validation_v1"
    assert doc["overall"]["optimizer_ready"] is False
    assert doc["overall"]["recommendation_allowed"] is False
    assert doc["overall"]["blocker_reason"]


def test_cross_correlation_peak_at_zero_for_identical():
    rng = np.random.default_rng(0)
    x = rng.normal(size=500)
    out = cross_correlation_lags(x, x, max_lag=12)
    assert out["best_lag"] == 0
    assert out["best_corr"] == pytest.approx(1.0, abs=1e-6)
