"""Tests for explicit deep-retrofit EnergyPlus text patches."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from wattlab.easy_button import _apply_patch
from wattlab.energyplus.patches import (
    apply_air_to_water_heat_pump_surrogate,
    apply_condensing_boiler_efficiency,
    apply_high_efficiency_chiller,
    apply_high_performance_glazing,
    apply_premium_fan_vfd,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "examples" / "prototypes" / "5ZoneAirCooled.idf"


def _objects(text: str, object_type: str) -> list[str]:
    pattern = re.compile(
        rf"(?ms)^[ \t]*{re.escape(object_type)}[ \t]*,[ \t]*\r?\n"
        rf".*?;[^\r\n]*(?:\r?\n|$)"
    )
    return pattern.findall(text)


def _comment_value(block: str, comment: str) -> str:
    match = re.search(
        rf"(?m)^[ \t]*([^,!;]*?)[,;][ \t]*!-[ \t]*{re.escape(comment)}[ \t]*$",
        block,
    )
    assert match, f"Missing field comment {comment!r}"
    return match.group(1).strip()


def test_high_performance_glazing_patches_only_fenestration_constructions(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "glazing.idf"
    meta = apply_high_performance_glazing(PROTOTYPE, dest)
    before = PROTOTYPE.read_text(encoding="utf-8")
    after = dest.read_text(encoding="utf-8")

    assert meta["ok"] is True
    assert meta["fenestration_surfaces_patched"] == 6
    assert meta["glazing_materials_added"] == 1
    assert meta["constructions_added"] == 1
    assert "conceptual_envelope_proxy" in meta["flags"]
    assert after.count("! WattLab deep retrofit: high_performance_glazing") == 1
    assert len(_objects(after, "WindowMaterial:SimpleGlazingSystem")) == 1
    assert len(_objects(after, "Construction")) == len(_objects(before, "Construction")) + 1
    for block in _objects(after, "FenestrationSurface:Detailed"):
        assert _comment_value(block, "Construction Name") == "WattLab High Performance Glazing"
    before_opaque = [
        _comment_value(block, "Construction Name")
        for block in _objects(before, "BuildingSurface:Detailed")
    ]
    after_opaque = [
        _comment_value(block, "Construction Name")
        for block in _objects(after, "BuildingSurface:Detailed")
    ]
    assert after_opaque == before_opaque
    assert "1.4,                     !- U-Factor {W/m2-K}" in after
    assert "0.3,                     !- Solar Heat Gain Coefficient" in after
    assert "0.5;                     !- Visible Transmittance" in after


def test_high_performance_glazing_is_idempotent(tmp_path: Path) -> None:
    first = tmp_path / "first.idf"
    second = tmp_path / "second.idf"
    apply_high_performance_glazing(PROTOTYPE, first)
    meta = apply_high_performance_glazing(first, second)
    text = second.read_text(encoding="utf-8")

    assert meta["ok"] is True
    assert meta["fenestration_surfaces_patched"] == 6
    assert meta["glazing_materials_added"] == 0
    assert meta["constructions_added"] == 0
    assert text.count("! WattLab deep retrofit: high_performance_glazing") == 1
    assert len(_objects(text, "WindowMaterial:SimpleGlazingSystem")) == 1
    assert len(
        [
            block
            for block in _objects(text, "Construction")
            if "WattLab High Performance Glazing" in block
        ]
    ) == 1


def test_high_performance_glazing_reapply_updates_existing_material(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.idf"
    second = tmp_path / "second.idf"
    apply_high_performance_glazing(PROTOTYPE, first)
    meta = apply_high_performance_glazing(
        first,
        second,
        u_factor=1.1,
        shgc=0.25,
        visible_transmittance=0.45,
    )
    text = second.read_text(encoding="utf-8")
    materials = _objects(text, "WindowMaterial:SimpleGlazingSystem")

    assert len(materials) == 1
    assert _comment_value(materials[0], "U-Factor {W/m2-K}") == "1.1"
    assert _comment_value(materials[0], "Solar Heat Gain Coefficient") == "0.25"
    assert _comment_value(materials[0], "Visible Transmittance") == "0.45"
    assert meta["glazing_materials_added"] == 0
    assert meta["glazing_materials_updated"] == 1
    assert meta["glazing_materials_patched"] == 1
    assert meta["u_factor"] == 1.1
    assert meta["shgc"] == 0.25
    assert meta["visible_transmittance"] == 0.45


@pytest.mark.parametrize(
    ("patch", "kwargs"),
    [
        (apply_high_performance_glazing, {"u_factor": 0}),
        (apply_high_performance_glazing, {"u_factor": float("nan")}),
        (apply_high_performance_glazing, {"shgc": 1.01}),
        (apply_high_performance_glazing, {"visible_transmittance": -0.01}),
        (apply_condensing_boiler_efficiency, {"efficiency": 1.01}),
        (apply_high_efficiency_chiller, {"cop": 0}),
        (apply_premium_fan_vfd, {"total_efficiency": 0}),
        (apply_premium_fan_vfd, {"motor_efficiency": 1.01}),
        (apply_premium_fan_vfd, {"pressure_pa": -1}),
        (apply_premium_fan_vfd, {"min_flow_fraction": 1.01}),
        (apply_air_to_water_heat_pump_surrogate, {"cop": 0}),
    ],
)
def test_physical_bounds_fail_without_writing(
    tmp_path: Path, patch, kwargs: dict[str, float]
) -> None:
    dest = tmp_path / "invalid.idf"
    with pytest.raises(ValueError):
        patch(PROTOTYPE, dest, **kwargs)
    assert not dest.exists()


@pytest.mark.parametrize(
    "patch",
    [
        apply_high_performance_glazing,
        apply_condensing_boiler_efficiency,
        apply_high_efficiency_chiller,
        apply_premium_fan_vfd,
        apply_air_to_water_heat_pump_surrogate,
    ],
)
def test_missing_target_fails_closed_without_writing(tmp_path: Path, patch) -> None:
    src = tmp_path / "empty.idf"
    src.write_text("Version,25.1;\n", encoding="utf-8")
    dest = tmp_path / "should-not-exist.idf"

    with pytest.raises(ValueError, match="target"):
        patch(src, dest)
    assert not dest.exists()


def test_direct_equipment_efficiency_patches_have_exact_counts(tmp_path: Path) -> None:
    boiler_dest = tmp_path / "boiler.idf"
    boiler_meta = apply_condensing_boiler_efficiency(
        PROTOTYPE, boiler_dest, efficiency=0.95
    )
    boiler = _objects(boiler_dest.read_text(encoding="utf-8"), "Boiler:HotWater")
    assert boiler_meta["ok"] is True
    assert boiler_meta["boilers_patched"] == 1
    assert _comment_value(boiler[0], "Nominal Thermal Efficiency") == "0.95"
    assert "screening" in " ".join(boiler_meta["flags"])
    assert "conceptual_major_equipment_replacement" in boiler_meta["flags"]

    chiller_dest = tmp_path / "chiller.idf"
    chiller_meta = apply_high_efficiency_chiller(PROTOTYPE, chiller_dest, cop=6.1)
    chiller = _objects(chiller_dest.read_text(encoding="utf-8"), "Chiller:Electric")
    assert chiller_meta["ok"] is True
    assert chiller_meta["chillers_patched"] == 1
    assert _comment_value(chiller[0], "Nominal COP {W/W}") == "6.1"
    assert _comment_value(chiller[0], "Condenser Type") == "AirCooled"
    assert "screening" in " ".join(chiller_meta["flags"])
    assert "conceptual_major_equipment_replacement" in chiller_meta["flags"]


def test_premium_fan_vfd_patches_all_requested_fields(tmp_path: Path) -> None:
    dest = tmp_path / "fan.idf"
    meta = apply_premium_fan_vfd(
        PROTOTYPE,
        dest,
        total_efficiency=0.75,
        motor_efficiency=0.95,
        pressure_pa=400,
        min_flow_fraction=0.10,
    )
    fans = _objects(dest.read_text(encoding="utf-8"), "Fan:VariableVolume")

    assert meta["ok"] is True
    assert meta["fans_patched"] == 1
    assert meta["fields_patched"] == 4
    assert _comment_value(fans[0], "Fan Total Efficiency") == "0.75"
    assert _comment_value(fans[0], "Motor Efficiency") == "0.95"
    assert _comment_value(fans[0], "Pressure Rise {Pa}") == "400"
    assert _comment_value(fans[0], "Fan Power Minimum Flow Fraction") == "0.1"


def test_awhp_is_explicit_electric_boiler_surrogate(tmp_path: Path) -> None:
    dest = tmp_path / "awhp.idf"
    meta = apply_air_to_water_heat_pump_surrogate(PROTOTYPE, dest, cop=2.8)
    boiler = _objects(dest.read_text(encoding="utf-8"), "Boiler:HotWater")[0]

    assert meta["ok"] is True
    assert meta["boilers_patched"] == 1
    assert meta["fuel_types_patched"] == 1
    assert meta["efficiencies_patched"] == 1
    assert _comment_value(boiler, "Fuel Type") == "Electricity"
    assert _comment_value(boiler, "Nominal Thermal Efficiency") == "2.8"
    assert "conceptual_system_surrogate" in meta["flags"]
    assert "surrogate" in meta["description"].lower()


@pytest.mark.parametrize(
    ("name", "expected_patch"),
    [
        ("high_performance_glazing", "high_performance_glazing"),
        ("condensing_boiler", "condensing_boiler"),
        ("high_efficiency_chiller", "high_efficiency_chiller"),
        ("premium_fan_vfd", "premium_fan_vfd"),
        ("awhp_surrogate", "awhp_surrogate"),
    ],
)
def test_easy_button_wires_deep_retrofit_patch_names(
    tmp_path: Path, name: str, expected_patch: str
) -> None:
    dest = tmp_path / f"{name}.idf"
    meta = _apply_patch(name, PROTOTYPE, dest)
    assert meta["ok"] is True
    assert meta["patch"] == expected_patch


@pytest.mark.parametrize(
    ("name", "params"),
    [
        (
            "high_performance_glazing",
            {"u_factor": None, "shgc": None, "visible_transmittance": None},
        ),
        ("condensing_boiler", {"efficiency": None}),
        ("high_efficiency_chiller", {"cop": None}),
        (
            "premium_fan_vfd",
            {
                "total_efficiency": None,
                "motor_efficiency": None,
                "pressure_pa": None,
                "min_flow_fraction": None,
            },
        ),
        ("awhp_surrogate", {"cop": None}),
    ],
)
def test_easy_button_explicit_null_params_use_defaults(
    tmp_path: Path, name: str, params: dict[str, None]
) -> None:
    dest = tmp_path / f"{name}-null.idf"
    measure = {"idf_patch": {"name": name, "params": params}}
    meta = _apply_patch(name, PROTOTYPE, dest, measure)
    assert meta["ok"] is True


@pytest.mark.skipif(
    os.environ.get("RUN_ENERGYPLUS_DOCKER") != "1",
    reason="set RUN_ENERGYPLUS_DOCKER=1 to run annual EnergyPlus scenarios",
)
@pytest.mark.parametrize(
    ("name", "patch"),
    [
        ("glazing", apply_high_performance_glazing),
        ("boiler", apply_condensing_boiler_efficiency),
        ("chiller", apply_high_efficiency_chiller),
        ("fan", apply_premium_fan_vfd),
        ("awhp", apply_air_to_water_heat_pump_surrogate),
    ],
)
def test_patched_idf_runs_in_energyplus_docker(
    tmp_path: Path, name: str, patch
) -> None:
    from wattlab.config import DEFAULT_MADISON_EPW
    from wattlab.energyplus.docker import run_energyplus

    idf = tmp_path / f"{name}.idf"
    patch(PROTOTYPE, idf)
    proc = run_energyplus(idf, DEFAULT_MADISON_EPW, tmp_path / f"out-{name}")
    assert proc.returncode == 0, (proc.stdout or "")[-2000:] + (proc.stderr or "")[-2000:]
