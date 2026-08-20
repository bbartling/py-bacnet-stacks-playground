"""Trajectory-based W2A invalid-domain classification. Separate from ERR warning counts."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

RUNTIME_FRACTION_MIN = 0.01
ACTIVE_AIRFLOW_FRACTION = 0.25


def classify_coil_timestep(
    *,
    runtime_fraction: float,
    actual_air_kg_s: float,
    rated_air_kg_s: float,
    plr: float | None = None,
    heating_rate_w: float | None = None,
    cooling_rate_w: float | None = None,
    compressor_w: float | None = None,
    water_flow_fraction: float | None = None,
    coil: str | None = None,
    zone: str | None = None,
    hour: float | None = None,
) -> dict[str, Any]:
    rt = float(runtime_fraction)
    actual = float(actual_air_kg_s)
    rated = float(rated_air_kg_s)
    frac = (actual / rated) if rated > 0 else float("nan")
    invalid = bool(rt > RUNTIME_FRACTION_MIN and rated > 0 and frac < ACTIVE_AIRFLOW_FRACTION)
    if rt > RUNTIME_FRACTION_MIN and rated <= 0:
        invalid = True
    return {
        "coil": coil,
        "zone": zone,
        "hour": hour,
        "runtime_fraction": rt,
        "actual_air_kg_s": actual,
        "rated_air_kg_s": rated,
        "airflow_fraction": frac,
        "plr": plr,
        "heating_rate_w": heating_rate_w,
        "cooling_rate_w": cooling_rate_w,
        "compressor_w": compressor_w,
        "water_flow_fraction": water_flow_fraction,
        "invalid_domain": invalid,
        "warning_domain_flag": invalid,
    }


def count_active_invalid(rows: Sequence[Mapping[str, Any]]) -> int:
    return sum(1 for row in rows if bool(row.get("invalid_domain")))
