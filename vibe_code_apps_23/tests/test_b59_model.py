import math
from dataclasses import FrozenInstanceError, replace

import pytest

from vibe23.b59_model import (
    CFM_TO_M3_S,
    CLAIM_LABEL,
    DEFAULT_CALIBRATION_PARAMETERS,
    DEFAULT_SIMULATION_YEAR,
    PUBLISHED_RTU_RATINGS,
    RTU_COOLING_CAPACITY_W,
    RTU_MINIMUM_OA_M3_S,
    RTU_SUPPLY_FLOW_M3_S,
    UNMATCHED_TOPOLOGY,
    B59CalibrationParameters,
    build_b59_screening_seed_idf,
    screening_seed_summary,
    screening_zone_specs,
    write_b59_screening_seed_idf,
)


def test_screening_seed_scope_area_and_topology_are_explicit():
    summary = screening_seed_summary()
    assert summary["claim_label"] == "OFFICE_SCREENING_SEED_UNCALIBRATED"
    assert summary["office_floor_count"] == 2
    assert math.isclose(summary["office_floor_area_each_m2"], 2325.0)
    assert math.isclose(summary["office_floor_area_total_m2"], 4650.0)
    assert summary["rtu_service_group_count"] == 4
    assert summary["occupied_zone_count"] == 24
    assert summary["ufad_plenum_zone_count"] == 24
    assert summary["segments_per_rtu_per_floor"] == ["SOUTH_PERIMETER", "CORE", "NORTH_PERIMETER"]
    assert summary["immutable_geometry_scope"]["rtu_groups"] == [1, 2, 3, 4]


def test_calibration_parameters_are_frozen_bounded_and_exclude_geometry():
    parameters = B59CalibrationParameters()
    with pytest.raises(FrozenInstanceError):
        parameters.lighting_w_m2 = 9.0  # type: ignore[misc]
    with pytest.raises(ValueError, match="cooling_cop"):
        replace(parameters, cooling_cop=9.0)
    with pytest.raises(ValueError, match="HVAC must end after occupancy"):
        replace(parameters, weekday_hvac_end_hour=parameters.weekday_occupancy_end_hour)
    with pytest.raises(ValueError, match="15-minute EnergyPlus timestep"):
        replace(parameters, weekday_hvac_end_hour=20.68)
    with pytest.raises(ValueError, match="hvac_availability_mode"):
        replace(parameters, hvac_availability_mode="interpolated")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="occupancy_calendar_mode"):
        replace(parameters, occupancy_calendar_mode="blended")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="TwoSpeedDX rated performance domain"):
        replace(
            parameters,
            cooling_capacity_w=B59CalibrationParameters.BOUNDS["cooling_capacity_w"][0],
            coil_airflow_m3_s=B59CalibrationParameters.BOUNDS["coil_airflow_m3_s"][1],
        )
    assert "floor_length_m" not in parameters.manifest()
    assert "cooling_capacity_w" in parameters.manifest()
    assert "weekday_hvac_start_hour" in parameters.manifest()


def test_zone_layout_preserves_each_floor_rtu_and_core_perimeter_group():
    zones = screening_zone_specs()
    keys = {(zone.floor, zone.rtu_group, zone.segment) for zone in zones}
    assert len(keys) == 24
    for floor in (3, 4):
        for rtu in (1, 2, 3, 4):
            assert (floor, rtu, "SOUTH_PERIMETER") in keys
            assert (floor, rtu, "CORE") in keys
            assert (floor, rtu, "NORTH_PERIMETER") in keys
            assert math.isclose(sum(z.area_m2 for z in zones if z.floor == floor and z.rtu_group == rtu), 581.25)


def test_generated_idf_retains_claim_boundary_and_published_rtu_seed_values():
    idf = build_b59_screening_seed_idf()
    assert f"CLAIM LABEL: {CLAIM_LABEL}" in idf
    assert "NOT AN AS-BUILT OR CALIBRATED MODEL" in idf
    assert "HVACTemplate:System:PackagedVAV" in idf
    assert idf.count("HVACTemplate:System:PackagedVAV,") == 4
    assert idf.count("HVACTemplate:Zone:VAV,") == 24
    assert idf.count("_UFAD_PLENUM") > 24
    assert f"{RTU_SUPPLY_FLOW_M3_S:.8g}" in idf
    assert f"{RTU_MINIMUM_OA_M3_S:.8g}" in idf
    assert f"{RTU_COOLING_CAPACITY_W:.8g}" in idf
    assert "Electricity:Facility" in idf
    assert "PUBLISHED RTU RATING (evidence, not direct coil input)" in idf
    assert "SIMULATION PROXY" in idf
    assert "20 hp supply motor" in idf
    assert "7.5 hp return motor" in idf
    assert "water-cooled DX condenser loop" in idf
    assert len(UNMATCHED_TOPOLOGY) >= 8


def test_published_ratings_are_separate_from_engineering_consistent_proxy():
    summary = screening_seed_summary()
    published = summary["rtu_published_seed_values"]
    proxy = summary["rtu_simulation_proxy"]
    assert published["supply_flow_cfm"] == 20_000.0
    assert published["minimum_outdoor_air_cfm"] == 5_000.0
    assert published["cooling_tons"] == 30.0
    assert published["supply_fan_motor_hp"] == 20.0
    assert published["return_fan_motor_hp"] == 7.5
    assert math.isclose(proxy["coil_airflow_m3_s"], 12_000.0 * CFM_TO_M3_S)
    assert proxy["coil_airflow_m3_s"] < PUBLISHED_RTU_RATINGS.supply_flow_m3_s
    assert "performance domain" in proxy["rationale"]


