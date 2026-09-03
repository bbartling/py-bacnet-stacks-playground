"""Thermostat conversions, schedules, and IDF schedule patching."""
from __future__ import annotations

import re
from typing import Any, Sequence

import numpy as np

from .constants import DEFAULT_COOL_F, DEFAULT_HEAT_F, INTERVALS_PER_DAY, MAX_COOL_F, MAX_HEAT_F


def f_to_c(temp_f: float) -> float:
    return (float(temp_f) - 32.0) * 5.0 / 9.0


def c_to_f(temp_c: float) -> float:
    return float(temp_c) * 9.0 / 5.0 + 32.0


def baseline_setpoints_f(n: int = INTERVALS_PER_DAY) -> tuple[np.ndarray, np.ndarray]:
    if n < 1:
        raise ValueError("n must be positive")
    heat = np.full(n, DEFAULT_HEAT_F, dtype=float)
    cool = np.full(n, DEFAULT_COOL_F, dtype=float)
    return heat, cool


def build_schedule_action(
    *,
    pre_start_hour: float = 12.0,
    event_start: float = 14.0,
    event_end: float = 18.0,
    recover_end: float = 21.0,
    pre_cool_f: float = 70.5,
    event_cool_f: float = MAX_COOL_F,
    recover_cool_f: float = DEFAULT_COOL_F,
    pre_heat_f: float = 72.5,
    event_heat_f: float = MAX_HEAT_F,
    recover_heat_f: float = DEFAULT_HEAT_F,
    mode: str = "summer_dr",
) -> dict[str, Any]:
    """Build a DR/grid schedule action dict (hours are decimal clock hours)."""

    return {
        "mode": mode,
        "pre_start_hour": float(pre_start_hour),
        "event_start": float(event_start),
        "event_end": float(event_end),
        "recover_end": float(recover_end),
        "pre_cool_f": float(pre_cool_f),
        "event_cool_f": float(event_cool_f),
        "recover_cool_f": float(recover_cool_f),
        "pre_heat_f": float(pre_heat_f),
        "event_heat_f": float(event_heat_f),
        "recover_heat_f": float(recover_heat_f),
    }


def action_to_setpoints_f(
    action: dict[str, Any],
    *,
    n: int = INTERVALS_PER_DAY,
) -> tuple[np.ndarray, np.ndarray]:
    heat, cool = baseline_setpoints_f(n)
    mode = str(action.get("mode") or "summer_dr")
    pre_s = float(action["pre_start_hour"])
    ev_s = float(action["event_start"])
    ev_e = float(action["event_end"])
    rec_e = float(action.get("recover_end", 24.0))
    for i in range(n):
        hour = (i + 1) * 24.0 / n
        if mode.startswith("winter"):
            if pre_s < hour <= ev_s:
                heat[i] = float(action["pre_heat_f"])
            elif ev_s < hour <= ev_e:
                heat[i] = float(action["event_heat_f"])
            elif ev_e < hour <= rec_e:
                heat[i] = float(action["recover_heat_f"])
        else:
            if pre_s < hour <= ev_s:
                cool[i] = float(action["pre_cool_f"])
            elif ev_s < hour <= ev_e:
                cool[i] = float(action["event_cool_f"])
            elif ev_e < hour <= rec_e:
                cool[i] = float(action["recover_cool_f"])
    heat, cool = enforce_heat_below_cool(heat, cool)
    return heat, cool


