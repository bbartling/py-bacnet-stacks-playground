"""Unit contract tests for WattLab's SI-first quantity layer."""

from __future__ import annotations

import pytest

from wattlab.units import (
    DisplayMode,
    Quantity,
    convert,
    convert_absolute_temperature,
    convert_temperature_delta,
    display_quantity,
    public_quantity,
)


@pytest.mark.parametrize(
    ("value", "ip_unit", "si_unit"),
    [
        (100.0, "ft2", "m2"),
        (100.0, "ft", "m"),
        (1000.0, "CFM", "m3/s"),
        (100.0, "GPM", "L/s"),
        (2.0, "inWC", "Pa"),
        (15.0, "psi", "kPa"),
        (10.0, "hp", "kW"),
        (12000.0, "Btu/h", "W"),
        (120.0, "MBH", "kW"),
        (10.0, "ton", "kW_cooling"),
        (1.0, "therm", "kWh"),
        (1.0, "therm", "MJ"),
        (1.0, "therm", "GJ"),
        (1.0, "MMBtu", "GJ"),
        (70.0, "kBtu/ft2", "kWh/m2"),
        (10.0, "Btu/lb", "kJ/kg"),
        (0.25, "Btu/lbF", "kJ/kgK"),
        (1000.0, "lb/h", "kg/s"),
        (1000.0, "F-day", "K-day"),
        (25.0, "$/ft2", "$/m2"),
        (1000.0, "lbCO2e", "kgCO2e"),
    ],
)
def test_ip_si_conversions_round_trip(value: float, ip_unit: str, si_unit: str) -> None:
    converted = convert(value, ip_unit, si_unit)
    assert convert(converted, si_unit, ip_unit) == pytest.approx(value)


def test_efficiency_conversions_round_trip() -> None:
    cop = convert(0.75, "kW/ton", "COP")
    assert cop == pytest.approx(4.68913712)
    assert convert(cop, "COP", "kW/ton") == pytest.approx(0.75)
    assert convert(12.0, "EER", "COP") == pytest.approx(3.51685284)
    assert convert(convert(12.0, "EER", "COP"), "COP", "EER") == pytest.approx(12.0)


def test_absolute_and_delta_temperature_are_separate() -> None:
    assert convert_absolute_temperature(32.0, "F", "C") == pytest.approx(0.0)
    assert convert_absolute_temperature(0.0, "C", "F") == pytest.approx(32.0)
    assert convert_temperature_delta(18.0, "deltaF", "deltaC") == pytest.approx(10.0)
    assert convert_temperature_delta(18.0, "deltaF", "K") == pytest.approx(10.0)
    assert convert_temperature_delta(10.0, "K", "deltaF") == pytest.approx(18.0)

    with pytest.raises(ValueError, match="absolute"):
        convert_temperature_delta(32.0, "F", "C")
    with pytest.raises(ValueError, match="difference"):
        convert_absolute_temperature(18.0, "deltaF", "deltaC")
    with pytest.raises(ValueError, match="dedicated"):
        convert(32.0, "F", "C")


def test_quantity_is_finite_and_public_tag_is_explicit() -> None:
    quantity = public_quantity(1000.0, "CFM", "volumetric_flow", tags={"measured"})
    assert quantity.is_public
    assert quantity.tags == frozenset({"public", "measured"})
    assert quantity.to("m3/s").value == pytest.approx(0.47194745)

    with pytest.raises(ValueError, match="finite"):
        Quantity(float("nan"), "kW", "power")


def test_display_modes_select_expected_units() -> None:
    quantity = public_quantity(1000.0, "CFM", "volumetric_flow")
    assert display_quantity(quantity, DisplayMode.IMPERIAL) == "1,000 CFM"
    assert display_quantity(quantity, DisplayMode.METRIC) == "0.472 m3/s"
    assert display_quantity(quantity, DisplayMode.SOURCE) == "1,000 CFM"
    assert display_quantity(quantity, DisplayMode.DUAL) == "1,000 CFM (0.472 m3/s)"
