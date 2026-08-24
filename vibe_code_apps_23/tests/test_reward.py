from __future__ import annotations

import pytest

from vibe23.reward import ComfortContract, OperatorPayPolicy, score_operator_pay_day
from vibe23.tariff import BillingState, TariffEvidence, TariffScenario


def _tariff() -> TariffScenario:
    return TariffScenario.flat(
        tariff_id="illustrative", evidence=TariffEvidence.ILLUSTRATIVE, energy_rate_per_kwh=0.10, demand_rate_per_kw=10
    )


def _zones(value: float) -> dict[str, list[float]]:
    return {"North": [value] * 96, "South": [value] * 96}


def _comfort() -> ComfortContract:
    return ComfortContract(
        readiness_steps=(28, 29),
        occupied_steps=tuple(range(28, 68)),
        low_f=68.0,
        high_f=74.0,
        required_zone_names=("North", "South"),
    )


def test_operator_pay_reward_is_paired_and_separates_paycheck_from_training_reward() -> None:
    result = score_operator_pay_day(
        candidate_kw=[90.0] * 96,
        baseline_kw=[100.0] * 96,
        candidate_zone_temperatures_f=_zones(70.0),
        comfort=_comfort(),
        tariff=_tariff(),
        opening_billing_state=BillingState(month_to_date_peak_kw=105.0),
        policy=OperatorPayPolicy(savings_multiplier=2.0),
        candidate_schedules={"heating": [68.0] * 48 + [70.0] * 48},
    )
    assert result.readiness_ok
    assert result.savings_usd == pytest.approx(24.0)
    assert result.display_paycheck_usd == pytest.approx(148.0)
    assert result.training_reward == pytest.approx(0.23957894736842103)
    assert result.labels["paycheck"].startswith("ILLUSTRATIVE")
    assert result.action_smoothness == pytest.approx(2.0 / 95.0)


def test_readiness_failure_zeroes_paycheck_and_forbids_missing_baseline() -> None:
    zones = _zones(70.0)
    zones["North"][28] = 66.0
    result = score_operator_pay_day(
        candidate_kw=[90.0] * 96,
        baseline_kw=[100.0] * 96,
        candidate_zone_temperatures_f=zones,
        comfort=_comfort(),
        tariff=_tariff(),
        opening_billing_state=BillingState(),
    )
    assert not result.readiness_ok
    assert result.display_paycheck_usd == 0.0
    assert result.training_reward < -20.0
    with pytest.raises(ValueError, match="candidate-as-baseline"):
        score_operator_pay_day(
            candidate_kw=[90.0] * 96,
            baseline_kw=None,
            candidate_zone_temperatures_f=_zones(70.0),
            comfort=_comfort(),
            tariff=_tariff(),
            opening_billing_state=BillingState(),
        )


def test_nonfinite_schedule_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="finite values"):
        score_operator_pay_day(
            candidate_kw=[90.0] * 96,
            baseline_kw=[100.0] * 96,
            candidate_zone_temperatures_f=_zones(70.0),
            comfort=_comfort(),
            tariff=_tariff(),
            opening_billing_state=BillingState(),
            candidate_schedules={"heating": [68.0] * 95 + [float("nan")]},
        )
