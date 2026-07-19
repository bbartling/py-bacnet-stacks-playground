"""Investigation contracts for existing-building calibration work.

Strict Pydantic v2 models (``extra="forbid"`` everywhere) that make evidence
provenance, assumptions, scenarios, and calibration claims auditable:

- ``ProvenanceClass`` / ``Confidence``  — where a value came from, how sure we are
- ``EvidenceField`` / ``EvidenceInventory`` — per-field evidence with provenance
- ``AssumptionRecord``   — explicit assumption (never allowed to claim ``measured``)
- ``SoftObservation``    — qualitative observation that supports/contradicts a hypothesis
- ``CapacityFactors`` / ``OperatingHoursConfig`` — scenario knobs
- ``ScenarioDefinition`` — deterministic ``scenario_id`` + ``config_hash``
- ``ParameterSpec``      — bounded, tuneable parameter with an EnergyPlus target
- ``ObjectiveWeights``   — explicit multi-objective weights (never hidden)
- ``CalibrationMode``    — mode A/B/C ladder
- ``InvestigationBadge`` + ``award_badge`` — VALIDATED only with passing held-out evidence

These are additive; they do not replace or alter ``wattlab.contracts``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

ScalarValue = float | int | str | bool

_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class ProvenanceClass(str, Enum):
    """Where a piece of building evidence came from."""

    MEASURED = "measured"
    USER_ENTERED = "user_entered"
    BAS_OBSERVED = "bas_observed"
    UTILITY_OBSERVED = "utility_observed"
    DRAWING_OR_SCHEDULE = "drawing_or_schedule"
    SPREADSHEET_DERIVED = "spreadsheet_derived"
    INFERRED = "inferred"
    ARCHETYPE_DEFAULT = "archetype_default"
    ENERGYPLUS_AUTOSIZED = "energyplus_autosized"
    SCENARIO_OVERRIDE = "scenario_override"
    CALIBRATED = "calibrated"
    UNKNOWN = "unknown"


#: Provenance classes that count as direct observation of the real building.
OBSERVED_PROVENANCE: frozenset[ProvenanceClass] = frozenset(
    {
        ProvenanceClass.MEASURED,
        ProvenanceClass.BAS_OBSERVED,
        ProvenanceClass.UTILITY_OBSERVED,
    }
)


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class CalibrationMode(str, Enum):
    """Calibration ladder: A conceptual → B monthly bills → C interval data."""

    CONCEPTUAL_HYPOTHESIS = "A"
    MONTHLY_CALIBRATED = "B"
    INTERVAL_CALIBRATED = "C"


class InvestigationBadge(str, Enum):
    """Honest status stamped on every existing-building investigation."""

    CONCEPTUAL_HYPOTHESIS = "CONCEPTUAL_HYPOTHESIS"
    MONTHLY_CALIBRATED = "MONTHLY_CALIBRATED"
    INTERVAL_CALIBRATED = "INTERVAL_CALIBRATED"
    VALIDATED = "VALIDATED"
    INVESTIGATE = "INVESTIGATE"


def award_badge(
    mode: CalibrationMode,
    *,
    held_out_passed: bool | None = None,
    investigate: bool = False,
) -> InvestigationBadge:
    """Map a calibration mode to a badge.

    ``VALIDATED`` is only awarded when a held-out evidence period passed
    (``held_out_passed=True``) *and* the run is at least monthly-calibrated.
    A conceptual hypothesis can never be VALIDATED: it has no evidence to
    hold out, so claiming a passing held-out period is a contradiction.
    """
    if investigate:
        return InvestigationBadge.INVESTIGATE
    if held_out_passed:
        if mode is CalibrationMode.CONCEPTUAL_HYPOTHESIS:
            raise ValueError(
                "CONCEPTUAL_HYPOTHESIS cannot be VALIDATED: a conceptual run "
                "has no measured evidence to hold out"
            )
        return InvestigationBadge.VALIDATED
    return InvestigationBadge[mode.name]


class EvidenceField(BaseModel):
    """One named piece of evidence with explicit provenance and confidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    value: ScalarValue | None = None
    units: str | None = None
    provenance: ProvenanceClass
    confidence: Confidence = Confidence.UNKNOWN
    source: str | None = None
    observed_at: datetime | date | None = None
    notes: str | None = None

    @property
    def is_observed(self) -> bool:
        return self.provenance in OBSERVED_PROVENANCE


