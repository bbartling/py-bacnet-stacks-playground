"""Transparent, deterministic grid search contracts for calibrated Vibe 23 models.

This module deliberately has no EnergyPlus or Ray dependency.  It enumerates
the finite decision menu, freezes the common state, and accepts a simulator
adapter supplied by the caller.  That makes it suitable as the audit benchmark
for an EnergyPlus/RLlib experiment rather than a disguised RL implementation.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Sequence

from .reward import RewardResult
from .tariff import TariffScenario

GRID_SCHEMA = "vibe23.grid_search.v1"
RLIB_ENERGYPLUS_PIN = "a8993f0d87e7d1fbcff0c2593274de2d472aef75"
RLIB_ENERGYPLUS_REPOSITORY = "https://github.com/airboxlab/rllib-energyplus"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FrozenExperimentState:
    """Hashes that every baseline and grid candidate must share."""

    decision_day: str
    model_sha256: str
    weather_sha256: str
    calibration_run_sha256: str
    initial_state_sha256: str
    baseline_trajectory_sha256: str
    billing_state_sha256: str
    tariff_sha256: str
    occupancy_calendar_sha256: str
    energyplus_version: str

    def __post_init__(self) -> None:
        if not self.decision_day or not self.energyplus_version:
            raise ValueError("decision_day and energyplus_version are required")
        for name, value in asdict(self).items():
            if name in {"decision_day", "energyplus_version"}:
                continue
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")

    def fingerprint(self) -> str:
        return _sha256(asdict(self))


@dataclass(frozen=True)
class GridDimension:
    name: str
    values: tuple[Any, ...]

    def __post_init__(self) -> None:
        if not self.name or not self.values:
            raise ValueError("each grid dimension needs a name and at least one value")
        fingerprints = [_canonical_json(v) for v in self.values]
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError(f"grid dimension {self.name!r} contains duplicate values")


@dataclass(frozen=True)
class GridCandidate:
    candidate_id: str
    ordinal: int
    action: Mapping[str, Any]
    action_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "ordinal": self.ordinal,
            "action": dict(self.action),
            "action_sha256": self.action_sha256,
        }


def enumerate_grid(dimensions: Sequence[GridDimension]) -> tuple[GridCandidate, ...]:
    """Cartesian-enumerate a declared grid in declared dimension/value order."""

    dims = tuple(dimensions)
    if not dims:
        raise ValueError("at least one grid dimension is required")
    names = [dimension.name for dimension in dims]
    if len(set(names)) != len(names):
        raise ValueError("grid dimension names must be unique")
    candidates: list[GridCandidate] = []
    for ordinal, values in enumerate(itertools.product(*(dimension.values for dimension in dims))):
        action = {dimension.name: value for dimension, value in zip(dims, values, strict=True)}
        action_sha256 = _sha256(action)
        candidates.append(
            GridCandidate(
                candidate_id=f"GRID_{ordinal:04d}_{action_sha256[:12]}",
                ordinal=ordinal,
                action=action,
                action_sha256=action_sha256,
            )
        )
    return tuple(candidates)


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str
    experiment_state_sha256: str
    tariff_sha256: str
    reward: RewardResult
    peak_kw: float
    total_kwh: float
    simulator_provenance_sha256: str
    simulation_success: bool = True

    def __post_init__(self) -> None:
        for name in ("experiment_state_sha256", "tariff_sha256", "simulator_provenance_sha256"):
            value = getattr(self, name)
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        if self.peak_kw < 0 or self.total_kwh < 0:
            raise ValueError("peak_kw and total_kwh must be non-negative")
        billed_peak = float(self.reward.candidate_billing["day_peak_kw"])
        billed_energy = float(self.reward.candidate_billing["energy_kwh"])
        if self.reward.candidate_billing.get("tariff_sha256") != self.tariff_sha256:
            raise ValueError("tariff_sha256 must match reward.candidate_billing")
        if self.reward.baseline_billing.get("tariff_sha256") != self.tariff_sha256:
            raise ValueError("tariff_sha256 must match reward.baseline_billing")
        if self.reward.candidate_billing.get("billing_state_sha256") != self.reward.baseline_billing.get(
            "billing_state_sha256"
        ):
            raise ValueError("candidate and baseline must share the same opening billing state")
        if abs(self.peak_kw - billed_peak) > 1e-9:
            raise ValueError("peak_kw must match reward.candidate_billing.day_peak_kw")
        if abs(self.total_kwh - billed_energy) > 1e-9:
            raise ValueError("total_kwh must match reward.candidate_billing.energy_kwh")

    @property
    def eligible(self) -> bool:
        return self.simulation_success and self.reward.readiness_ok


Simulator = Callable[[GridCandidate, FrozenExperimentState], CandidateEvaluation]


def run_grid_search(
    *,
    dimensions: Sequence[GridDimension],
    frozen_state: FrozenExperimentState,
    simulator: Simulator,
) -> tuple[CandidateEvaluation, ...]:
    """Run the exact declared menu and reject cross-state or mislabeled results."""

    candidates = enumerate_grid(dimensions)
    state_sha = frozen_state.fingerprint()
    evaluations: list[CandidateEvaluation] = []
    for candidate in candidates:
        evaluation = simulator(candidate, frozen_state)
        if evaluation.candidate_id != candidate.candidate_id:
            raise ValueError("simulator returned a result for a different candidate")
        if evaluation.experiment_state_sha256 != state_sha:
            raise ValueError("identical-state contract violated by simulator result")
        if evaluation.tariff_sha256 != frozen_state.tariff_sha256:
            raise ValueError("frozen tariff contract violated by simulator result")
        if evaluation.reward.candidate_billing.get("billing_state_sha256") != frozen_state.billing_state_sha256:
            raise ValueError("frozen billing-state contract violated by simulator result")
        evaluations.append(evaluation)
    return tuple(evaluations)


def rank_grid_candidates(
    evaluations: Sequence[CandidateEvaluation], *, tariff: TariffScenario
) -> dict[str, Any]:
    """Rank eligible candidates using tariff-authorized or physical objectives.

    Candidate/illustrative tariff dollars remain in every result, but the winner
    is chosen by physical quantities until a verified account-bound tariff is
    available.  This is a fail-closed answer to the main Vibe 22 tariff lesson.
    """

    expected_tariff_sha256 = tariff.fingerprint()
    mismatched = [item.candidate_id for item in evaluations if item.tariff_sha256 != expected_tariff_sha256]
    if mismatched:
        raise ValueError(f"ranking tariff does not match evaluated candidates: {mismatched}")
    eligible = [item for item in evaluations if item.eligible]
    if not eligible:
        return {
            "schema": GRID_SCHEMA,
            "status": "NO_FULLY_READY_SUCCESSFUL_CANDIDATE",
            "winner": None,
            "eligible_count": 0,
            "tariff_label": tariff.money_label,
            "selection_label": tariff.selection_label,
        }
    if tariff.monetary_selection_authorized:
        def key(item: CandidateEvaluation) -> tuple[float, float, float, float, str]:
            return (
                item.reward.selection_cost_usd,
                item.peak_kw,
                item.reward.occupied_low_degree_hours + item.reward.occupied_high_degree_hours,
                item.reward.action_smoothness,
                item.candidate_id,
            )

        objective = "VERIFIED_MONETARY_COST_THEN_PHYSICAL_TIEBREAKS"
    else:
        def key(item: CandidateEvaluation) -> tuple[float, float, float, float, str]:
            return (
                item.peak_kw,
                item.total_kwh,
                item.reward.occupied_low_degree_hours + item.reward.occupied_high_degree_hours,
                item.reward.action_smoothness,
                item.candidate_id,
            )

        objective = "PHYSICAL_PEAK_KWH_COMFORT_SMOOTHNESS; MONEY_SCENARIO_ONLY"
    winner = sorted(eligible, key=key)[0]
    return {
        "schema": GRID_SCHEMA,
        "status": "OK",
        "winner": winner.candidate_id,
        "eligible_count": len(eligible),
        "selection_objective": objective,
        "tariff_label": tariff.money_label,
        "selection_label": tariff.selection_label,
        "winner_cost_usd": winner.reward.selection_cost_usd,
        "winner_peak_kw": winner.peak_kw,
        "winner_kwh": winner.total_kwh,
        "winner_action_smoothness": winner.reward.action_smoothness,
    }


def rllib_energyplus_adapter_provenance() -> dict[str, str]:
    """Pinned upstream facts; intentionally does not import RLlib or EnergyPlus."""

    return {
        "repository": RLIB_ENERGYPLUS_REPOSITORY,
        "commit": RLIB_ENERGYPLUS_PIN,
        "upstream_package_version": "0.11.0",
        "upstream_api": "EnergyPlusEnv subclass using EnergyPlus Python API",
        "upstream_rl_example": "Ray RLlib PPO trainer",
        "grid_search_support": "NOT_CLAIMED; Vibe23 owns deterministic enumeration and scoring",
        "pin_sha256": _sha256({"repository": RLIB_ENERGYPLUS_REPOSITORY, "commit": RLIB_ENERGYPLUS_PIN}),
    }
