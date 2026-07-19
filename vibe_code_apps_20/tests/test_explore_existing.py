from __future__ import annotations

import json

from wattlab.existing_building.explore import REQUIRED_ARTIFACTS, run_explore_existing


def _config() -> dict:
    return {
        "project_id": "synthetic-existing",
        "building_type": "office",
        "city": "madison",
        "floor_area_ft2": 42000,
        "capacity": {
            "factors": [1.0, 0.8, 0.5],
            "independent_factors": [{"cooling": 0.75, "heating": 1.0}],
        },
        "operating_hours": [{"name": "weekday_10h", "weekday_hours": 10}],
        "ventilation": [{"name": "zero_oa", "oa_fraction": 0.0}],
        "search": {"max_scenarios": 12},
    }


def test_dry_run_writes_all_artifacts(tmp_path):
    result = run_explore_existing(_config(), dry_run=True, out_dir=tmp_path)
    assert result["badge"] == "CONCEPTUAL_HYPOTHESIS"
    assert set(REQUIRED_ARTIFACTS) <= {p.name for p in tmp_path.iterdir()}


def test_scenario_hashes_are_deterministic(tmp_path):
    run_explore_existing(_config(), dry_run=True, out_dir=tmp_path / "a")
    run_explore_existing(_config(), dry_run=True, out_dir=tmp_path / "b")
    a = json.loads((tmp_path / "a" / "scenario_registry.json").read_text())
    b = json.loads((tmp_path / "b" / "scenario_registry.json").read_text())
    assert [row["scenario_hash"] for row in a] == [row["scenario_hash"] for row in b]


def test_reduced_capacity_does_not_claim_automatic_savings(tmp_path):
    run_explore_existing(_config(), dry_run=True, out_dir=tmp_path)
    rows = json.loads((tmp_path / "scenario_results.json").read_text())
    reduced = [row for row in rows if row["scenario_type"] == "capacity" and row["parameters"]["factor"] < 1]
    assert reduced
    assert all(row["savings_kwh"] is None for row in reduced)
    assert all("unmet_hours" in row and "runtime_hours" in row for row in reduced)


def test_mission_style_config_builds_scenarios(tmp_path):
    """capacity_factors / ventilation_scenarios / dict operating_hours."""
    cfg = {
        "project_id": "mission-style",
        "building_type": "school",
        "city": "detroit",
        "floor_area_ft2": 100000,
        "capacity_factors": {
            "cooling_plant": [1.0, 0.7],
            "heating_plant": [1.0, 0.6],
        },
        "operating_hours": {
            "occupied": {"monday_friday": ["07:00", "17:00"]},
            "weather_extensions": {
                "hot": {"allow_overnight": False},
                "cold": {"allow_overnight": True},
            },
        },
        "ventilation_scenarios": ["archetype", "0.0", "stuck_closed"],
        "max_scenarios": 20,
    }
    result = run_explore_existing(cfg, dry_run=True, out_dir=tmp_path)
    assert result["badge"] == "CONCEPTUAL_HYPOTHESIS"
    registry = json.loads((tmp_path / "scenario_registry.json").read_text())
    types = {row["scenario_type"] for row in registry}
    assert {"reference", "capacity", "operating_hours", "ventilation"} <= types
    assert len(registry) <= 20
