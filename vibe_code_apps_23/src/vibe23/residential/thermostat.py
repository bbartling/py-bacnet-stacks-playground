"""Thermostat conversions, schedules, and IDF schedule patching."""
from __future__ import annotations

import re
from typing import Any, Sequence

import numpy as np

from .constants import (
    CENTER_F,
    CENTER_SEARCH_HALF_RANGE_F,
    CENTER_SEARCH_STEP_F,
    DEFAULT_COOL_F,
    DEFAULT_HEAT_F,
    HALF_DEADBAND_F,
    INTERVALS_PER_DAY,
    MAX_COOL_F,
    MAX_HEAT_F,
    SUMMER_DR_EVENT_END,
    SUMMER_DR_EVENT_START,
    SUMMER_DR_PRE_START_HOUR,
    SUMMER_DR_RECOVER_END,
    WINTER_DR_EVENT_END,
    WINTER_DR_EVENT_START,
    WINTER_DR_PRE_START_HOUR,
    WINTER_DR_RECOVER_END,
)


def f_to_c(temp_f: float) -> float:
    return (float(temp_f) - 32.0) * 5.0 / 9.0


def c_to_f(temp_c: float) -> float:
    return float(temp_c) * 9.0 / 5.0 + 32.0


def center_to_heat_cool(center_f: float) -> tuple[float, float]:
    """Map a dual-setpoint center to heat/cool with a fixed 2°F deadband."""
    c = float(center_f)
    return c - HALF_DEADBAND_F, c + HALF_DEADBAND_F


def center_search_values(
    *,
    center: float = CENTER_F,
    half_range: float = CENTER_SEARCH_HALF_RANGE_F,
    step: float = CENTER_SEARCH_STEP_F,
) -> tuple[float, ...]:
    """Return ±half_range around center in ``step`` increments (inclusive)."""
    lo = float(center) - float(half_range)
    hi = float(center) + float(half_range)
    n = int(round((hi - lo) / float(step))) + 1
    return tuple(round(lo + i * float(step), 4) for i in range(n))


def baseline_setpoints_f(n: int = INTERVALS_PER_DAY) -> tuple[np.ndarray, np.ndarray]:
    if n < 1:
        raise ValueError("n must be positive")
    heat = np.full(n, DEFAULT_HEAT_F, dtype=float)
    cool = np.full(n, DEFAULT_COOL_F, dtype=float)
    return heat, cool


def build_schedule_action(
    *,
    pre_start_hour: float | None = None,
    event_start: float | None = None,
    event_end: float | None = None,
    recover_end: float | None = None,
    pre_center_f: float = CENTER_F,
    event_center_f: float = CENTER_F,
    recover_center_f: float = CENTER_F,
    pre_cool_f: float | None = None,
    event_cool_f: float | None = None,
    recover_cool_f: float | None = None,
    pre_heat_f: float | None = None,
    event_heat_f: float | None = None,
    recover_heat_f: float | None = None,
    mode: str = "summer_dr",
) -> dict[str, Any]:
    """Build a DR/grid schedule action dict (hours are decimal clock hours).

    Prefer ``*_center_f`` (2°F deadband around the center). Legacy ``*_heat_f`` /
    ``*_cool_f`` keys are accepted and converted when both bounds are provided.
    """

    winter = str(mode).startswith("winter")
    if pre_start_hour is None:
        pre_start_hour = WINTER_DR_PRE_START_HOUR if winter else SUMMER_DR_PRE_START_HOUR
    if event_start is None:
        event_start = WINTER_DR_EVENT_START if winter else SUMMER_DR_EVENT_START
    if event_end is None:
        event_end = WINTER_DR_EVENT_END if winter else SUMMER_DR_EVENT_END
    if recover_end is None:
        recover_end = WINTER_DR_RECOVER_END if winter else SUMMER_DR_RECOVER_END

    def _pair(
        center: float,
        heat: float | None,
        cool: float | None,
    ) -> tuple[float, float, float]:
        if heat is not None and cool is not None:
            return (float(heat) + float(cool)) / 2.0, float(heat), float(cool)
        h, c = center_to_heat_cool(center)
        return float(center), h, c

    pre_c, pre_h, pre_cl = _pair(pre_center_f, pre_heat_f, pre_cool_f)
    ev_c, ev_h, ev_cl = _pair(event_center_f, event_heat_f, event_cool_f)
    rec_c, rec_h, rec_cl = _pair(recover_center_f, recover_heat_f, recover_cool_f)

    return {
        "mode": mode,
        "pre_start_hour": float(pre_start_hour),
        "event_start": float(event_start),
        "event_end": float(event_end),
        "recover_end": float(recover_end),
        "pre_center_f": float(pre_c),
        "event_center_f": float(ev_c),
        "recover_center_f": float(rec_c),
        "pre_cool_f": float(pre_cl),
        "event_cool_f": float(ev_cl),
        "recover_cool_f": float(rec_cl),
        "pre_heat_f": float(pre_h),
        "event_heat_f": float(ev_h),
        "recover_heat_f": float(rec_h),
    }


def action_to_setpoints_f(
    action: dict[str, Any],
    *,
    n: int = INTERVALS_PER_DAY,
) -> tuple[np.ndarray, np.ndarray]:
    heat, cool = baseline_setpoints_f(n)
    pre_s = float(action["pre_start_hour"])
    ev_s = float(action["event_start"])
    ev_e = float(action["event_end"])
    rec_e = float(action.get("recover_end", 24.0))

    def _bounds(prefix: str) -> tuple[float, float]:
        if f"{prefix}_center_f" in action:
            return center_to_heat_cool(float(action[f"{prefix}_center_f"]))
        return float(action[f"{prefix}_heat_f"]), float(action[f"{prefix}_cool_f"])

    pre_h, pre_c = _bounds("pre")
    ev_h, ev_c = _bounds("event")
    if "recover_center_f" in action or "recover_heat_f" in action or "recover_cool_f" in action:
        rec_h, rec_c = _bounds("recover")
    else:
        rec_h, rec_c = DEFAULT_HEAT_F, DEFAULT_COOL_F

    for i in range(n):
        hour = (i + 1) * 24.0 / n
        if pre_s < hour <= ev_s:
            heat[i], cool[i] = pre_h, pre_c
        elif ev_s < hour <= ev_e:
            heat[i], cool[i] = ev_h, ev_c
        elif ev_e < hour <= rec_e:
            heat[i], cool[i] = rec_h, rec_c
    heat, cool = enforce_heat_below_cool(heat, cool)
    return heat, cool


def enforce_heat_below_cool(
    heat_f: Sequence[float] | np.ndarray,
    cool_f: Sequence[float] | np.ndarray,
    *,
    min_gap_f: float = 2.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Keep dual-setpoint heating strictly below cooling (EnergyPlus fatal otherwise)."""

    heat = np.asarray(heat_f, dtype=float).copy()
    cool = np.asarray(cool_f, dtype=float).copy()
    if heat.shape != cool.shape:
        raise ValueError("heat/cool shapes must match")
    for i in range(len(heat)):
        if heat[i] >= cool[i] - min_gap_f + 1e-9:
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
