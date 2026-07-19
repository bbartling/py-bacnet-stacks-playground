"""Tests for the additive lifecycle finance extension (wattlab.finance)."""

from __future__ import annotations

import pytest

from wattlab.finance import (
    DEFAULT_GAS_CO2E_KG_PER_THERM,
    DEFAULT_GRID_CO2E_KG_PER_KWH,
    KWH_PER_THERM,
    OM_PROVENANCE_TIERS,
    discounted_payback_years,
    irr,
    lifecycle_metrics,
)


def _flat_row(**overrides):
    """25,000 kWh + 1,000 therms, no escalation/discount unless overridden."""
    kwargs = dict(
        measure_id="SCHED-1",
        implementation_cost_usd=12000.0,
        kwh_saved=25000.0,
        therms_saved=1000.0,
        elec_rate_usd_per_kwh=0.12,
        gas_rate_usd_per_therm=0.80,
        measure_life_years=10,
        discount_rate=0.0,
        escalation_rate=0.0,
    )
    kwargs.update(overrides)
    return lifecycle_metrics(**kwargs)


def test_lifecycle_basic_paybacks_and_roi():
    row = _flat_row()
    # 25000*0.12 + 1000*0.80 = 3800 USD/yr energy, no O&M.
    assert row["annual_energy_cost_saved_usd"] == pytest.approx(3800.0)
    assert row["annual_cost_saved_usd"] == pytest.approx(3800.0)
    assert row["simple_payback_years"] == pytest.approx(12000.0 / 3800.0, abs=0.01)
    assert row["energy_only_payback_years"] == row["simple_payback_years"]
    assert row["lifetime_savings_usd"] == pytest.approx(38000.0)
    assert row["roi_over_life"] == pytest.approx((38000.0 - 12000.0) / 12000.0, abs=1e-3)
    # At 0% discount, NPV = lifetime - cost and SIR = lifetime / cost.
    assert row["npv_usd"] == pytest.approx(26000.0)
    assert row["sir"] == pytest.approx(38000.0 / 12000.0, abs=1e-3)
    # Discounted payback at 0% equals simple payback.
    assert row["discounted_payback_years"] == pytest.approx(12000.0 / 3800.0, abs=0.01)


def test_lifecycle_om_split_and_energy_only_payback():
    row = _flat_row(om_savings_usd_per_year=1200.0, om_provenance="facility_validated")
    assert row["annual_om_saved_usd"] == pytest.approx(1200.0)
    assert row["annual_cost_saved_usd"] == pytest.approx(5000.0)
    assert row["simple_payback_years"] == pytest.approx(12000.0 / 5000.0, abs=0.01)
    # Energy-only payback ignores the O&M line entirely.
    assert row["energy_only_payback_years"] == pytest.approx(12000.0 / 3800.0, abs=0.01)
    assert row["om_provenance"] == "facility_validated"
    assert row["assumptions"]["om_escalated"] is False


def test_om_provenance_tiers_validated():
    for tier in OM_PROVENANCE_TIERS:
        assert _flat_row(om_provenance=tier)["om_provenance"] == tier
    with pytest.raises(ValueError, match="om_provenance"):
        _flat_row(om_provenance="vendor_brochure")


def test_irr_matches_annuity_hand_check():
    # 1000 cost, 500/yr for 3 years: annuity factor 2.0 -> IRR ~23.38%.
    rate = irr([500.0, 500.0, 500.0], 1000.0)
    assert rate == pytest.approx(0.2338, abs=0.001)
    # Never-recovered cost has no IRR.
    assert irr([10.0], 1000.0) is None
    row = _flat_row(measure_life_years=10)
    # 3800/yr on 12000: IRR well above 25%.
    assert row["irr"] is not None and row["irr"] > 0.25


def test_discounted_payback_with_discounting():
    # 1000 cost, 600/yr, 10% discount: PV years are 545.45, 495.87 ->
    # crossing during year 2 at 1 + (1000-545.45)/495.87.
    got = discounted_payback_years([600.0, 600.0, 600.0], 1000.0, 0.10)
    assert got == pytest.approx(1 + (1000.0 - 600.0 / 1.1) / (600.0 / 1.1**2), abs=1e-6)
    assert discounted_payback_years([10.0, 10.0], 1000.0, 0.10) is None


def test_cost_of_conserved_energy_and_intensity_metrics():
    row = _flat_row(floor_area_ft2=50000.0)
    kwh_equiv = 25000.0 + 1000.0 * KWH_PER_THERM
    # 0% discount -> CRF is 1/life.
    assert row["cost_of_conserved_energy_usd_per_kwh"] == pytest.approx(
        12000.0 / 10 / kwh_equiv, abs=1e-4
    )
    assert row["cost_usd_per_annual_kwh_saved"] == pytest.approx(12000.0 / kwh_equiv, abs=1e-4)
    assert row["cost_usd_per_ft2"] == pytest.approx(12000.0 / 50000.0, abs=1e-4)
    # Without floor area the intensity is None, not a guess.
    assert _flat_row()["cost_usd_per_ft2"] is None


def test_cce_uses_capital_recovery_factor_at_positive_discount():
    row = _flat_row(discount_rate=0.05)
    kwh_equiv = 25000.0 + 1000.0 * KWH_PER_THERM
    crf = 0.05 * 1.05**10 / (1.05**10 - 1)
    assert row["cost_of_conserved_energy_usd_per_kwh"] == pytest.approx(
        12000.0 * crf / kwh_equiv, abs=1e-4
    )


def test_co2e_avoided_uses_default_factors():
    row = _flat_row()
    expected_kg = 25000.0 * DEFAULT_GRID_CO2E_KG_PER_KWH + 1000.0 * DEFAULT_GAS_CO2E_KG_PER_THERM
    assert row["co2e_avoided_kg_per_year"] == pytest.approx(expected_kg, abs=0.1)
    assert row["co2e_avoided_metric_tons_over_life"] == pytest.approx(
        expected_kg * 10 / 1000.0, abs=0.01
    )
    # Custom factors flow through and are stamped in assumptions.
    custom = _flat_row(grid_co2e_kg_per_kwh=0.2, gas_co2e_kg_per_therm=5.0)
    assert custom["co2e_avoided_kg_per_year"] == pytest.approx(25000.0 * 0.2 + 1000.0 * 5.0)
    assert custom["assumptions"]["grid_co2e_kg_per_kwh"] == 0.2


def test_zero_savings_measure_degrades_gracefully():
    row = lifecycle_metrics(
        measure_id="DUD",
        implementation_cost_usd=5000.0,
        kwh_saved=0.0,
        therms_saved=0.0,
        measure_life_years=10,
    )
    assert row["simple_payback_years"] is None
    assert row["energy_only_payback_years"] is None
    assert row["discounted_payback_years"] is None
    assert row["irr"] is None
    assert row["cost_of_conserved_energy_usd_per_kwh"] is None
    assert row["co2e_avoided_kg_per_year"] == 0.0
