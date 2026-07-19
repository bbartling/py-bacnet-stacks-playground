"""Tests for sizing inventory parsing, capacity factors, and OA patches."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from wattlab.energyplus.patches.capacity import apply_capacity_factors
from wattlab.energyplus.patches.ventilation import apply_outdoor_air_fraction
from wattlab.energyplus.sizing import (
    freeze_autosized_values,
    inventory_resolver,
    parse_sizing_inventory,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TINY_IDF = FIXTURES / "tiny_capacity.idf"


@pytest.fixture()
def output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "output"
    out.mkdir()
    shutil.copy2(FIXTURES / "sizing_eplusout.eio", out / "eplusout.eio")
    shutil.copy2(FIXTURES / "sizing_eplustbl.csv", out / "eplustbl.csv")
    return out


def _field_value(text: str, object_type: str, comment: str) -> str:
    block_re = re.compile(
        rf"(?ms)^[ \t]*{re.escape(object_type)}[ \t]*,[ \t]*\r?\n"
        rf".*?;[^\r\n]*(?:\r?\n|$)"
    )
    block = block_re.search(text)
    assert block, f"missing {object_type} object"
    m = re.search(
        rf"(?m)^[ \t]*([^,!;]*?)[,;][ \t]*!-[ \t]*{re.escape(comment)}[ \t]*$",
        block.group(0),
    )
    assert m, f"missing field {comment!r} in {object_type}"
    return m.group(1).strip()


def test_parse_sizing_inventory_from_synthetic_outputs(output_dir: Path) -> None:
    inv = parse_sizing_inventory(output_dir)

    assert inv["counts"]["zones"] == 3
    assert inv["counts"]["systems"] == 2
    assert inv["counts"]["components"] == 15
    space1_cooling = inv["zones"][0]
    assert space1_cooling["zone"] == "SPACE1-1"
    assert space1_cooling["load_type"] == "Cooling"
    assert space1_cooling["user_design_load_w"] == pytest.approx(4008.46969)
    assert space1_cooling["user_design_air_flow_m3s"] == pytest.approx(0.23561)

    cooling_system = inv["systems"][0]
    assert cooling_system["system"] == "VAV SYS 1"
    assert cooling_system["load_type"] == "Cooling"
    assert cooling_system["user_design_capacity_w"] == pytest.approx(24519.85074)
    assert cooling_system["user_design_air_flow_m3s"] == pytest.approx(1.05935)

    chiller = [
        c
        for c in inv["components"]
        if c["object_type"] == "Chiller:Electric"
        and "Nominal Capacity" in c["description"]
    ]
    assert len(chiller) == 1
    assert chiller[0]["value"] == pytest.approx(34875.51811)

    tables = inv["tables"]
    assert [r["name"] for r in tables["central_plant"]] == [
        "CENTRAL CHILLER",
        "CENTRAL BOILER",
    ]
    assert tables["central_plant"][0]["Nominal Capacity [W]"] == pytest.approx(34875.52)
    assert tables["fans"][0]["name"] == "SUPPLY FAN 1"
    assert tables["fans"][0]["Delta Pressure [pa]"] == pytest.approx(600.0)
    assert tables["cooling_coils"][0]["Nominal Total Capacity [W]"] == pytest.approx(
        28911.62
    )
    assert len(tables["heating_coils"]) == 2


def test_inventory_resolver_matches_case_insensitively(output_dir: Path) -> None:
    resolve = inventory_resolver(parse_sizing_inventory(output_dir))
    assert resolve("Chiller:Electric", "Central Chiller", "Nominal Capacity {W}") == (
        pytest.approx(34875.51811)
    )
    assert resolve("Fan:VariableVolume", "Supply Fan 1", "Maximum Flow Rate {m3/s}") == (
        pytest.approx(1.05935)
    )
    assert resolve("Chiller:Electric", "Central Chiller", "No Such Field {W}") is None
    assert resolve("Boiler:HotWater", "Other Boiler", "Nominal Capacity {W}") is None


def test_capacity_factors_scale_intended_numeric_fields(tmp_path: Path) -> None:
    dest = tmp_path / "scaled.idf"
    meta = apply_capacity_factors(
        TINY_IDF,
        dest,
        {"fan_pressure": 0.8, "terminal_airflow": 1.25},
    )
    text = dest.read_text(encoding="utf-8")

    assert meta["ok"] is True
    assert _field_value(text, "Fan:VariableVolume", "Pressure Rise {Pa}") == "480"
    # Autosized terminal airflow has no resolver here: left autosized.
    assert (
        _field_value(
            text, "AirTerminal:SingleDuct:VAV:Reheat", "Maximum Air Flow Rate {m3/s}"
        )
        == "autosize"
    )
    assert meta["fields_scaled"] == 1
    assert meta["autosize_unresolved"] == 1
    # Untouched categories stay put.
    assert _field_value(text, "Chiller:Electric", "Nominal Capacity {W}") == "autosize"
    assert _field_value(text, "Fan:VariableVolume", "Fan Total Efficiency") == "0.7"
    assert "conceptual_capacity_screen" in meta["flags"]


def test_capacity_factors_fan_power_surrogate_is_labeled(tmp_path: Path) -> None:
    dest = tmp_path / "fan_power.idf"
    meta = apply_capacity_factors(TINY_IDF, dest, {"fan_power": 0.5})
    text = dest.read_text(encoding="utf-8")
    assert _field_value(text, "Fan:VariableVolume", "Pressure Rise {Pa}") == "300"
    assert "fan_power_scaled_via_pressure_rise_surrogate" in meta["flags"]


def test_capacity_factors_reject_bad_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown capacity category"):
        apply_capacity_factors(TINY_IDF, tmp_path / "bad.idf", {"nonsense": 1.0})
    with pytest.raises(ValueError, match="finite and > 0"):
        apply_capacity_factors(TINY_IDF, tmp_path / "bad.idf", {"fan_pressure": 0.0})


def test_freeze_autosized_values_uses_inventory(
    tmp_path: Path, output_dir: Path
) -> None:
    inv = parse_sizing_inventory(output_dir)
    dest = tmp_path / "frozen.idf"
    meta = freeze_autosized_values(
        TINY_IDF, dest, inv, {"cooling_plant": 1.2, "heating_plant": 0.9}
    )
    text = dest.read_text(encoding="utf-8")

    # Frozen at design value x factor.
    assert _field_value(text, "Chiller:Electric", "Nominal Capacity {W}") == "41850.6"
    assert _field_value(text, "Boiler:HotWater", "Nominal Capacity {W}") == "36944.2"
    # Categories without an explicit factor freeze at 1.0 x design value.
    assert _field_value(text, "Fan:VariableVolume", "Maximum Flow Rate {m3/s}") == (
        "1.05935"
    )
    assert (
        _field_value(
            text, "AirTerminal:SingleDuct:VAV:Reheat", "Maximum Air Flow Rate {m3/s}"
        )
        == "0.23561"
    )
    assert _field_value(text, "Coil:Heating:Water", "Rated Capacity {W}") == "12244.3"
    assert (
        _field_value(text, "Coil:Cooling:Water", "Design Water Flow Rate {m3/s}")
        == "0.00135079"
    )
    # Numeric fan pressure scaled by the default 1.0 factor stays 600.
    assert _field_value(text, "Fan:VariableVolume", "Pressure Rise {Pa}") == "600"
    assert meta["autosize_frozen"] >= 6
    assert "cooling_coil_capacity_scaled_via_water_flow_surrogate" in meta["flags"]
    assert meta["patch"] == "freeze_autosized_values"
    assert meta["ok"] is True


def test_zero_oa_does_not_clear_infiltration(tmp_path: Path) -> None:
    before = TINY_IDF.read_text(encoding="utf-8")
    dest = tmp_path / "oa_zero.idf"
    meta = apply_outdoor_air_fraction(TINY_IDF, dest, 0.0, stuck_closed=True)
    text = dest.read_text(encoding="utf-8")

    # Infiltration untouched (design flow value preserved verbatim).
    infil_re = re.compile(
        r"(?ms)^[ \t]*ZoneInfiltration:DesignFlowRate[ \t]*,[ \t]*\r?\n"
        r".*?;[^\r\n]*(?:\r?\n|$)"
    )
    assert infil_re.findall(text) == infil_re.findall(before)
    assert (
        _field_value(text, "ZoneInfiltration:DesignFlowRate", "Design Flow Rate {m3/s}")
        == "0.032"
    )
    assert meta["infiltration_objects_preserved"] == 1
    assert "zero_oa_infiltration_preserved" in meta["flags"]
    assert "oa_damper_stuck_closed_surrogate" in meta["flags"]

    # OA controller now points at the constant zero-fraction schedule.
    assert (
        _field_value(
            text, "Controller:OutdoorAir", "Minimum Outdoor Air Schedule Name"
        )
        == "WattLab Min OA Fraction Sched"
    )
    assert "Until: 24:00,0;" in text
    assert meta["effective_fraction"] == 0.0


def test_outdoor_air_fraction_and_economizer_disable(tmp_path: Path) -> None:
    dest = tmp_path / "oa_half.idf"
    meta = apply_outdoor_air_fraction(
        TINY_IDF, dest, 0.5, economizer_disabled=True
    )
    text = dest.read_text(encoding="utf-8")
    assert (
        _field_value(text, "Controller:OutdoorAir", "Economizer Control Type")
        == "NoEconomizer"
    )
    assert "Until: 24:00,0.5;" in text
    assert meta["controllers_patched"] == 1
    assert meta["economizers_patched"] == 1
    assert "min_oa_fraction_of_design_min_oa_not_supply_flow" in meta["flags"]
    assert "conceptual_ventilation_surrogate" in meta["flags"]


def test_outdoor_air_fraction_bounds(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="min_oa_fraction"):
        apply_outdoor_air_fraction(TINY_IDF, tmp_path / "bad.idf", 1.5)
