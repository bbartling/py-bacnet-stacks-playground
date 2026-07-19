"""Tests for the central IDF patch registry (extracted from easy_button)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wattlab.easy_button import _apply_patch
from wattlab.energyplus.patches.registry import apply_patch, known_patch_names

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "examples" / "prototypes" / "5ZoneAirCooled.idf"

# Every name easy_button._apply_patch historically accepted must dispatch.
LEGACY_NAME_TO_PATCH = {
    "fan_avail_continuous": "fan_avail_continuous",
    "baseline_continuous": "fan_avail_continuous",
    "fan_avail_occupied_office": "fan_avail_occupied_office",
    "schedule_occupied": "fan_avail_occupied_office",
    "gl36_airside_proxy": "gl36_airside_proxy",
    "gl36_proxy": "gl36_airside_proxy",
    "chiller_lockout": "chiller_lockout",
    "mech_oat_lockout": "chiller_lockout",
    "sat_reset": "sat_reset",
    "sat_reset_proxy": "sat_reset",
    "high_performance_glazing": "high_performance_glazing",
    "condensing_boiler": "condensing_boiler",
    "high_efficiency_chiller": "high_efficiency_chiller",
    "premium_fan_vfd": "premium_fan_vfd",
    "awhp_surrogate": "awhp_surrogate",
}


def test_registry_covers_all_legacy_names() -> None:
    names = set(known_patch_names())
    assert set(LEGACY_NAME_TO_PATCH) <= names


@pytest.mark.parametrize(("name", "expected_patch"), sorted(LEGACY_NAME_TO_PATCH.items()))
def test_known_patch_names_dispatch(tmp_path: Path, name: str, expected_patch: str) -> None:
    dest = tmp_path / f"{name}.idf"
    meta = apply_patch(name, PROTOTYPE, dest)
    assert meta["patch"] == expected_patch
    assert meta["ok"] is True
    assert dest.is_file()


@pytest.mark.parametrize(
    ("name", "params", "expected_patch"),
    [
        ("hourly_outputs", {}, "hourly_outputs"),
        ("monthly_energy_tables", {}, "monthly_energy_tables"),
        (
            "capacity_factors",
            {"factors": {"fan_pressure": 0.8}},
            "capacity_factors",
        ),
        ("outdoor_air_fraction", {"min_oa_fraction": 0.5}, "outdoor_air_fraction"),
    ],
)
def test_new_patch_names_dispatch(
    tmp_path: Path, name: str, params: dict, expected_patch: str
) -> None:
    dest = tmp_path / f"{name}.idf"
    meta = apply_patch(name, PROTOTYPE, dest, params)
    assert meta["patch"] == expected_patch
    assert dest.is_file()


def test_registry_params_are_forwarded(tmp_path: Path) -> None:
    dest = tmp_path / "lockout.idf"
    meta = apply_patch("chiller_lockout", PROTOTYPE, dest, {"oat_lockout_f": 60.0})
    assert meta["oat_lockout_f"] == 60.0
    assert meta["temperature_c"] == 15.6


def test_unknown_patch_name_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown idf_patch name"):
        apply_patch("no_such_patch", PROTOTYPE, tmp_path / "x.idf")


def test_easy_button_facade_uses_registry(tmp_path: Path) -> None:
    dest = tmp_path / "facade.idf"
    measure = {"idf_patch": {"name": "premium_fan_vfd", "params": {"pressure_pa": 350.0}}}
    meta = _apply_patch("premium_fan_vfd", PROTOTYPE, dest, measure)
    assert meta["patch"] == "premium_fan_vfd"
    assert meta["pressure_pa"] == 350.0
    assert meta["ok"] is True
