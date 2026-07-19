"""Contracts in wattlab.existing_building.models: provenance, scenarios, badges."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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


def test_provenance_enum_covers_required_classes():
    values = {p.value for p in ProvenanceClass}
    assert values == {
        "measured",
        "user_entered",
        "bas_observed",
        "utility_observed",
        "drawing_or_schedule",
        "spreadsheet_derived",
        "inferred",
        "archetype_default",
        "energyplus_autosized",
        "scenario_override",
        "calibrated",
        "unknown",
    }


def test_evidence_field_rejects_extra_fields():
    with pytest.raises(ValidationError):
        EvidenceField(
            name="chiller_tons",
            value=120,
            provenance=ProvenanceClass.DRAWING_OR_SCHEDULE,
            bogus="nope",
        )


def test_evidence_inventory_rejects_duplicate_names_and_summarizes():
    field = EvidenceField(
        name="floor_area_ft2",
        value=42000,
        provenance=ProvenanceClass.MEASURED,
        confidence=Confidence.HIGH,
    )
    with pytest.raises(ValidationError, match="duplicate"):
        EvidenceInventory(building_id="b1", fields=[field, field])

    inventory = EvidenceInventory(
        building_id="b1",
        fields=[
            field,
            EvidenceField(
                name="cooling_cop", provenance=ProvenanceClass.ARCHETYPE_DEFAULT
            ),
        ],
    )
    assert inventory.get("floor_area_ft2").is_observed
    assert inventory.provenance_summary() == {"measured": 1, "archetype_default": 1}
    assert inventory.observed_fraction() == pytest.approx(0.5)


def test_assumption_cannot_claim_observed_provenance():
    with pytest.raises(ValidationError, match="cannot claim"):
        AssumptionRecord(
            name="infiltration_ach",
            value=0.4,
            rationale="typical for vintage",
            provenance=ProvenanceClass.MEASURED,
        )
    record = AssumptionRecord(
        name="infiltration_ach", value=0.4, rationale="typical for vintage"
    )
    assert record.provenance is ProvenanceClass.ARCHETYPE_DEFAULT


def test_soft_observation_direction():
    obs = SoftObservation(
        statement="boiler short-cycles on mild days",
        source="operator interview",
        direction="supports",
        hypothesis="oversized heating plant",
    )
    assert obs.direction == "supports"


def test_capacity_factors_bounds_and_parameters():
    factors = CapacityFactors.uniform(0.8)
    assert factors.as_parameters()["capacity_cooling"] == pytest.approx(0.8)
    with pytest.raises(ValidationError):
        CapacityFactors(cooling=0.0)
    with pytest.raises(ValidationError):
        CapacityFactors(heating=2.0)


def test_operating_hours_validation_and_weekly_total():
    hours = OperatingHoursConfig(name="weekday_10h", weekday_start_hour=7, weekday_end_hour=17)
    assert hours.weekly_occupied_hours == 50
    with pytest.raises(ValidationError, match="after"):
        OperatingHoursConfig(name="bad", weekday_start_hour=18, weekday_end_hour=8)
    with pytest.raises(ValidationError, match="together"):
        OperatingHoursConfig(name="half", weekend_start_hour=8)


def test_scenario_id_is_deterministic_and_content_addressed():
    kwargs = dict(
        name="reduced cooling capacity",
        scenario_type="capacity",
        parameters={"capacity_cooling": 0.75},
    )
    a = ScenarioDefinition(**kwargs)
    b = ScenarioDefinition(**kwargs)
    assert a.config_hash == b.config_hash
    assert a.scenario_id == b.scenario_id
    assert a.scenario_id.startswith("capacity-")
    assert len(a.config_hash) == 64

    changed = ScenarioDefinition(**{**kwargs, "parameters": {"capacity_cooling": 0.5}})
    assert changed.scenario_id != a.scenario_id


def test_scenario_parameter_names_must_be_identifiers():
    with pytest.raises(ValidationError, match="lower_snake_case"):
        ScenarioDefinition(
            name="x", scenario_type="capacity", parameters={"Bad Name": 1}
        )


def test_parameter_spec_bounds_and_clip():
    spec = ParameterSpec(
        name="cooling_cop",
        description="plant COP",
        default=3.2,
        minimum=2.0,
        maximum=6.5,
        energyplus_target="Coil:Cooling:DX.Gross Rated COP",
    )
    assert spec.clip(99) == 6.5
    assert spec.clip(0) == 2.0
    with pytest.raises(ValidationError, match="below"):
        ParameterSpec(name="x", description="d", default=1, minimum=5, maximum=2)
    with pytest.raises(ValidationError, match="within"):
        ParameterSpec(name="x", description="d", default=9, minimum=0, maximum=5)
    with pytest.raises(ValidationError, match="depend on itself"):
        ParameterSpec(
            name="x", description="d", default=1, minimum=0, maximum=5, depends_on=["x"]
        )


def test_objective_weights_require_some_positive_weight():
    with pytest.raises(ValidationError, match="positive"):
        ObjectiveWeights(
            monthly_nmbe=0,
            monthly_cvrmse=0,
            interval_cvrmse=0,
            interval_peak_error=0,
            nighttime_error=0,
            physical_plausibility=0,
        )
    weights = ObjectiveWeights()
    assert set(weights.as_dict()) == {
        "monthly_nmbe",
        "monthly_cvrmse",
        "interval_cvrmse",
        "interval_peak_error",
        "nighttime_error",
        "physical_plausibility",
    }


def test_badges_follow_calibration_modes():
    assert (
        award_badge(CalibrationMode.CONCEPTUAL_HYPOTHESIS)
        is InvestigationBadge.CONCEPTUAL_HYPOTHESIS
    )
    assert (
        award_badge(CalibrationMode.MONTHLY_CALIBRATED)
        is InvestigationBadge.MONTHLY_CALIBRATED
    )
    assert (
        award_badge(CalibrationMode.INTERVAL_CALIBRATED)
        is InvestigationBadge.INTERVAL_CALIBRATED
    )
    assert (
        award_badge(CalibrationMode.INTERVAL_CALIBRATED, investigate=True)
        is InvestigationBadge.INVESTIGATE
    )


def test_validated_requires_passing_held_out_evidence():
    assert (
        award_badge(CalibrationMode.MONTHLY_CALIBRATED, held_out_passed=True)
        is InvestigationBadge.VALIDATED
    )
    # A failed hold-out never yields VALIDATED.
    assert (
        award_badge(CalibrationMode.MONTHLY_CALIBRATED, held_out_passed=False)
        is InvestigationBadge.MONTHLY_CALIBRATED
    )
    # A conceptual hypothesis can never be VALIDATED.
    with pytest.raises(ValueError, match="cannot be VALIDATED"):
        award_badge(CalibrationMode.CONCEPTUAL_HYPOTHESIS, held_out_passed=True)
