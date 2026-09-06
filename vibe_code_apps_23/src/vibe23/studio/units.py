"""Display-unit helpers for Studio (imperial vs metric). Internal traces stay °F / ft²."""
from __future__ import annotations

from typing import Literal

UnitSystem = Literal["imperial", "metric"]

FT2_PER_M2 = 10.76391041671


def normalize_units(value: str | None) -> UnitSystem:
    text = str(value or "imperial").strip().lower()
    return "metric" if text in {"metric", "si", "celsius", "m2"} else "imperial"


def f_to_c(temp_f: float) -> float:
    return (float(temp_f) - 32.0) * 5.0 / 9.0


def c_to_f(temp_c: float) -> float:
    return float(temp_c) * 9.0 / 5.0 + 32.0


def ft2_to_m2(ft2: float) -> float:
    return float(ft2) / FT2_PER_M2


def m2_to_ft2(m2: float) -> float:
    return float(m2) * FT2_PER_M2


def display_temp(temp_f: float, units: UnitSystem) -> float:
    return f_to_c(temp_f) if units == "metric" else float(temp_f)


def display_temp_series(temps_f: list[float], units: UnitSystem) -> list[float]:
    if units == "metric":
        return [f_to_c(v) for v in temps_f]
    return [float(v) for v in temps_f]


def display_area(ft2: float, units: UnitSystem) -> float:
    return ft2_to_m2(ft2) if units == "metric" else float(ft2)


def temp_unit(units: UnitSystem) -> str:
    return "°C" if units == "metric" else "°F"


def area_unit(units: UnitSystem) -> str:
    return "m²" if units == "metric" else "ft²"


def intensity_unit(units: UnitSystem) -> str:
    return "kWh/m²-day" if units == "metric" else "kWh/ft²-day"


def energy_intensity(kwh: float, *, floor_ft2: float, units: UnitSystem) -> float:
    if floor_ft2 <= 0:
        raise ValueError("floor_ft2 must be positive")
    if units == "metric":
        return float(kwh) / ft2_to_m2(floor_ft2)
    return float(kwh) / float(floor_ft2)


def comfort_wtp_label(units: UnitSystem) -> str:
    # Scoring stays $/°F·h internally; flex captions convert °C·h for display.
    _ = units
    return "ILLUSTRATIVE comfort WTP ($/°F·h vs baseline)"


__all__ = [
    "UnitSystem",
    "area_unit",
    "comfort_wtp_label",
    "c_to_f",
    "display_area",
    "display_temp",
    "display_temp_series",
    "energy_intensity",
    "f_to_c",
    "ft2_to_m2",
    "intensity_unit",
    "m2_to_ft2",
    "normalize_units",
    "temp_unit",
]