class EvidenceInventory(BaseModel):
    """All evidence fields for one building; names must be unique."""

    model_config = ConfigDict(extra="forbid")

    building_id: str = Field(min_length=1)
    fields: list[EvidenceField] = Field(default_factory=list)

    @field_validator("fields")
    @classmethod
    def _unique_names(cls, v: list[EvidenceField]) -> list[EvidenceField]:
        names = [f.name for f in v]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate evidence field names: {', '.join(dupes)}")
        return v

    def get(self, name: str) -> EvidenceField | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def provenance_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.fields:
            counts[f.provenance.value] = counts.get(f.provenance.value, 0) + 1
        return counts

    def observed_fraction(self) -> float:
        if not self.fields:
            return 0.0
        return sum(1 for f in self.fields if f.is_observed) / len(self.fields)


class AssumptionRecord(BaseModel):
    """An explicit modeling assumption; never allowed to masquerade as measured."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    value: ScalarValue
    units: str | None = None
    rationale: str = Field(min_length=1)
    provenance: ProvenanceClass = ProvenanceClass.ARCHETYPE_DEFAULT
    confidence: Confidence = Confidence.LOW
    affects_parameters: list[str] = Field(default_factory=list)

    @field_validator("provenance")
    @classmethod
    def _assumptions_are_not_observations(cls, v: ProvenanceClass) -> ProvenanceClass:
        if v in OBSERVED_PROVENANCE:
            raise ValueError(
                f"an AssumptionRecord cannot claim {v.value!r} provenance; "
                "record it as an EvidenceField instead"
            )
        return v


class SoftObservation(BaseModel):
    """Qualitative observation ("boiler short-cycles on mild days") with direction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = Field(min_length=1)
    source: str = Field(min_length=1)
    direction: Literal["supports", "contradicts", "neutral"] = "neutral"
    hypothesis: str | None = None
    confidence: Confidence = Confidence.UNKNOWN
    observed_at: datetime | date | None = None


class CapacityFactors(BaseModel):
    """Per-end-use capacity multipliers relative to the baseline model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cooling: float = Field(default=1.0, gt=0, le=1.5)
    heating: float = Field(default=1.0, gt=0, le=1.5)
    fan: float = Field(default=1.0, gt=0, le=1.5)
    pumps: float = Field(default=1.0, gt=0, le=1.5)

    @classmethod
    def uniform(cls, factor: float) -> "CapacityFactors":
        return cls(cooling=factor, heating=factor, fan=factor, pumps=factor)

    def as_parameters(self) -> dict[str, float]:
        return {
            "capacity_cooling": self.cooling,
            "capacity_heating": self.heating,
            "capacity_fan": self.fan,
            "capacity_pumps": self.pumps,
        }


class OperatingHoursConfig(BaseModel):
    """Occupied-hours schedule knob for scenario generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    weekday_start_hour: int = Field(default=7, ge=0, le=23)
    weekday_end_hour: int = Field(default=18, ge=1, le=24)
    weekend_start_hour: int | None = Field(default=None, ge=0, le=23)
    weekend_end_hour: int | None = Field(default=None, ge=1, le=24)
    holidays_occupied: bool = False

    @model_validator(mode="after")
    def _hours_ordered(self) -> "OperatingHoursConfig":
        if self.weekday_end_hour <= self.weekday_start_hour:
            raise ValueError(
                f"weekday_end_hour ({self.weekday_end_hour}) must be after "
                f"weekday_start_hour ({self.weekday_start_hour})"
            )
        if (self.weekend_start_hour is None) != (self.weekend_end_hour is None):
            raise ValueError(
                "weekend_start_hour and weekend_end_hour must be provided together"
            )
        if (
            self.weekend_start_hour is not None
            and self.weekend_end_hour is not None
            and self.weekend_end_hour <= self.weekend_start_hour
        ):
            raise ValueError(
                f"weekend_end_hour ({self.weekend_end_hour}) must be after "
                f"weekend_start_hour ({self.weekend_start_hour})"
            )
        return self

    @property
    def weekly_occupied_hours(self) -> int:
        weekday = (self.weekday_end_hour - self.weekday_start_hour) * 5
        weekend = 0
        if self.weekend_start_hour is not None and self.weekend_end_hour is not None:
            weekend = (self.weekend_end_hour - self.weekend_start_hour) * 2
        return weekday + weekend


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
    )


