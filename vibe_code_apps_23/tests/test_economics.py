from __future__ import annotations

import pytest

from vibe23.economics import (
    LifecycleAssumptions,
    default_day_type_weights,
    distribution_bands,
    lifecycle_report,
    methods_appendix_markdown,
    price_discovery_summary,
    required_incentive_per_kwh_shed,
    residential_day_value_stack,
    tornado_one_at_a_time,
    weighted_annual_from_days,
)
from vibe23.economics.lifecycle import effective_capex


def test_required_incentive_accounts_for_existing_tou():
    out = required_incentive_per_kwh_shed(
        target_usd_per_event=5.0,
        kwh_shed=2.5,
        existing_tou_savings_usd=0.5,
    )
    assert out["required_usd_per_kwh_shed"] == pytest.approx(1.8)


def test_price_discovery_and_value_stack():
    disc = price_discovery_summary(
        kwh_shed=2.0,
        event_hours=5.0,
        tou_savings_usd=0.8,
        capacity_kwh=13.5,
        eta_rt=0.9025,
        net_capex_usd=9800.0,
        off_peak=0.08,
    )
    assert disc["avg_kw_shed"] == pytest.approx(0.4)
    assert len(disc["incentive_table"]) == 3
    assert disc["bess_arbitrage_breakeven"]["required_peak_usd_per_kwh"] > 0.08
    stack = residential_day_value_stack(
        tou_arbitrage_usd=1.2,
        dr_incentive_usd=5.0,
        include_dr_incentive=True,
        resilience_usd=10.0,
        include_resilience=False,
    )
    assert stack["total_usd"] == pytest.approx(6.2)


def test_lifecycle_rejects_unguarded_tax_credit():
    with pytest.raises(ValueError, match="tax credit"):
        LifecycleAssumptions(net_capex_usd=10000, annual_arbitrage_usd=500, tax_credit_frac=0.3)


def test_lifecycle_payback_and_npv():
    a = LifecycleAssumptions(
        net_capex_usd=10000.0,
        annual_arbitrage_usd=2000.0,
        discount_rate=0.0,
        lifetime_years=10,
        warranty_years=10,
        annual_degradation_frac=0.0,
        throughput_kwh_per_year=3000.0,
    )
    report = lifecycle_report(a)
    assert effective_capex(a) == 10000.0
    assert report["simple_payback_years"] == pytest.approx(5.0)
    assert report["npv_usd"] == pytest.approx(10000.0)  # 10*2000 - 10000
    assert report["lcos_usd_per_kwh"] is not None


def test_weighted_annual_not_365x_and_tornado():
    weights = default_day_type_weights()
    assert abs(sum(weights.values()) - 365.0) < 1e-6
    days = {
        "summer_hot": 2.0,
        "summer_typical": 0.5,
        "winter_design": 4.0,
        "winter_typical": 1.0,
        "shoulder": 0.2,
    }
    annual = weighted_annual_from_days(days, weights)
    naive = 2.0 * 365
    assert annual["annual_usd"] < naive
    bands = distribution_bands([0.2, 0.5, 1.0, 2.0, 4.0])
    assert bands["p10_usd"] <= bands["p50_usd"] <= bands["p90_usd"]

    def evaluate(params):
        return float(params["spread"]) * float(params["cycles"]) - float(params["capex"]) * 0.01

    tornado = tornado_one_at_a_time(
        {"spread": 0.2, "cycles": 250.0, "capex": 9800.0},
        evaluate=evaluate,
    )
    assert tornado["bars"][0]["swing_usd"] >= tornado["bars"][-1]["swing_usd"]


def test_methods_appendix_contains_claims():
    md = methods_appendix_markdown(
        day={"label": "test", "baseline_daily_kwh": 28.0},
        equipment={"internal_gains": "diurnal"},
        economics={"note": "ILLUSTRATIVE"},
    )
    assert "HYPOTHETICAL_GL14_TUNED_DEMO_MODEL" in md
    assert "ILLUSTRATIVE" in md
    assert "28.0" in md
