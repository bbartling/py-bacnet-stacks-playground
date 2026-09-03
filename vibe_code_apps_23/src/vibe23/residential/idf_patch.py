"""Thin wrappers around thermostat IDF patch helpers."""
from __future__ import annotations

from typing import Sequence

from .thermostat import apply_setpoint_schedules_to_idf, set_run_period


def patch_setpoints(text: str, heat_f: Sequence[float], cool_f: Sequence[float]) -> str:
    return apply_setpoint_schedules_to_idf(text, heat_f, cool_f)


def patch_run_day(text: str, month: int, day: int, name: str = "RESIDENTIAL_BASE_DAY") -> str:
    return set_run_period(text, month, day, name)


def prepare_residential_idf(
    text: str,
    *,
    month: int,
    day: int,
    heat_f: Sequence[float],
    cool_f: Sequence[float],
    run_name: str = "RESIDENTIAL_BASE_DAY",
) -> str:
    patched = set_run_period(text, month, day, run_name)
    return apply_setpoint_schedules_to_idf(patched, heat_f, cool_f)
