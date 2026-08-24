"""Fail-closed paired-comparison gates for baseline-contract repair."""
from __future__ import annotations

import pytest

from eplus_gym.rl.paired_comparison import (
    PairedComparisonError,
    assert_pair_compatible,
    demand_floor_must_be_explicit,
    native_and_gym_must_not_share_contract_id,
    refuse_cross_experiment_peak_delta,
)


def _meta(**overrides):
    base = {
        "idf_sha256": "aaa",
        "epw_sha256": "bbb",
        "target_date": "2026-01-26",
        "baseline_contract_name": "OBSERVED_BAS_INCUMBENT_V2",
        "baseline_contract_sha256": "ccc",
        "action_contract_version": "research_v3",
        "heating_schedule_fingerprint": "fp1",
        "energyplus_version": "26.1.0",
        "demand_interval": "15min",
        "lookback_dates": ["2026-01-25"],
        "tariff_mode": "FLAT_PLUS_DEMAND",
        "opening_mtd_kw": 0.0,
    }
    base.update(overrides)
    return base


def test_native_and_gym_cannot_share_contract_id():
    with pytest.raises(PairedComparisonError):
        native_and_gym_must_not_share_contract_id(
            "A04_NATIVE_CALIBRATION_REFERENCE",
            "A04_NATIVE_CALIBRATION_REFERENCE",
        )
    native_and_gym_must_not_share_contract_id(
        "A04_NATIVE_CALIBRATION_REFERENCE",
        "OBSERVED_BAS_INCUMBENT_V2",
    )


def test_different_dates_refuse_peak_delta():
    a = _meta(target_date="2026-01-26")
    b = _meta(target_date="2025-12-20")
    with pytest.raises(PairedComparisonError, match="target_date"):
        refuse_cross_experiment_peak_delta(
            peak_a=285.0,
            peak_b=211.0,
            meta_a=a,
            meta_b=b,
            claim="DQN reduced 285 kW to 211 kW",
        )


def test_different_baseline_hashes_refuse():
    a = _meta(baseline_contract_sha256="hash_a")
    b = _meta(baseline_contract_sha256="hash_b")
    with pytest.raises(PairedComparisonError, match="baseline_contract_sha256"):
        assert_pair_compatible(a, b, context="scorecard")


def test_compatible_pair_passes():
    a = _meta()
    b = _meta()
    assert_pair_compatible(a, b)


def test_demand_floor_never_silent_zero():
    with pytest.raises(PairedComparisonError):
        demand_floor_must_be_explicit(None, allow_zero_with_disclosure=True)
    with pytest.raises(PairedComparisonError):
        demand_floor_must_be_explicit(0.0, allow_zero_with_disclosure=False)
    demand_floor_must_be_explicit(0.0, allow_zero_with_disclosure=True)
    demand_floor_must_be_explicit(50.0, allow_zero_with_disclosure=False)


def test_285_to_x_requires_same_day_same_baseline():
    a = _meta(
        target_date="2026-01-26",
        baseline_contract_name="A04_NATIVE_CALIBRATION_REFERENCE",
    )
    b = _meta(
        target_date="2025-12-31",
        baseline_contract_name="OBSERVED_BAS_INCUMBENT_V2",
    )
    with pytest.raises(PairedComparisonError, match="Refusing peak delta"):
        refuse_cross_experiment_peak_delta(
            peak_a=285.0,
            peak_b=220.0,
            meta_a=a,
            meta_b=b,
            claim="Grid reduced 285 to 220",
        )
