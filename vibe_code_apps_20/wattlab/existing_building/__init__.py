"""Existing-building investigation toolkit (additive to ``wattlab.contracts``).

Modules:

- ``models``          — provenance/evidence/scenario/badge contracts
- ``utility_periods`` — date-keyed, multi-year monthly billing histories
- ``interval_meters`` — interval CSV loader with timezone/DST + coverage stats
- ``metrics``         — unified NMBE/CV(RMSE)/MAE/correlation/peak + splits
- ``objective``       — explicit-weight multi-objective calibration score
- ``parameters``      — bounded, tuneable parameter registry
- ``search``          — deterministic OFAT + coarse bounded search
"""

from __future__ import annotations

from wattlab.existing_building.interval_meters import (
    CoverageStats,
    IntervalDataset,
    IntervalLoadError,
    convert_cumulative,
    load_interval_csv,
)
from wattlab.existing_building.metrics import (
    MetricSet,
    compute_metrics,
    cvrmse_percent,
    mae,
    nmbe_percent,
    peak_error_percent,
    pearson_correlation,
    split_masks,
    split_metrics,
)
from wattlab.existing_building.models import (
    AssumptionRecord,
    CalibrationMode,
    CapacityFactors,
    Confidence,
    EvidenceField,
    EvidenceInventory,
    InvestigationBadge,
    ObjectiveWeights,
    OperatingHoursConfig,
    ParameterSpec,
    ProvenanceClass,
    ScenarioDefinition,
    SoftObservation,
    award_badge,
)
from wattlab.existing_building.objective import (
    ObjectiveBreakdown,
    PlausibilityPenalty,
    score_objective,
)
from wattlab.existing_building.parameters import (
    ParameterRegistry,
    default_parameter_registry,
)
from wattlab.existing_building.search import (
    Candidate,
    SearchConfig,
    SearchResult,
    SensitivityResult,
    candidate_id,
    ofat_sensitivity,
    run_search,
)
from wattlab.existing_building.utility_periods import (
    BillingHistory,
    BillingPeriod,
    PeriodGap,
    PeriodOverlap,
    from_utility_dataset,
)

__all__ = [
    "AssumptionRecord",
    "BillingHistory",
    "BillingPeriod",
    "CalibrationMode",
    "Candidate",
    "CapacityFactors",
    "Confidence",
    "CoverageStats",
    "EvidenceField",
    "EvidenceInventory",
    "IntervalDataset",
    "IntervalLoadError",
    "InvestigationBadge",
    "MetricSet",
    "ObjectiveBreakdown",
    "ObjectiveWeights",
    "OperatingHoursConfig",
    "ParameterRegistry",
    "ParameterSpec",
    "PeriodGap",
    "PeriodOverlap",
    "PlausibilityPenalty",
    "ProvenanceClass",
    "ScenarioDefinition",
    "SearchConfig",
    "SearchResult",
    "SensitivityResult",
    "SoftObservation",
    "award_badge",
    "candidate_id",
    "compute_metrics",
    "convert_cumulative",
    "cvrmse_percent",
    "default_parameter_registry",
    "from_utility_dataset",
    "load_interval_csv",
    "mae",
    "nmbe_percent",
    "ofat_sensitivity",
    "peak_error_percent",
    "pearson_correlation",
    "run_search",
    "score_objective",
    "split_masks",
    "split_metrics",
]