def enforce_heat_below_cool(
    heat_f: Sequence[float] | np.ndarray,
    cool_f: Sequence[float] | np.ndarray,
    *,
    min_gap_f: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Keep dual-setpoint heating strictly below cooling (EnergyPlus fatal otherwise)."""

    heat = np.asarray(heat_f, dtype=float).copy()
    cool = np.asarray(cool_f, dtype=float).copy()
    if heat.shape != cool.shape:
        raise ValueError("heat/cool shapes must match")
    for i in range(len(heat)):
        if heat[i] >= cool[i] - min_gap_f + 1e-9:
            # Prefer preserving the actively moved bound by sliding the other.
            if cool[i] <= DEFAULT_COOL_F:
                heat[i] = cool[i] - min_gap_f
            else:
                cool[i] = heat[i] + min_gap_f
    return heat, cool


def _until_label(index: int, n: int) -> str:
    total_minutes = int(round((index + 1) * 24 * 60 / n))
    total_minutes = min(total_minutes, 24 * 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02d}:{minutes:02d}"


def _compact_schedule(name: str, values_c: Sequence[float]) -> str:
    n = len(values_c)
    lines = [
        "  Schedule:Compact,",
        f"    {name},           !- Name",
        "    Temperature,             !- Schedule Type Limits Name",
        "    Through: 12/31,          !- Field 1",
        "    For: AllDays,            !- Field 2",
    ]
    for i, value in enumerate(values_c):
        until = _until_label(i, n)
        suffix = ";" if i == n - 1 else ","
        lines.append(f"    Until: {until},{float(value):.4f}{suffix}")
    return "\n".join(lines)


def apply_setpoint_schedules_to_idf(
    text: str,
    heat_f_series: Sequence[float],
    cool_f_series: Sequence[float],
) -> str:
    """Replace Schedule:Compact HEAT SETPOINT and COOL SETPOINT with 5-min series."""

    if len(heat_f_series) != len(cool_f_series):
        raise ValueError("heat and cool series must have the same length")
    if len(heat_f_series) < 1:
        raise ValueError("setpoint series must not be empty")
    heat_c = [f_to_c(v) for v in heat_f_series]
    cool_c = [f_to_c(v) for v in cool_f_series]
    heat_block = _compact_schedule("HEAT SETPOINT", heat_c)
    cool_block = _compact_schedule("COOL SETPOINT", cool_c)
    pattern = re.compile(
        r"(?ims)^\s*Schedule:Compact\s*,\s*\r?\n\s*HEAT SETPOINT\s*,.*?;",
    )
    text, n_heat = pattern.subn(heat_block, text, count=1)
    if n_heat != 1:
        raise ValueError("could not patch HEAT SETPOINT Schedule:Compact")
    pattern = re.compile(
        r"(?ims)^\s*Schedule:Compact\s*,\s*\r?\n\s*COOL SETPOINT\s*,.*?;",
    )
    text, n_cool = pattern.subn(cool_block, text, count=1)
    if n_cool != 1:
        raise ValueError("could not patch COOL SETPOINT Schedule:Compact")
    return text


def set_run_period(text: str, month: int, day: int, name: str = "RESIDENTIAL_BASE_DAY") -> str:
    if not 1 <= int(month) <= 12 or not 1 <= int(day) <= 31:
        raise ValueError("month/day out of range")
    block = f"""  RunPeriod,
    {name},    !- Name
    {int(month)},                       !- Begin Month
    {int(day)},                      !- Begin Day of Month
    ,                        !- Begin Year
    {int(month)},                       !- End Month
    {int(day)},                      !- End Day of Month
    ,                        !- End Year
    Tuesday,                 !- Day of Week for Start Day
    Yes,                     !- Use Weather File Holidays and Special Days
    Yes,                     !- Use Weather File Daylight Saving Period
    No,                      !- Apply Weekend Holiday Rule
    Yes,                     !- Use Weather File Rain Indicators
    Yes;                     !- Use Weather File Snow Indicators"""
    pattern = re.compile(r"(?ims)^\s*RunPeriod\s*,.*?;")
    text, n = pattern.subn(block, text, count=1)
    if n != 1:
        raise ValueError("could not patch RunPeriod")
    return text


def comfort_ok(
    temps_f: Sequence[float],
    low: float = MAX_HEAT_F,
    high: float = MAX_COOL_F,
) -> bool:
    if not temps_f:
        return False
    arr = np.asarray(temps_f, dtype=float)
    return bool(np.all(np.isfinite(arr)) and np.all(arr >= low) and np.all(arr <= high))