def test_output_profiles_keep_campaign_runs_lean_and_diagnostics_opt_in():
    lean = build_b59_screening_seed_idf(output_profile="lean")
    assert lean.count("Output:Meter,") == 13
    assert "Hourly;" in lean
    assert "Monthly;" not in lean
    assert "Output:Variable," not in lean
    assert "Output:SQLite," not in lean
    assert "B59:ScopeAudit:PartialMeterBoundProxy" in lean

    diagnostic = build_b59_screening_seed_idf(output_profile="diagnostic")
    assert diagnostic.count("Output:Meter,") == 26
    assert "Monthly;" in diagnostic
    assert "Air System Outdoor Air Mass Flow Rate" in diagnostic
    assert "Output:Variable," in diagnostic
    assert "Output:SQLite," in diagnostic

    with pytest.raises(ValueError, match="unsupported output profile"):
        build_b59_screening_seed_idf(output_profile="verbose")  # type: ignore[arg-type]


def test_run_period_uses_explicit_configurable_calendar_year_for_leap_day():
    default_idf = build_b59_screening_seed_idf()
    expected_default = (
        "RunPeriod,\n  SCREENING_YEAR,\n  1,\n  1,\n"
        f"  {DEFAULT_SIMULATION_YEAR},\n  12,\n  31,\n  {DEFAULT_SIMULATION_YEAR},"
    )
    assert expected_default in default_idf
    assert "explicit so leap-day weather is retained" in default_idf

    alternate_idf = build_b59_screening_seed_idf(simulation_year=2024)
    assert "  2024,\n  12,\n  31,\n  2024," in alternate_idf
    assert screening_seed_summary(simulation_year=2024)["simulation_year"] == 2024
    with pytest.raises(ValueError, match="between 1900 and 2100"):
        build_b59_screening_seed_idf(simulation_year=1800)
    with pytest.raises(TypeError, match="must be an integer"):
        build_b59_screening_seed_idf(simulation_year=True)  # type: ignore[arg-type]


def test_parameter_values_are_bound_into_the_idf_without_changing_scope():
    parameters = replace(
        DEFAULT_CALIBRATION_PARAMETERS,
        lighting_w_m2=9.5,
        coil_airflow_m3_s=12_500.0 * CFM_TO_M3_S,
    )
    idf = build_b59_screening_seed_idf(parameters)
    assert "4.75," in idf
    assert f"{parameters.coil_airflow_m3_s:.8g}" in idf
    assert idf.count("HVACTemplate:System:PackagedVAV,") == 4


def test_discrete_schedule_hypotheses_and_pandemic_step_are_explicit():
    default_idf = build_b59_screening_seed_idf()
    assert "SCREENING_PEOPLE_FRACTION" in default_idf
    assert "SCREENING_LIGHTS_FRACTION" in default_idf
    assert "SCREENING_MEL_FRACTION" in default_idf
    assert "Through: 3/17" in default_idf
    assert "SCREENING_WEEKDAY_FRACTION" not in default_idf

    continuous = replace(DEFAULT_CALIBRATION_PARAMETERS, hvac_availability_mode="continuous")
    continuous_idf = build_b59_screening_seed_idf(continuous)
    assert "Schedule:Constant,\n  SCREENING_HVAC_AVAILABILITY,\n  FRACTION,\n  1;" in continuous_idf

    generic = replace(DEFAULT_CALIBRATION_PARAMETERS, occupancy_calendar_mode="generic")
    generic_idf = build_b59_screening_seed_idf(generic)
    assert "Through: 3/17" not in generic_idf


def test_meter_scope_splits_unmetered_north_lighting_and_fails_claim_closed():
    idf = build_b59_screening_seed_idf()
    assert idf.count("B59_LIGHTS_METERED_SOUTH_PROXY_") > 24
    assert idf.count("B59_LIGHTS_UNMETERED_NORTH_PROXY_") > 24
    assert "Meter:Custom,\n  B59:MeterBound:LightingSouth" in idf
    assert "Meter:Custom,\n  B59:Unmetered:LightingNorth" in idf
    assert "Meter:Custom,\n  B59:MappedRTU:FansPlusCooling" in idf
    assert "Meter:Custom,\n  B59:Unresolved:ElectricTerminalReheat" in idf
    mapped_hvac_block = idf.split("Meter:Custom,\n  B59:MappedRTU:FansPlusCooling", 1)[1].split(";", 1)[0]
    assert "Fans:Electricity" in mapped_hvac_block
    assert "Cooling:Electricity" in mapped_hvac_block
    assert "Heating:Electricity" not in mapped_hvac_block
    assert "Electricity:HVAC" not in mapped_hvac_block

    scope = screening_seed_summary()["meter_scope"]
    assert scope["measured_target_formula"] == "mels_S + mels_N + lig_S + hvac_S + hvac_N"
    assert scope["facility_total_comparison_allowed"] is False
    assert scope["guideline14_claim_eligible"] is False
    assert "elevators" in scope["dispositions"]
    assert "terminal_heat" in scope["dispositions"]
    assert "ashp_wshp" in scope["dispositions"]
    assert scope["model_output_mapping"]["mapped_rtu_fans_plus_cooling"] == "B59:MappedRTU:FansPlusCooling"


def test_writer_is_deterministic_and_does_not_promote_claim(tmp_path):
    first = write_b59_screening_seed_idf(tmp_path / "first.idf")
    second = write_b59_screening_seed_idf(tmp_path / "second.idf")
    assert first.read_bytes() == second.read_bytes()
    text = first.read_text(encoding="utf-8")
    assert CLAIM_LABEL in text
    assert "MONTHLY_CALIBRATED" not in text
    assert "DSM_RESEARCH_READY" not in text
