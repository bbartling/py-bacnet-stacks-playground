"""Joule → kWh → kW Ideal-Loads + fixed-COP electrical proxy."""
from __future__ import annotations

from dataclasses import dataclass

from eplus_native import (
    DEFAULT_COOL_COP,
    DEFAULT_HEAT_COP,
    PROXY_FORMULA_VERSION,
)

J_PER_KWH = 3.6e6


@dataclass(frozen=True)
class ProxyMeta:
    heat_cop: float
    cool_cop: float
    interval_hours: float
    formula_version: str = PROXY_FORMULA_VERSION
    honesty: str = (
        "Ideal Loads + fixed-COP electrical proxy — not a detailed GSHP/GLHE plant."
    )


def site_electric_proxy_kwh(
    electricity_j: float,
    district_heating_j: float,
    district_cooling_j: float,
    *,
    heat_cop: float = DEFAULT_HEAT_COP,
    cool_cop: float = DEFAULT_COOL_COP,
) -> dict[str, float]:
    elec_kwh = float(electricity_j) / J_PER_KWH
    heat_kwh = float(district_heating_j) / (J_PER_KWH * max(heat_cop, 1e-6))
    cool_kwh = float(district_cooling_j) / (J_PER_KWH * max(cool_cop, 1e-6))
    site = elec_kwh + heat_kwh + cool_kwh
    return {
        "electricity_kwh": elec_kwh,
        "heating_electric_proxy_kwh": heat_kwh,
        "cooling_electric_proxy_kwh": cool_kwh,
        "site_electric_proxy_kwh": site,
    }


def site_electric_proxy_kw(
    electricity_j: float,
    district_heating_j: float,
    district_cooling_j: float,
    *,
    interval_hours: float,
    heat_cop: float = DEFAULT_HEAT_COP,
    cool_cop: float = DEFAULT_COOL_COP,
) -> dict[str, float]:
    if interval_hours <= 0:
        raise ValueError("interval_hours must be > 0")
    parts = site_electric_proxy_kwh(
        electricity_j,
        district_heating_j,
        district_cooling_j,
        heat_cop=heat_cop,
        cool_cop=cool_cop,
    )
    parts["interval_hours"] = float(interval_hours)
    parts["site_electric_proxy_kw"] = parts["site_electric_proxy_kwh"] / float(interval_hours)
    parts["heat_cop"] = float(heat_cop)
    parts["cool_cop"] = float(cool_cop)
    parts["proxy_formula_version"] = PROXY_FORMULA_VERSION
    return parts
