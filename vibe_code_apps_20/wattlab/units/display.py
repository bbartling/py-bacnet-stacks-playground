"""Consistent Imperial, Metric, source-unit, and dual-unit presentation."""

from __future__ import annotations

from enum import Enum

from .quantity import Quantity


class DisplayMode(str, Enum):
    IMPERIAL = "imperial"
    METRIC = "metric"
    SOURCE = "source"
    DUAL = "dual"


_DISPLAY_UNITS: dict[str, tuple[str, str]] = {
    "area": ("ft2", "m2"),
    "length": ("ft", "m"),
    "volumetric_flow": ("CFM", "m3/s"),
    "liquid_flow": ("GPM", "L/s"),
    "pressure": ("inWC", "Pa"),
    "pressure_kpa": ("psi", "kPa"),
    "power_kw": ("hp", "kW"),
    "power_w": ("Btu/h", "W"),
    "power_kw_mbh": ("MBH", "kW"),
    "cooling_capacity": ("ton", "kW_cooling"),
    "energy_intensity": ("kBtu/ft2", "kWh/m2"),
    "specific_energy": ("Btu/lb", "kJ/kg"),
    "specific_heat": ("Btu/lbF", "kJ/kgK"),
    "mass_flow": ("lb/h", "kg/s"),
    "degree_day": ("F-day", "K-day"),
    "area_cost": ("$/ft2", "$/m2"),
    "emissions_mass": ("lbCO2e", "kgCO2e"),
}


def _format(quantity: Quantity) -> str:
    value = f"{quantity.value:,.3f}".rstrip("0").rstrip(".")
    return f"{value} {quantity.unit}"


def display_quantity(quantity: Quantity, mode: DisplayMode | str) -> str:
    """Format a quantity under a public display policy."""

    selected = DisplayMode(mode)
    if selected is DisplayMode.SOURCE:
        return _format(quantity)
    try:
        imperial_unit, metric_unit = _DISPLAY_UNITS[quantity.dimension]
    except KeyError as exc:
        raise ValueError(
            f"No display-unit mapping for dimension {quantity.dimension!r}"
        ) from exc
    imperial = quantity.to(imperial_unit)
    metric = quantity.to(metric_unit)
    if selected is DisplayMode.IMPERIAL:
        return _format(imperial)
    if selected is DisplayMode.METRIC:
        return _format(metric)
    source_is_metric = quantity.unit.strip().lower() == metric_unit.lower()
    primary, secondary = (metric, imperial) if source_is_metric else (imperial, metric)
    return f"{_format(primary)} ({_format(secondary)})"
