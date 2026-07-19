"""Weighted multi-objective calibration score with fully explicit weights.

The score is a weighted sum of error terms (lower is better). Design rules:

- **Never hide weights.** Every breakdown serializes the declared weights,
  the effective weights actually applied, and each term's raw value and
  contribution, even when a term is inactive.
- **Auto-zero interval terms when there is no interval data.** A monthly-
  bills-only run must not be penalized (or flattered) by interval terms it
  cannot compute; those weights are zeroed and listed in ``auto_zeroed``.
- **Physical plausibility is a first-class term.** Implausible parameter
  combinations (COP above thermodynamic sanity, negative infiltration,
  occupancy denser than fire code…) add explicit named penalties instead of
  being silently clipped.
"""

from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field

from wattlab.existing_building.metrics import MetricSet
from wattlab.existing_building.models import ObjectiveWeights

#: Objective terms that require interval data to be meaningful.
INTERVAL_TERMS: tuple[str, ...] = (
    "interval_cvrmse",
    "interval_peak_error",
    "nighttime_error",
)


class PlausibilityPenalty(BaseModel):
    """One named physical-plausibility violation with an explicit magnitude."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    magnitude: float = Field(gt=0)
    reason: str = Field(min_length=1)


class ObjectiveTerm(BaseModel):
    """One scored term: raw error, weight applied, and its contribution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw: float | None
    declared_weight: float = Field(ge=0)
    effective_weight: float = Field(ge=0)
    contribution: float
    active: bool


class ObjectiveBreakdown(BaseModel):
    """Full, serializable accounting of one objective evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_score: float
    terms: dict[str, ObjectiveTerm]
    declared_weights: dict[str, float]
    effective_weights: dict[str, float]
    auto_zeroed: list[str]
    has_monthly_data: bool
    has_interval_data: bool
    penalties: list[PlausibilityPenalty]

    @property
    def plausibility_total(self) -> float:
        return sum(p.magnitude for p in self.penalties)

    @property
    def is_plausible(self) -> bool:
        return not self.penalties


def _abs_or_none(value: float | None) -> float | None:
    return None if value is None else abs(value)


def score_objective(
    weights: ObjectiveWeights,
    *,
    monthly: MetricSet | None = None,
    interval: MetricSet | None = None,
    nighttime: MetricSet | None = None,
    penalties: Sequence[PlausibilityPenalty] = (),
) -> ObjectiveBreakdown:
    """Score one candidate model against the evidence (lower is better).

    ``monthly`` compares bill-period energy; ``interval`` compares the
    interval series; ``nighttime`` is the nighttime split of the interval
    comparison. Terms whose data is absent contribute exactly zero via a
    zero *effective* weight — visibly, never silently.
    """
    if nighttime is not None and interval is None:
        raise ValueError(
            "nighttime metrics were supplied without interval metrics; the "
            "nighttime split is derived from interval data"
        )

    raw_values: dict[str, float | None] = {
        "monthly_nmbe": _abs_or_none(monthly.nmbe_percent if monthly else None),
        "monthly_cvrmse": monthly.cvrmse_percent if monthly else None,
        "interval_cvrmse": interval.cvrmse_percent if interval else None,
        "interval_peak_error": _abs_or_none(
            interval.peak_error_percent if interval else None
        ),
        "nighttime_error": _abs_or_none(
            nighttime.nmbe_percent if nighttime else None
        ),
        "physical_plausibility": sum(p.magnitude for p in penalties),
    }

    declared = weights.as_dict()
    effective = dict(declared)
    auto_zeroed: list[str] = []
    for name in INTERVAL_TERMS:
        if raw_values[name] is None and effective[name] > 0:
            effective[name] = 0.0
            auto_zeroed.append(name)
    if monthly is None:
        for name in ("monthly_nmbe", "monthly_cvrmse"):
            if effective[name] > 0:
                effective[name] = 0.0
                auto_zeroed.append(name)

    terms: dict[str, ObjectiveTerm] = {}
    total = 0.0
    for name, raw in raw_values.items():
        weight = effective[name]
        active = raw is not None and weight > 0
        contribution = (raw * weight) if active else 0.0
        total += contribution
        terms[name] = ObjectiveTerm(
            raw=raw,
            declared_weight=declared[name],
            effective_weight=weight,
            contribution=contribution,
            active=active,
        )

    return ObjectiveBreakdown(
        total_score=total,
        terms=terms,
        declared_weights=declared,
        effective_weights=effective,
        auto_zeroed=auto_zeroed,
        has_monthly_data=monthly is not None,
        has_interval_data=interval is not None,
        penalties=list(penalties),
    )
