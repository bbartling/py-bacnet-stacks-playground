"""Tests for the ventilation hypothesis scenario grid."""

from __future__ import annotations

from pathlib import Path

import pytest

from wattlab.energyplus.patches.registry import apply_patch
from wattlab.existing_building.ventilation import (
    INFILTRATION_NOTE,
    ZERO_OA_WARNING,
    build_all_ventilation_scenarios,
    build_ventilation_scenario,
    list_ventilation_scenarios,
)

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "examples" / "prototypes" / "5ZoneAirCooled.idf"

EXPECTED_SCENARIOS = [
    "archetype",
    "1.0",
    "0.75",
    "0.5",
    "0.25",
    "0.1",
    "0.0",
    "stuck_closed",
    "occupied_only",
    "mild_weather_only",
    "off_during_extremes",
    "economizer_disabled",
    "economizer_with_zero_min_oa",
]


def test_scenario_grid_is_complete() -> None:
    assert list_ventilation_scenarios() == EXPECTED_SCENARIOS
    assert set(build_all_ventilation_scenarios()) == set(EXPECTED_SCENARIOS)


@pytest.mark.parametrize(
    "name", ["0.0", "stuck_closed", "economizer_with_zero_min_oa"]
)
def test_zero_oa_scenarios_carry_diagnostic_warning(name: str) -> None:
    scenario = build_ventilation_scenario(name)
    assert ZERO_OA_WARNING in scenario["warnings"]
    assert scenario["metadata"]["diagnostic_only"] is True


@pytest.mark.parametrize("name", EXPECTED_SCENARIOS)
def test_infiltration_zero_false_always(name: str) -> None:
    scenario = build_ventilation_scenario(name)
    assert scenario["metadata"]["infiltration_zero"] is False
    assert INFILTRATION_NOTE in scenario["warnings"]
    assert "unchanged" in scenario["metadata"]["infiltration"]


@pytest.mark.parametrize("name", EXPECTED_SCENARIOS)
def test_params_are_patch_ready(name: str) -> None:
    scenario = build_ventilation_scenario(name)
    assert scenario["patch"] == "outdoor_air_fraction"
    params = scenario["params"]
    assert set(params) == {"min_oa_fraction", "stuck_closed", "economizer_disabled"}
    assert 0.0 <= params["min_oa_fraction"] <= 1.0
    assert isinstance(params["stuck_closed"], bool)
    assert isinstance(params["economizer_disabled"], bool)


@pytest.mark.parametrize("name", EXPECTED_SCENARIOS)
def test_metadata_distinguishes_air_paths(name: str) -> None:
    metadata = build_ventilation_scenario(name)["metadata"]
    # Min OA, infiltration, and economizer are three separate control
    # surfaces that must never be conflated in a screen.
    assert metadata["minimum_outdoor_air"]
    assert metadata["infiltration"]
    assert metadata["economizer"]
    assert metadata["minimum_outdoor_air"] != metadata["infiltration"]
    assert metadata["conceptual_surrogate"] is True


def test_stuck_closed_is_a_fault_not_a_setpoint() -> None:
    scenario = build_ventilation_scenario("stuck_closed")
    assert scenario["params"]["stuck_closed"] is True
    assert scenario["params"]["min_oa_fraction"] == 1.0  # commanded, not delivered


def test_economizer_scenarios_are_distinct() -> None:
    disabled = build_ventilation_scenario("economizer_disabled")
    assert disabled["params"]["economizer_disabled"] is True
    assert disabled["params"]["min_oa_fraction"] == 1.0

    zero_min = build_ventilation_scenario("economizer_with_zero_min_oa")
    assert zero_min["params"]["economizer_disabled"] is False
    assert zero_min["params"]["min_oa_fraction"] == 0.0
    assert "econom" in zero_min["metadata"]["economizer"].lower()


def test_schedule_surrogate_scenarios_are_flagged() -> None:
    for name in ("occupied_only", "mild_weather_only", "off_during_extremes"):
        scenario = build_ventilation_scenario(name)
        assert scenario["metadata"]["requires_schedule_surrogate"] is True
        assert scenario["metadata"]["schedule_surrogate"]
        assert any("surrogate" in w.lower() for w in scenario["warnings"])


def test_numeric_names_normalize() -> None:
    assert build_ventilation_scenario(0.5)["scenario"] == "0.5"
    assert build_ventilation_scenario("0.50")["scenario"] == "0.5"
    assert build_ventilation_scenario("1")["scenario"] == "1.0"


def test_unknown_scenario_raises() -> None:
    with pytest.raises(ValueError, match="Unknown ventilation"):
        build_ventilation_scenario("wide_open_windows")
    with pytest.raises(ValueError, match="Unknown ventilation"):
        build_ventilation_scenario("0.33")


@pytest.mark.parametrize("name", ["0.5", "stuck_closed"])
def test_params_apply_through_patch_registry(tmp_path: Path, name: str) -> None:
    scenario = build_ventilation_scenario(name)
    dest = tmp_path / f"{name}.idf"
    meta = apply_patch(scenario["patch"], PROTOTYPE, dest, scenario["params"])
    assert meta["ok"] is True
    assert dest.is_file()
    if name == "stuck_closed":
        assert meta["effective_fraction"] == 0.0
