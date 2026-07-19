"""Deterministic bounded search over registered calibration parameters.

Strategy — deliberately boring, auditable, and reproducible (no heavy ML):

1. **OFAT sensitivity.** Each tuneable parameter is swept to its bounds one
   factor at a time while everything else stays at its default; the impact
   is the largest change in objective score versus the baseline.
2. **Prune.** Parameters whose impact falls below ``impact_threshold`` ×
   (largest impact) are frozen at their defaults for the search stage.
3. **Coarse search.** The surviving parameters are explored with either a
   full coarse grid (when it fits in the evaluation budget) or uniform
   random samples from ``random.Random(seed)`` — same seed, same candidates,
   same order, on any machine.
4. **Retain top-N plausible.** Candidates carrying physical-plausibility
   penalties are reported but never ranked above penalty-free ones.

Every candidate gets a deterministic ``candidate_id`` (SHA-256 of its
canonical parameter JSON), so results can be diffed across runs.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
from typing import Callable, Sequence

from pydantic import BaseModel, ConfigDict, Field

from wattlab.existing_building.objective import ObjectiveBreakdown
from wattlab.existing_building.parameters import ParameterRegistry

#: Evaluator contract: full parameter dict in, full objective breakdown out.
Evaluator = Callable[[dict[str, float]], ObjectiveBreakdown]


def candidate_id(parameters: dict[str, float]) -> str:
    """Deterministic 12-hex id for one parameter combination."""
    canonical = json.dumps(
        {k: float(v) for k, v in parameters.items()},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


class SearchConfig(BaseModel):
    """Knobs for the OFAT + coarse-search pipeline (all explicit)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int = 0
    grid_points_per_parameter: int = Field(default=3, ge=2, le=7)
    max_grid_evaluations: int = Field(default=256, ge=1)
    n_random_samples: int = Field(default=64, ge=1)
    impact_threshold: float = Field(default=0.02, ge=0, le=1)
    top_n: int = Field(default=5, ge=1)


class SensitivityResult(BaseModel):
    """OFAT impact of one parameter (score units, lower baseline = better)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter: str
    baseline_score: float
    score_at_minimum: float
    score_at_maximum: float
    impact: float = Field(ge=0)
    pruned: bool


class Candidate(BaseModel):
    """One evaluated parameter combination."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    parameters: dict[str, float]
    score: float
    plausible: bool
    breakdown: ObjectiveBreakdown


class SearchResult(BaseModel):
    """Full, serializable record of one search run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int
    strategy: str
    baseline: Candidate
    sensitivity: list[SensitivityResult]
    searched_parameters: list[str]
    pruned_parameters: list[str]
    n_evaluations: int = Field(ge=1)
    top_candidates: list[Candidate]

    @property
    def best(self) -> Candidate:
        return self.top_candidates[0] if self.top_candidates else self.baseline


def _evaluate(evaluator: Evaluator, parameters: dict[str, float]) -> Candidate:
    breakdown = evaluator(dict(parameters))
    return Candidate(
        candidate_id=candidate_id(parameters),
        parameters=dict(parameters),
        score=breakdown.total_score,
        plausible=breakdown.is_plausible,
        breakdown=breakdown,
    )


def ofat_sensitivity(
    registry: ParameterRegistry,
    evaluator: Evaluator,
    *,
    baseline: Candidate | None = None,
    impact_threshold: float = 0.02,
) -> tuple[Candidate, list[SensitivityResult]]:
    """One-factor-at-a-time bound sweep for every tuneable parameter."""
    defaults = registry.defaults()
    base = baseline or _evaluate(evaluator, defaults)
    results: list[SensitivityResult] = []
    impacts: dict[str, tuple[float, float]] = {}
    for spec in registry.tuneable():
        low = _evaluate(evaluator, {**defaults, spec.name: spec.minimum})
        high = _evaluate(evaluator, {**defaults, spec.name: spec.maximum})
        impacts[spec.name] = (low.score, high.score)
    max_impact = max(
        (
            max(abs(lo - base.score), abs(hi - base.score))
            for lo, hi in impacts.values()
        ),
        default=0.0,
    )
    for spec in registry.tuneable():
        lo, hi = impacts[spec.name]
        impact = max(abs(lo - base.score), abs(hi - base.score))
        pruned = max_impact > 0 and impact < impact_threshold * max_impact
        results.append(
            SensitivityResult(
                parameter=spec.name,
                baseline_score=base.score,
                score_at_minimum=lo,
                score_at_maximum=hi,
                impact=impact,
                pruned=pruned,
            )
        )
    results.sort(key=lambda r: (-r.impact, r.parameter))
    return base, results


def _grid_values(minimum: float, maximum: float, points: int) -> list[float]:
    step = (maximum - minimum) / (points - 1)
    return [minimum + i * step for i in range(points)]


def _grid_candidates(
    registry: ParameterRegistry,
    names: Sequence[str],
    defaults: dict[str, float],
    points: int,
) -> list[dict[str, float]]:
    axes = [
        _grid_values(registry.get(n).minimum, registry.get(n).maximum, points)
        for n in names
    ]
    return [
        {**defaults, **dict(zip(names, combo))}
        for combo in itertools.product(*axes)
    ]


def _random_candidates(
    registry: ParameterRegistry,
    names: Sequence[str],
    defaults: dict[str, float],
    n_samples: int,
    seed: int,
) -> list[dict[str, float]]:
    rng = random.Random(seed)
    out: list[dict[str, float]] = []
    for _ in range(n_samples):
        combo = dict(defaults)
        for name in names:
            spec = registry.get(name)
            combo[name] = rng.uniform(spec.minimum, spec.maximum)
        out.append(combo)
    return out


def run_search(
    registry: ParameterRegistry,
    evaluator: Evaluator,
    config: SearchConfig | None = None,
) -> SearchResult:
    """OFAT sensitivity, prune, coarse bounded search, retain top-N plausible."""
    cfg = config or SearchConfig()
    registry.validate_dependencies()
    defaults = registry.defaults()

    baseline, sensitivity = ofat_sensitivity(
        registry, evaluator, impact_threshold=cfg.impact_threshold
    )
    searched = [r.parameter for r in sensitivity if not r.pruned]
    pruned = [r.parameter for r in sensitivity if r.pruned]
    n_evaluations = 1 + 2 * len(sensitivity)

    candidates: list[Candidate] = [baseline]
    strategy = "ofat_only"
    if searched:
        grid_size = cfg.grid_points_per_parameter ** len(searched)
        if grid_size <= cfg.max_grid_evaluations:
            combos = _grid_candidates(
                registry, searched, defaults, cfg.grid_points_per_parameter
            )
            strategy = "ofat+grid"
        else:
            combos = _random_candidates(
                registry, searched, defaults, cfg.n_random_samples, cfg.seed
            )
            strategy = "ofat+random"
        seen = {baseline.candidate_id}
        for combo in combos:
            cid = candidate_id(combo)
            if cid in seen:
                continue
            seen.add(cid)
            candidates.append(_evaluate(evaluator, combo))
            n_evaluations += 1

    # Plausible candidates always outrank penalized ones; ties break on the
    # deterministic candidate id so ordering is stable across runs.
    ranked = sorted(
        candidates,
        key=lambda c: (not c.plausible, c.score, c.candidate_id),
    )
    return SearchResult(
        seed=cfg.seed,
        strategy=strategy,
        baseline=baseline,
        sensitivity=sensitivity,
        searched_parameters=searched,
        pruned_parameters=pruned,
        n_evaluations=n_evaluations,
        top_candidates=ranked[: cfg.top_n],
    )
