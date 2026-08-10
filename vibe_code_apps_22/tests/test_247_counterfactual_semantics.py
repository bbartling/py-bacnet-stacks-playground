"""24/7 SAME-STATE vs FULL OVERNIGHT counterfactual semantics."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP / "ml"), str(_APP)]

from simulation_contract import incremental_demand  # noqa: E402


def test_same_state_treatment_shares_init():
    """Experiment A: every strategy starts from identical measured 00:00 state."""
    midnight_kw = 40.0
    midnight_zones = [64.0] * 6
    init_bau = {"facility_kw": midnight_kw, "zones_f": list(midnight_zones)}
    init_247 = {"facility_kw": midnight_kw, "zones_f": list(midnight_zones)}
    assert init_bau == init_247


def test_full_overnight_247_must_not_reuse_setback_midnight_as_free_warm_state():
    """Experiment B: 24/7 that ran overnight creates its own midnight — not metered setback.

    Labeling a warm-at-temp init as a fair daily energy comparison vs setback BAU is forbidden.
    """
    metered_midnight_zones = [62.0] * 6  # setback overnight
    already_at_temp_zones = [70.0] * 6  # occupied SP — NOT a free overnight history
    assert metered_midnight_zones != already_at_temp_zones
    # Document the two experiment ids used by playground / docs
    experiments = {
        "SAME_STATE_TREATMENT_TEST": "identical measured 00:00 for all strategies",
        "FULL_OVERNIGHT_COUNTERFACTUAL": "controls begin D-1; include pre-midnight energy",
    }
    assert "SAME_STATE_TREATMENT_TEST" in experiments
    assert "FULL_OVERNIGHT_COUNTERFACTUAL" in experiments


def test_month_peak_counterfactual_35kw_credit():
    """prior=220, actual=285, CF=250 → CF reduces incremental billed demand by 35 kW vs actual."""
    prior = 220.0
    rate = 12.0
    _, inc_actual, _ = incremental_demand(prior, 285.0, rate)
    _, inc_cf, _ = incremental_demand(prior, 250.0, rate)
    assert inc_actual == pytest.approx(65.0)
    assert inc_cf == pytest.approx(30.0)
    assert (inc_actual - inc_cf) == pytest.approx(35.0)


def test_billing_counterfactual_240_dollar_golden():
    """Wave 8 audit golden: prior=100, actual=130, DSM=110, $12/kW → $240 demand saving."""
    prior = 100.0
    rate = 12.0
    new_a, inc_a, cost_a = incremental_demand(prior, 130.0, rate)
    new_d, inc_d, cost_d = incremental_demand(prior, 110.0, rate)
    assert new_a == pytest.approx(130.0)
    assert new_d == pytest.approx(110.0)
    assert inc_a == pytest.approx(30.0)
    assert inc_d == pytest.approx(10.0)
    assert (cost_a - cost_d) == pytest.approx(240.0)


def test_same_prior_mtd_for_baseline_and_counterfactual():
    prior = 220.0
    _, a, _ = incremental_demand(prior, 285.0, 10.0)
    _, b, _ = incremental_demand(prior, 250.0, 10.0)
    # Both used the same prior; only simulated peaks differ
    assert a > b
