"""Fail-closed engineering unit conversions with SI as the reference basis."""

from __future__ import annotations

from math import isfinite

_LINEAR: dict[str, tuple[str, float, str]] = {
    "ft2": ("area", 0.09290304, "ft2"),
    "m2": ("area", 1.0, "m2"),
    "ft": ("length", 0.3048, "ft"),
    "m": ("length", 1.0, "m"),
    "cfm": ("volumetric_flow", 0.00047194745, "CFM"),
    "m3/s": ("volumetric_flow", 1.0, "m3/s"),
    "gpm": ("liquid_flow", 0.0630901964, "GPM"),
    "l/s": ("liquid_flow", 1.0, "L/s"),
    "inwc": ("pressure", 249.08891, "inWC"),
    "pa": ("pressure", 1.0, "Pa"),
    "psi": ("pressure_kpa", 6.894757293, "psi"),
    "kpa": ("pressure_kpa", 1.0, "kPa"),
    "hp": ("power_kw", 0.745699872, "hp"),
    "kw": ("power_kw", 1.0, "kW"),
    "btu/h": ("power_w", 0.29307107, "Btu/h"),
    "w": ("power_w", 1.0, "W"),
    "mbh": ("power_kw_mbh", 0.29307107, "MBH"),
    "kw:mbh": ("power_kw_mbh", 1.0, "kW"),
    "ton": ("cooling_capacity", 3.5168528420667, "ton"),
    "kw_cooling": ("cooling_capacity", 1.0, "kW_cooling"),
    "therm": ("energy_therm", 105.505585262, "therm"),
    "kwh": ("energy_therm", 3.6, "kWh"),
    "mj": ("energy_therm", 1.0, "MJ"),
    "gj": ("energy_therm", 1000.0, "GJ"),
    "mmbtu": ("energy_mmbtu", 1.05505585262, "MMBtu"),
    "gj:mmbtu": ("energy_mmbtu", 1.0, "GJ"),
    "kbtu/ft2": ("energy_intensity", 3.154590745, "kBtu/ft2"),
    "kwh/m2": ("energy_intensity", 1.0, "kWh/m2"),
    "btu/lb": ("specific_energy", 2.326, "Btu/lb"),
    "kj/kg": ("specific_energy", 1.0, "kJ/kg"),
    "btu/lbf": ("specific_heat", 4.1868, "Btu/lbF"),
    "kj/kgk": ("specific_heat", 1.0, "kJ/kgK"),
    "lb/h": ("mass_flow", 0.000125997881, "lb/h"),
    "kg/s": ("mass_flow", 1.0, "kg/s"),
    "f-day": ("degree_day", 5.0 / 9.0, "F-day"),
    "k-day": ("degree_day", 1.0, "K-day"),
    "$/ft2": ("area_cost", 10.7639104167, "$/ft2"),
    "$/m2": ("area_cost", 1.0, "$/m2"),
    "lbco2e": ("emissions_mass", 0.45359237, "lbCO2e"),
    "kgco2e": ("emissions_mass", 1.0, "kgCO2e"),
}


def _key(unit: str) -> str:
    key = unit.strip().replace(" ", "").lower()
    aliases = {
        "ft^2": "ft2",
        "m^2": "m2",
        "m3/sec": "m3/s",
        "l/sec": "l/s",
        "inh2o": "inwc",
        "tons": "ton",
        "kwcooling": "kw_cooling",
        "kw-cooling": "kw_cooling",
        "btu/lb-f": "btu/lbf",
        "btu/lbdegf": "btu/lbf",
    }
    return aliases.get(key, key)


def _linear_entry(unit: str, other_unit: str) -> tuple[str, float, str]:
    key = _key(unit)
    other_key = _key(other_unit)
    # kW and GJ occur in more than one independent conversion family.
    if key == "kw" and other_key == "mbh":
        key = "kw:mbh"
    if key == "gj" and other_key == "mmbtu":
        key = "gj:mmbtu"
    try:
        return _LINEAR[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported unit: {unit!r}") from exc


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert supported non-temperature units.

    Temperature conversion is intentionally excluded so callers must state
    whether a value is an absolute temperature or a temperature difference.
    """

    number = float(value)
    if not isfinite(number):
        raise ValueError("value must be finite")
    from_key, to_key = _key(from_unit), _key(to_unit)
    temperature_units = {"f", "c", "deltaf", "deltac", "k"}
    if from_key in temperature_units or to_key in temperature_units:
        raise ValueError(
            "Temperature conversion requires the dedicated absolute or "
            "temperature-difference function"
        )
    if {from_key, to_key} <= {"kw/ton", "cop"}:
        if number <= 0:
            raise ValueError("efficiency value must be > 0")
        return 3.5168528420667 / number
    if {from_key, to_key} <= {"eer", "cop"}:
        return number / 3.412141633 if from_key == "eer" else number * 3.412141633
    source = _linear_entry(from_unit, to_unit)
    target = _linear_entry(to_unit, from_unit)
    if source[0] != target[0]:
        raise ValueError(
            f"Incompatible units: {from_unit!r} ({source[0]}) and "
            f"{to_unit!r} ({target[0]})"
        )
    return number * source[1] / target[1]


def convert_absolute_temperature(value: float, from_unit: str, to_unit: str) -> float:
    """Convert absolute dry-bulb temperatures among F, C, and K."""

    units = {_key(from_unit), _key(to_unit)}
    if not units <= {"f", "c", "k"}:
        raise ValueError(
            "absolute temperature units must be F, C, or K; temperature "
            "difference units are not accepted"
        )
    number = float(value)
    if not isfinite(number):
        raise ValueError("value must be finite")
    source, target = _key(from_unit), _key(to_unit)
    celsius = (number - 32.0) * 5.0 / 9.0 if source == "f" else number
    if source == "k":
        celsius -= 273.15
    if target == "f":
        return celsius * 9.0 / 5.0 + 32.0
    if target == "k":
        return celsius + 273.15
    return celsius


def convert_temperature_delta(value: float, from_unit: str, to_unit: str) -> float:
    """Convert temperature differences without applying absolute offsets."""

    units = {_key(from_unit), _key(to_unit)}
    if not units <= {"deltaf", "deltac", "k"}:
        raise ValueError(
            "temperature difference units must be deltaF, deltaC, or K; "
            "absolute F/C units are not accepted"
        )
    number = float(value)
    if not isfinite(number):
        raise ValueError("value must be finite")
    source, target = _key(from_unit), _key(to_unit)
    kelvin = number * 5.0 / 9.0 if source == "deltaf" else number
    return kelvin * 9.0 / 5.0 if target == "deltaf" else kelvin
