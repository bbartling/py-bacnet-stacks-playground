"""Objective scoring + deterministic search: hashes, weights, badge rules."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from wattlab.existing_building.metrics import (
    compute_metrics,
    cvrmse_percent,
    nmbe_percent,
    split_metrics,
)
from wattlab.existing_building.models import (
    CalibrationMode,
    InvestigationBadge,
    ObjectiveWeights,
    ParameterSpec,
    ScenarioDefinition,
    award_badge,
)
from wattlab.existing_building.objective import (
    PlausibilityPenalty,
    score_objective,
)
from wattlab.existing_building.parameters import (
    ParameterRegistry,
    default_parameter_registry,
)
from wattlab.existing_building.search import (
    SearchConfig,
    candidate_id,
    run_search,
)

ACTUAL = [100.0, 120.0, 90.0, 110.0, 105.0, 95.0]
MODELED = [98.0, 125.0, 88.0, 112.0, 100.0, 97.0]


# ---------------------------------------------------------------- metrics


def test_metric_denominators_follow_spec():
    # NMBE uses n; CVRMSE uses n-1.
    actual = [10.0, 10.0]
    modeled = [8.0, 8.0]
    assert nmbe_percent(actual, modeled) == pytest.approx(100 * 4 / (2 * 10))
    assert cvrmse_percent(actual, modeled) == pytest.approx(
        100 * (8.0 / 1) ** 0.5 / 10
    )
    # Single point falls back to n instead of dividing by zero.
    assert cvrmse_percent([10.0], [8.0]) == pytest.approx(20.0)


def test_split_metrics_cover_diagnostic_bands():
    start = datetime(2025, 6, 2)  # a Monday
    timestamps = [start + timedelta(hours=i) for i in range(24 * 7)]
    actual = [50.0 + (i % 24) for i in range(len(timestamps))]
    modeled = [a * 1.05 for a in actual]
    oat = [30.0 + (i % 24) * 3 for i in range(len(timestamps))]  # 30..99 F
    splits = split_metrics(timestamps, actual, modeled, oat_f=oat)
    assert {"nighttime", "occupied", "weekend", "hot", "cold"} <= set(splits)
    assert all(s.n >= 2 for s in splits.values())


# ---------------------------------------------------------------- objective


def test_objective_never_hides_weights():
    weights = ObjectiveWeights(monthly_nmbe=2.0, physical_plausibility=3.0)
    breakdown = score_objective(weights, monthly=compute_metrics(ACTUAL, MODELED))
    assert breakdown.declared_weights == weights.as_dict()
    assert set(breakdown.terms) == set(weights.as_dict())
    payload = breakdown.model_dump()
    assert payload["declared_weights"]["monthly_nmbe"] == 2.0
    assert payload["effective_weights"]["interval_cvrmse"] == 0.0


def test_interval_terms_auto_zero_without_interval_data():
    breakdown = score_objective(
        ObjectiveWeights(), monthly=compute_metrics(ACTUAL, MODELED)
    )
    assert set(breakdown.auto_zeroed) == {
        "interval_cvrmse",
        "interval_peak_error",
        "nighttime_error",
    }
    for name in breakdown.auto_zeroed:
        assert breakdown.effective_weights[name] == 0.0
        assert breakdown.declared_weights[name] > 0.0  # declared stays visible
        assert breakdown.terms[name].contribution == 0.0
    assert not breakdown.has_interval_data

    with_interval = score_objective(
        ObjectiveWeights(),
        monthly=compute_metrics(ACTUAL, MODELED),
        interval=compute_metrics(ACTUAL, MODELED),
    )
    assert "interval_cvrmse" not in with_interval.auto_zeroed
    assert with_interval.total_score > 0


def test_plausibility_penalties_are_explicit_and_raise_score():
    weights = ObjectiveWeights()
    monthly = compute_metrics(ACTUAL, MODELED)
    clean = score_objective(weights, monthly=monthly)
    penalized = score_objective(
        weights,
        monthly=monthly,
        penalties=[
            PlausibilityPenalty(
                name="cooling_cop", magnitude=50.0, reason="COP 9 exceeds sanity bound"
            )
        ],
    )
    assert penalized.total_score > clean.total_score
    assert not penalized.is_plausible
    assert penalized.terms["physical_plausibility"].raw == pytest.approx(50.0)


def test_nighttime_without_interval_is_rejected():
    with pytest.raises(ValueError, match="nighttime"):
        score_objective(
            ObjectiveWeights(), nighttime=compute_metrics(ACTUAL, MODELED)
        )


# ---------------------------------------------------------------- search


def _toy_registry() -> ParameterRegistry:
    return ParameterRegistry(
        [
            ParameterSpec(
                name="lights",
                description="lighting multiplier",
                default=1.0,
                minimum=0.5,
                maximum=1.5,
                energyplus_target="Lights",
            ),
            ParameterSpec(
                name="plug",
                description="plug multiplier",
                default=1.0,
                minimum=0.5,
                maximum=1.5,
                energyplus_target="ElectricEquipment",
            ),
            ParameterSpec(
                name="noise",
                description="near-zero-impact knob",
                default=1.0,
                minimum=0.999,
                maximum=1.001,
                energyplus_target="n/a",
            ),
        ]
    )


def _toy_evaluator(params: dict[str, float]):
    """Quadratic bowl with optimum at lights=0.8, plug=1.2."""
    error = 100 * (params["lights"] - 0.8) ** 2 + 100 * (params["plug"] - 1.2) ** 2
    error += 0.0001 * (params["noise"] - 1.0) ** 2
    modeled = [a * (1 + error / 100) for a in ACTUAL]
    penalties = []
    if params["lights"] > 1.4:
        penalties.append(
            PlausibilityPenalty(
                name="lights", magnitude=1000.0, reason="beyond plausible LPD"
            )
        )
    return score_objective(
        ObjectiveWeights(),
        monthly=compute_metrics(ACTUAL, modeled),
        penalties=penalties,
    )


def test_search_is_deterministic_and_hashes_are_stable():
    cfg = SearchConfig(seed=42, top_n=3)
    a = run_search(_toy_registry(), _toy_evaluator, cfg)
    b = run_search(_toy_registry(), _toy_evaluator, cfg)
    assert [c.candidate_id for c in a.top_candidates] == [
        c.candidate_id for c in b.top_candidates
    ]
    assert a.model_dump() == b.model_dump()
    # Content-addressed ids: same parameters, same id, anywhere.
    assert candidate_id({"lights": 1.0, "plug": 1.0}) == candidate_id(
        {"plug": 1.0, "lights": 1.0}
    )


def test_search_prunes_low_impact_and_improves_score():
    # 5 grid points per axis puts (0.75, 1.25) near the true optimum
    # (0.8, 1.2); the default 3-point grid would only revisit the baseline.
    result = run_search(
        _toy_registry(),
        _toy_evaluator,
        SearchConfig(seed=7, grid_points_per_parameter=5),
    )
    assert "noise" in result.pruned_parameters
    assert set(result.searched_parameters) == {"lights", "plug"}
    assert result.best.score < result.baseline.score
    assert result.strategy in {"ofat+grid", "ofat+random"}
    assert result.n_evaluations >= 1 + 2 * 3  # baseline + OFAT sweeps


def test_search_never_ranks_implausible_above_plausible():
    result = run_search(
        _toy_registry(), _toy_evaluator, SearchConfig(seed=1, top_n=10)
    )
    ranks = [c.plausible for c in result.top_candidates]
    # Once an implausible candidate appears, no plausible one may follow.
    assert ranks == sorted(ranks, reverse=True)
    assert result.top_candidates[0].plausible


def test_scenario_hashes_deterministic_across_processes():
    scenario = ScenarioDefinition(
        name="reduced cooling",
        scenario_type="capacity",
        parameters={"capacity_cooling": 0.75},
    )
    twin = ScenarioDefinition(
        name="reduced cooling",
        scenario_type="capacity",
        parameters={"capacity_cooling": 0.75},
    )
    assert scenario.config_hash == twin.config_hash
    dumped = scenario.model_dump()
    assert dumped["scenario_id"] == scenario.scenario_id


def test_conceptual_run_cannot_be_validated():
    # The badge layer refuses VALIDATED for mode A regardless of what the
    # search found: no held-out evidence exists for a conceptual hypothesis.
    with pytest.raises(ValueError, match="cannot be VALIDATED"):
        award_badge(CalibrationMode.CONCEPTUAL_HYPOTHESIS, held_out_passed=True)
    assert (
        award_badge(CalibrationMode.CONCEPTUAL_HYPOTHESIS)
        is InvestigationBadge.CONCEPTUAL_HYPOTHESIS
    )
