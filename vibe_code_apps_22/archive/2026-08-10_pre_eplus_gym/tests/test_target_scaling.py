"""Unit tests for MultiTargetScaler."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ML = Path(__file__).resolve().parents[1] / "ml"
sys.path.insert(0, str(_ML))

from feature_compile_heating_dsm import TARGET_COLS  # noqa: E402
from target_scaling import (  # noqa: E402
    N_TARGETS,
    MultiTargetScaler,
    assert_output_order,
    assert_target_cols,
)


def test_target_cols_order_frozen():
    assert list(TARGET_COLS) == [
        "facility_kw",
        "zone_temp_1F_A_f",
        "zone_temp_1F_B_f",
        "zone_temp_1F_C_f",
        "zone_temp_1F_D_f",
        "zone_temp_2F_A_f",
        "zone_temp_2F_B_f",
    ]
    assert N_TARGETS == 7
    assert_target_cols(TARGET_COLS)


def test_round_trip_synthetic():
    rng = np.random.default_rng(0)
    # Distinct scales: kW tens, temps ~70
    y = np.column_stack(
        [
            rng.normal(80, 30, 200),
            rng.normal(68, 2, 200),
            rng.normal(67, 2, 200),
            rng.normal(66, 2, 200),
            rng.normal(65, 2, 200),
            rng.normal(69, 2, 200),
            rng.normal(70, 2, 200),
        ]
    )
    sc = MultiTargetScaler().fit(y[:150])  # train-only
    z = sc.transform(y[150:])
    assert z.shape == (50, 7)
    # Each column roughly zero-mean / unit-ish on train
    z_tr = sc.transform(y[:150])
    assert abs(z_tr.mean(axis=0)).max() < 1e-6
    back = sc.inverse_transform(z)
    assert back.shape == (50, 7)
    np.testing.assert_allclose(back, y[150:], rtol=1e-5, atol=1e-5)


def test_wrong_width_raises():
    sc = MultiTargetScaler().fit(np.zeros((10, 7)))
    with pytest.raises(ValueError, match="expected 7"):
        sc.transform(np.zeros((5, 3)))


def test_assert_output_order():
    assert_output_order(np.zeros((4, 7)))
    with pytest.raises(AssertionError):
        assert_output_order(np.zeros((4, 6)))


def test_to_from_dict():
    y = np.arange(70, dtype=float).reshape(10, 7)
    sc = MultiTargetScaler().fit(y)
    sc2 = MultiTargetScaler.from_dict(sc.to_dict())
    np.testing.assert_allclose(sc.transform(y), sc2.transform(y))
