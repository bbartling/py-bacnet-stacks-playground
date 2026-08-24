from __future__ import annotations

import hashlib

import pytest

from vibe23.grid import (
    CandidateEvaluation,
    FrozenExperimentState,
    GridDimension,
    enumerate_grid,
    rank_grid_candidates,
    rllib_energyplus_adapter_provenance,
    run_grid_search,
)
from vibe23.reward import ComfortContract, score_operator_pay_day
from vibe23.tariff import BillingState, TariffEvidence, TariffScenario


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _state(tariff: TariffScenario, billing_state: BillingState) -> FrozenExperimentState:
    return FrozenExperimentState(
        decision_day="2019-01-15",
        model_sha256=_sha("model"),
        weather_sha256=_sha("weather"),
        calibration_run_sha256=_sha("calibration"),
        initial_state_sha256=_sha("initial"),
        baseline_trajectory_sha256=_sha("baseline"),
        billing_state_sha256=billing_state.fingerprint(),
        tariff_sha256=tariff.fingerprint(),
        occupancy_calendar_sha256=_sha("calendar"),
        energyplus_version="24.2.0",
    )


def _reward(candidate_kw: float, tariff: TariffScenario, billing_state: BillingState):
    return score_operator_pay_day(
        candidate_kw=[candidate_kw] * 96,
        baseline_kw=[100.0] * 96,
        candidate_zone_temperatures_f={"zone": [70.0] * 96},
        comfort=ComfortContract(
            readiness_steps=(28,),
            occupied_steps=(28,),
            low_f=68.0,
            high_f=74.0,
            required_zone_names=("zone",),
        ),
        tariff=tariff,
        opening_billing_state=billing_state,
    )


def test_enumeration_is_deterministic_and_duplicate_free() -> None:
    dimensions = (GridDimension("occupied_heating_f", (68.0, 70.0)), GridDimension("recovery_minutes", (0, 60)))
    left = enumerate_grid(dimensions)
    right = enumerate_grid(dimensions)
    assert [candidate.to_dict() for candidate in left] == [candidate.to_dict() for candidate in right]
    assert len(left) == 4
    with pytest.raises(ValueError, match="duplicate"):
        GridDimension("x", (1, 1))


def test_grid_rejects_cross_state_and_candidate_tariff_ranks_physics() -> None:
    tariff = TariffScenario.flat(
        tariff_id="candidate", evidence=TariffEvidence.CANDIDATE, energy_rate_per_kwh=0.1
    )
    billing_state = BillingState()
    state = _state(tariff, billing_state)
    dimensions = (GridDimension("x", (1, 2)),)

    def simulator(candidate, frozen):
        reward = _reward(80.0 if candidate.action["x"] == 1 else 90.0, tariff, billing_state)
        return CandidateEvaluation(
            candidate_id=candidate.candidate_id,
            experiment_state_sha256=frozen.fingerprint(),
            tariff_sha256=tariff.fingerprint(),
            reward=reward,
            peak_kw=float(reward.candidate_billing["day_peak_kw"]),
            total_kwh=float(reward.candidate_billing["energy_kwh"]),
            simulator_provenance_sha256=_sha(f"simulator-{candidate.candidate_id}"),
        )

    results = run_grid_search(dimensions=dimensions, frozen_state=state, simulator=simulator)
    ranked = rank_grid_candidates(results, tariff=tariff)
    assert ranked["winner"] == results[0].candidate_id
    assert ranked["selection_objective"].startswith("PHYSICAL")

    def wrong_state(candidate, frozen):
        reward = _reward(90.0, tariff, billing_state)
        return CandidateEvaluation(
            candidate_id=candidate.candidate_id,
            experiment_state_sha256="0" * 64,
            tariff_sha256=tariff.fingerprint(),
            reward=reward,
            peak_kw=float(reward.candidate_billing["day_peak_kw"]),
            total_kwh=float(reward.candidate_billing["energy_kwh"]),
            simulator_provenance_sha256=_sha("wrong-state-simulator"),
        )

    with pytest.raises(ValueError, match="identical-state"):
        run_grid_search(dimensions=dimensions, frozen_state=state, simulator=wrong_state)

    another_tariff = TariffScenario.flat(
        tariff_id="another", evidence=TariffEvidence.CANDIDATE, energy_rate_per_kwh=0.2
    )

    def wrong_tariff(candidate, frozen):
        reward = _reward(90.0, another_tariff, billing_state)
        return CandidateEvaluation(
            candidate_id=candidate.candidate_id,
            experiment_state_sha256=frozen.fingerprint(),
            tariff_sha256=another_tariff.fingerprint(),
            reward=reward,
            peak_kw=float(reward.candidate_billing["day_peak_kw"]),
            total_kwh=float(reward.candidate_billing["energy_kwh"]),
            simulator_provenance_sha256=_sha("wrong-tariff-simulator"),
        )

    with pytest.raises(ValueError, match="frozen tariff"):
        run_grid_search(dimensions=dimensions, frozen_state=state, simulator=wrong_tariff)

    with pytest.raises(ValueError, match="ranking tariff"):
        rank_grid_candidates(results, tariff=another_tariff)


def test_evaluation_rejects_split_brain_physical_metrics() -> None:
    tariff = TariffScenario.flat(
        tariff_id="candidate", evidence=TariffEvidence.CANDIDATE, energy_rate_per_kwh=0.1
    )
    reward = _reward(90.0, tariff, BillingState())
    with pytest.raises(ValueError, match="peak_kw"):
        CandidateEvaluation(
            candidate_id="GRID_TEST",
            experiment_state_sha256=_sha("state"),
            tariff_sha256=tariff.fingerprint(),
            reward=reward,
            peak_kw=1.0,
            total_kwh=float(reward.candidate_billing["energy_kwh"]),
            simulator_provenance_sha256=_sha("simulator"),
        )


def test_upstream_adapter_provenance_does_not_claim_grid_search() -> None:
    provenance = rllib_energyplus_adapter_provenance()
    assert provenance["commit"] == "a8993f0d87e7d1fbcff0c2593274de2d472aef75"
    assert provenance["grid_search_support"].startswith("NOT_CLAIMED")