class ScenarioDefinition(BaseModel):
    """A candidate model configuration with deterministic identity.

    ``config_hash`` is the SHA-256 of the canonical JSON of the scenario's
    declared content, and ``scenario_id`` embeds its first 12 hex chars, so
    the same configuration always maps to the same id across runs/machines.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    scenario_type: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = ""
    parameters: dict[str, ScalarValue] = Field(default_factory=dict)
    baseline_scenario_id: str | None = None
    provenance: ProvenanceClass = ProvenanceClass.SCENARIO_OVERRIDE

    @field_validator("parameters")
    @classmethod
    def _parameter_names_are_identifiers(
        cls, v: dict[str, ScalarValue]
    ) -> dict[str, ScalarValue]:
        bad = sorted(k for k in v if not _IDENTIFIER_RE.match(k))
        if bad:
            raise ValueError(
                f"parameter names must be lower_snake_case identifiers: {', '.join(bad)}"
            )
        return v

    def canonical_config(self) -> str:
        return _canonical_json(
            {
                "name": self.name,
                "scenario_type": self.scenario_type,
                "description": self.description,
                "parameters": self.parameters,
                "baseline_scenario_id": self.baseline_scenario_id,
                "provenance": self.provenance.value,
            }
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def config_hash(self) -> str:
        return hashlib.sha256(self.canonical_config().encode("utf-8")).hexdigest()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def scenario_id(self) -> str:
        return f"{self.scenario_type}-{self.config_hash[:12]}"


class ParameterSpec(BaseModel):
    """A bounded, optionally tuneable model parameter with an EnergyPlus target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1)
    units: str | None = None
    default: float
    minimum: float
    maximum: float
    tuneable: bool = True
    energyplus_target: str | None = None
    depends_on: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _bounds_consistent(self) -> "ParameterSpec":
        if self.minimum >= self.maximum:
            raise ValueError(
                f"{self.name}: minimum ({self.minimum}) must be below "
                f"maximum ({self.maximum})"
            )
        if not (self.minimum <= self.default <= self.maximum):
            raise ValueError(
                f"{self.name}: default ({self.default}) must lie within "
                f"[{self.minimum}, {self.maximum}]"
            )
        if self.name in self.depends_on:
            raise ValueError(f"{self.name}: parameter cannot depend on itself")
        return self

    def clip(self, value: float) -> float:
        return min(self.maximum, max(self.minimum, value))


class ObjectiveWeights(BaseModel):
    """Explicit weights for the multi-objective calibration score.

    Every weight is serialized on every score breakdown — weights are never
    hidden or silently renormalized away.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    monthly_nmbe: float = Field(default=1.0, ge=0)
    monthly_cvrmse: float = Field(default=1.0, ge=0)
    interval_cvrmse: float = Field(default=1.0, ge=0)
    interval_peak_error: float = Field(default=0.5, ge=0)
    nighttime_error: float = Field(default=0.5, ge=0)
    physical_plausibility: float = Field(default=1.0, ge=0)

    @model_validator(mode="after")
    def _some_weight_positive(self) -> "ObjectiveWeights":
        if not any(
            w > 0
            for w in (
                self.monthly_nmbe,
                self.monthly_cvrmse,
                self.interval_cvrmse,
                self.interval_peak_error,
                self.nighttime_error,
                self.physical_plausibility,
            )
        ):
            raise ValueError("at least one objective weight must be positive")
        return self

    def as_dict(self) -> dict[str, float]:
        return {
            "monthly_nmbe": self.monthly_nmbe,
            "monthly_cvrmse": self.monthly_cvrmse,
            "interval_cvrmse": self.interval_cvrmse,
            "interval_peak_error": self.interval_peak_error,
            "nighttime_error": self.nighttime_error,
            "physical_plausibility": self.physical_plausibility,
        }
