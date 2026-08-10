"""G14-style facility NMBE / CV(RMSE) helpers used in held-out recursive scores."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_ML = Path(__file__).resolve().parents[1] / "ml"
sys.path.insert(0, str(_ML))

from train_real_baseline_15min import facility_g14_metrics  # noqa: E402


def test_facility_g14_perfect_match():
    y = np.array([10.0, 20.0, 30.0, 40.0])
    g = facility_g14_metrics(y, y)
    assert g["facility_kw_cv_rmse"] == 0.0
    assert g["facility_kw_nmbe"] == 0.0


def test_facility_g14_biased_overpredict():
    y = np.array([100.0, 100.0, 100.0, 100.0])
    p = np.array([110.0, 110.0, 110.0, 110.0])
    g = facility_g14_metrics(y, p)
    assert g["facility_kw_nmbe"] is not None
    assert abs(float(g["facility_kw_nmbe"]) - 0.10) < 1e-9
    assert g["facility_kw_cv_rmse"] is not None
    assert float(g["facility_kw_cv_rmse"]) > 0.0
