from __future__ import annotations

import pytest

from vibe23.tariff import BillingState, TariffEvidence, TariffScenario, billing_cost, load_tariff


def test_illustrative_tariff_cannot_authorize_monetary_selection() -> None:
    tariff = TariffScenario.flat(
        tariff_id="scenario-flat", evidence=TariffEvidence.ILLUSTRATIVE, energy_rate_per_kwh=0.10, demand_rate_per_kw=12
    )
    assert not tariff.monetary_selection_authorized
    assert tariff.selection_label.startswith("PHYSICAL_RANKING_REQUIRED")


def test_verified_tariff_requires_account_binding() -> None:
    with pytest.raises(ValueError, match="account_period_binding"):
        TariffScenario.flat(
            tariff_id="missing-proof", evidence=TariffEvidence.VERIFIED, energy_rate_per_kwh=0.1
        )


def test_verified_tariff_accepts_complete_period_bound_evidence() -> None:
    tariff = TariffScenario.flat(
        tariff_id="verified-fixture",
        evidence=TariffEvidence.VERIFIED,
        energy_rate_per_kwh=0.1,
        source_reference="fixture-rate.pdf",
        source_sha256="a" * 64,
        account_period_binding="Fixture account and meter, 2019-01",
        effective_period="2019-01-01/2019-01-31",
    )
    assert tariff.monetary_selection_authorized


def test_billing_cost_uses_incremental_demand_from_opening_floor() -> None:
    tariff = TariffScenario.flat(
        tariff_id="candidate", evidence=TariffEvidence.CANDIDATE, energy_rate_per_kwh=0.10, demand_rate_per_kw=10
    )
    result = billing_cost([90.0] * 96, tariff=tariff, opening_state=BillingState(month_to_date_peak_kw=100.0))
    assert result["energy_kwh"] == 2160.0
    assert result["demand_cost_usd"] == 0.0
    result = billing_cost([110.0] * 96, tariff=tariff, opening_state=BillingState(month_to_date_peak_kw=100.0))
    assert result["incremental_demand_kw"] == 10.0
    assert result["demand_cost_usd"] == 100.0


def test_loader_refuses_unlabeled_tariff() -> None:
    with pytest.raises(ValueError, match="evidence"):
        load_tariff({"tariff_id": "oops", "energy_rate_per_kwh": 0.1})


def test_loader_refuses_schema_drift() -> None:
    with pytest.raises(ValueError, match="schema"):
        load_tariff(
            {
                "schema": "wrong",
                "tariff_id": "oops",
                "evidence": "ILLUSTRATIVE",
                "energy_rate_per_kwh": 0.1,
            }
        )
