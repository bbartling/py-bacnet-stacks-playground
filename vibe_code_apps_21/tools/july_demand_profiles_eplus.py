#!/usr/bin/env python3
"""July hot-day electrical demand profiles for ECM_FULL_PARITY Demand tab.

Runs EnergyPlus single-day cases on the CURRENT G14 twin
(`geo_b100_dual_ahu_shape_ops11`):

  1) Weekday baseline (hottest July weekday in AMY)
  2) Weekend baseline (hottest July Saturday in AMY)
  3) Weekday load-shed: zone Clg SP +5°F and Dump DAT +5°F, 14:00–16:00
  4) Weekday deadband widen: occupied ~5°F DB → 10°F DB (Htg↓ / Clg↑), 14:00–16:00
  5) Weekday chiller plant OFF (CHW AvailabilityManager:Scheduled = 0), 14:00–16:00
  6) Weekday all HVAC OFF (FanAvail + CHW plant = 0), 14:00–16:00
  7) Weekday load SHIFT: precool morning (Clg/DAT −2°F 06–12) then relax DB after noon
     (Clg +5°F / Htg −2.5°F 12–18) — electrical demand moves earlier in the day
  8) Weekday precool + CHW OFF 14–16 (thermal-mass carry through peak)

Writes reports/full_parity_july_demand/july_demand_profiles.json
"""
from __future__ import annotations

import argparse
import calendar
import csv
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any, Literal


def _month_last_day(month: int, year: int = 2025) -> int:
    return calendar.monthrange(year, month)[1]


def _through_prev(month: int, day: int, year: int = 2025) -> str:
    """Day before event for Schedule:Compact Through: (never invalid dates)."""
    if day > 1:
        return f"{month}/{day - 1}"
    if month == 1:
        return f"1/1"
    prev_m = month - 1
    return f"{prev_m}/{_month_last_day(prev_m, year)}"


def _through_month_end(month: int, year: int = 2025) -> str:
    return f"{month}/{_month_last_day(month, year)}"

ROOT = Path("/data") if Path("/data/runs").is_dir() else Path.home() / "wattlab_workspace"
TWIN_ID = "geo_b100_dual_ahu_shape_ops11"
TWIN = ROOT / "runs" / TWIN_ID
IDF = TWIN / "model.idf"
EPW = ROOT / "runs" / f"{TWIN_ID}__stage_in" / "amy.epw"
OUT = ROOT / "reports" / "full_parity_july_demand"

Mode = Literal[
    "baseline",
    "setpoint_raise",
    "deadband_widen",
    "chiller_off",
    "hvac_off",
    "precool_shift",
    "precool_chiller_off",
]

_RUNPERIOD_RE = re.compile(r"RunPeriod,\s*\n\s*Annual,.*?;", re.IGNORECASE | re.DOTALL)
_CLG_RE = re.compile(
    r"Schedule:Compact,\s*\n\s*Clg-SetP-Sch, Temperature,\s*\n.*?;\s*\n",
    re.IGNORECASE | re.DOTALL,
)
_HTG_RE = re.compile(
    r"Schedule:Compact,\s*\n\s*Htg-SetP-Sch, Temperature,\s*\n.*?;\s*\n",
    re.IGNORECASE | re.DOTALL,
)
_FAN_RE = re.compile(
    r"Schedule:Compact,\s*\n\s*FanAvailSched,.*?;\s*\n",
    re.IGNORECASE | re.DOTALL,
)
_CHW_AM_LIST_RE = re.compile(
    r"AvailabilityManagerAssignmentList,\s*\n\s*Chilled Water Loop Availability List,.*?;",
    re.IGNORECASE | re.DOTALL,
)
_DUMP_RE = {
    "Dump_AHU1_DAT_SP": re.compile(
        r"Schedule:Compact,\s*\n\s*Dump_AHU1_DAT_SP,.*?;\s*\n",
        re.IGNORECASE | re.DOTALL,
    ),
    "Dump_AHU2_DAT_SP": re.compile(
        r"Schedule:Compact,\s*\n\s*Dump_AHU2_DAT_SP,.*?;\s*\n",
        re.IGNORECASE | re.DOTALL,
    ),
}

CASE_SPECS: list[tuple[str, str, Mode, dict[str, Any]]] = [
    ("weekday_baseline", "weekday", "baseline", {}),
    ("weekend_baseline", "weekend", "baseline", {}),
    ("weekday_loadshed_p5f", "weekday", "setpoint_raise", {"delta_f": 5.0}),
    ("weekday_deadband_10f", "weekday", "deadband_widen", {"target_db_f": 10.0}),
    ("weekday_chiller_off", "weekday", "chiller_off", {}),
    ("weekday_hvac_off", "weekday", "hvac_off", {}),
    (
        "weekday_precool_shift",
        "weekday",
        "precool_shift",
        {
            "precool_f": 2.0,
            "relax_clg_f": 5.0,
            "relax_htg_f": 2.5,
            "precool_start_h": 6,
            "precool_end_h": 12,
            "relax_end_h": 18,
        },
    ),
    (
        "weekday_precool_chiller_off",
        "weekday",
        "precool_chiller_off",
        {
            "precool_f": 2.0,
            "precool_start_h": 6,
            "precool_end_h": 12,
            "start_h": 14,
            "end_h": 16,
        },
    ),
]


def _delta_c(delta_f: float) -> float:
    return delta_f * (5.0 / 9.0)


def _pick_hot_july_days(epw: Path) -> dict[str, Any]:
    """Pick hottest July weekday + Saturday from AMY EPW dry-bulb."""
    from collections import defaultdict

    day_max: dict[tuple[int, int, int], float] = defaultdict(lambda: -999.0)
    for line in epw.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split(",")
        if len(parts) < 7 or not parts[1].strip().isdigit():
            continue
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            db = float(parts[6])
        except ValueError:
            continue
        if m != 7:
            continue
        key = (y, m, d)
        if db > day_max[key]:
            day_max[key] = db

    weekday = None
    weekend = None
    ranked = sorted(((tmax, ymd) for ymd, tmax in day_max.items()), reverse=True)
    for tmax, (y, m, d) in ranked:
        dow = date(y, m, d).strftime("%A")
        if weekday is None and dow not in ("Saturday", "Sunday"):
            weekday = {"year": y, "month": m, "day": d, "dow": dow, "max_db_c": round(tmax, 2)}
        if weekend is None and dow == "Saturday":
            weekend = {"year": y, "month": m, "day": d, "dow": dow, "max_db_c": round(tmax, 2)}
        if weekday and weekend:
            break
    if not weekday or not weekend:
        raise RuntimeError(f"Could not pick July weekday/weekend from {epw}")
    return {"weekday": weekday, "weekend": weekend}


def _patch_runperiod(text: str, *, month: int, day: int, year: int, dow: str) -> str:
    block = (
        f"RunPeriod,\n"
        f"    DR_JulyPeak,             !- Name\n"
        f"    {month},                       !- Begin Month\n"
        f"    {day},                      !- Begin Day of Month\n"
        f"    {year},                    !- Begin Year\n"
        f"    {month},                      !- End Month\n"
        f"    {day},                      !- End Day of Month\n"
        f"    {year},                    !- End Year\n"
        f"    {dow},                !- Day of Week for Start Day\n"
        f"    Yes, Yes, No, Yes, Yes;"
    )
    if not _RUNPERIOD_RE.search(text):
        raise RuntimeError("RunPeriod Annual block not found")
    return _RUNPERIOD_RE.sub(block, text, count=1)


def _ensure_hourly_meters(text: str) -> str:
    if "Output:Meter,Electricity:Facility,Hourly" in text:
        return text
    if "Output:Meter,Electricity:Facility,Monthly;" not in text:
        text += "\n  Output:Meter,Electricity:Facility,Hourly;\n"
        text += "  Output:Meter,Cooling:Electricity,Hourly;\n"
        return text
    return text.replace(
        "Output:Meter,Electricity:Facility,Monthly;",
        "Output:Meter,Electricity:Facility,Hourly;\n"
        "  Output:Meter,Electricity:Facility,Monthly;\n"
        "  Output:Meter,Cooling:Electricity,Hourly;",
        1,
    )


def _clg_loadshed_block(
    *,
    month: int,
    day: int,
    start_h: int,
    end_h: int,
    occupied_c: float,
    shed_c: float,
) -> str:
    prev = _through_prev(month, day)
    return (
        f"Schedule:Compact,\n"
        f"    Clg-SetP-Sch, Temperature,\n"
        f"    Through: {_through_prev(month, day)},\n"
        f"    For: Weekdays SummerDesignDay,\n"
        f"    Until: 6:00, 30.0, Until: 22:00, {occupied_c}, Until: 24:00, 30.0,\n"
        f"    For: Saturday,\n"
        f"    Until: 6:00, 30.0, Until: 18:00, {occupied_c}, Until: 24:00, 30.0,\n"
        f"    For: AllOtherDays, Until: 24:00, 30.0,\n"
        f"    Through: {month}/{day},\n"
        f"    For: Weekdays SummerDesignDay,\n"
        f"    Until: 6:00, 30.0,\n"
        f"    Until: {start_h}:00, {occupied_c},\n"
        f"    Until: {end_h}:00, {shed_c},\n"
        f"    Until: 22:00, {occupied_c},\n"
        f"    Until: 24:00, 30.0,\n"
        f"    For: Saturday,\n"
        f"    Until: 6:00, 30.0, Until: 18:00, {occupied_c}, Until: 24:00, 30.0,\n"
        f"    For: AllOtherDays, Until: 24:00, 30.0,\n"
        f"    Through: 12/31,\n"
        f"    For: Weekdays SummerDesignDay,\n"
        f"    Until: 6:00, 30.0, Until: 22:00, {occupied_c}, Until: 24:00, 30.0,\n"
        f"    For: Saturday,\n"
        f"    Until: 6:00, 30.0, Until: 18:00, {occupied_c}, Until: 24:00, 30.0,\n"
        f"    For: AllOtherDays, Until: 24:00, 30.0;\n"
    )


def _htg_loadshed_block(
    *,
    month: int,
    day: int,
    start_h: int,
    end_h: int,
    occupied_c: float,
    shed_c: float,
    setback_c: float = 15.6,
) -> str:
    prev = _through_prev(month, day)
    return (
        f"Schedule:Compact,\n"
        f"    Htg-SetP-Sch, Temperature,\n"
        f"    Through: {prev},\n"
        f"    For: Weekdays SummerDesignDay,\n"
        f"    Until: 6:00, {setback_c}, Until: 22:00, {occupied_c}, Until: 24:00, {setback_c},\n"
        f"    For: Saturday,\n"
        f"    Until: 6:00, {setback_c}, Until: 18:00, {occupied_c}, Until: 24:00, {setback_c},\n"
        f"    For: AllOtherDays, Until: 24:00, {setback_c},\n"
        f"    Through: {month}/{day},\n"
        f"    For: Weekdays SummerDesignDay,\n"
        f"    Until: 6:00, {setback_c},\n"
        f"    Until: {start_h}:00, {occupied_c},\n"
        f"    Until: {end_h}:00, {shed_c},\n"
        f"    Until: 22:00, {occupied_c},\n"
        f"    Until: 24:00, {setback_c},\n"
        f"    For: Saturday,\n"
        f"    Until: 6:00, {setback_c}, Until: 18:00, {occupied_c}, Until: 24:00, {setback_c},\n"
        f"    For: AllOtherDays, Until: 24:00, {setback_c},\n"
        f"    Through: 12/31,\n"
        f"    For: Weekdays SummerDesignDay,\n"
        f"    Until: 6:00, {setback_c}, Until: 22:00, {occupied_c}, Until: 24:00, {setback_c},\n"
        f"    For: Saturday,\n"
        f"    Until: 6:00, {setback_c}, Until: 18:00, {occupied_c}, Until: 24:00, {setback_c},\n"
        f"    For: AllOtherDays, Until: 24:00, {setback_c};\n"
    )


def _dump_july_loadshed(
    name: str,
    *,
    month: int,
    day: int,
    start_h: int,
    end_h: int,
    july_c: float,
    shed_c: float,
) -> str:
    """Rewrite Dump_* DAT so only event-day 14–16 raises SAT."""
    prev = _through_prev(month, day)
    months = {
        "Dump_AHU1_DAT_SP": [
            (1, 31, 27.78),
            (2, 28, 1.11),
            (3, 31, 10.5),
            (4, 30, 10.5),
            (5, 31, 11.0),
            (6, 30, 9.5),
            (8, 31, 11.67),
            (9, 30, 11.11),
            (10, 31, 15.5),
            (11, 30, 26.67),
            (12, 31, 27.78),
        ],
        "Dump_AHU2_DAT_SP": [
            (1, 31, 27.78),
            (2, 28, 1.0),
            (3, 31, 6.8),
            (4, 30, 6.8),
            (5, 31, 7.2),
            (6, 30, 5.8),
            (8, 31, 7.78),
            (9, 30, 7.22),
            (10, 31, 11.5),
            (11, 30, 26.67),
            (12, 31, 27.78),
        ],
    }
    lines = [
        "Schedule:Compact,",
        f"  {name},",
        "  Temperature,",
    ]
    for mm, dd, val in months[name]:
        if mm < month:
            lines += [f"  Through: {mm}/{dd},", "  For: AllDays,", "  Until: 24:00,", f"  {val},"]
    lines += [
        f"  Through: {prev},",
        "  For: AllDays,",
        "  Until: 24:00,",
        f"  {july_c},",
        f"  Through: {month}/{day},",
        "  For: AllDays,",
        f"  Until: {start_h}:00,",
        f"  {july_c},",
        f"  Until: {end_h}:00,",
        f"  {shed_c},",
        "  Until: 24:00,",
        f"  {july_c},",
        f"  Through: {_through_month_end(month)},",
        "  For: AllDays,",
        "  Until: 24:00,",
        f"  {july_c},",
    ]
    for mm, dd, val in months[name]:
        if mm > month:
            lines += [f"  Through: {mm}/{dd},", "  For: AllDays,", "  Until: 24:00,", f"  {val},"]
    lines[-1] = lines[-1].rstrip(",") + ";"
    return "\n".join(lines) + "\n"


def _fan_avail_with_window_off(
    *,
    start_h: int,
    end_h: int,
    on_start: int = 9,
    on_end: int = 23,
) -> str:
    """Single-day RunPeriod FanAvail: on during occupied, forced off in DR window."""
    return (
        "Schedule:Compact,\n"
        "  FanAvailSched, On/Off,\n"
        "  Through: 12/31,\n"
        "  For: AllDays,\n"
        f"  Until: {on_start}:00, 0.0,\n"
        f"  Until: {start_h}:00, 1.0,\n"
        f"  Until: {end_h}:00, 0.0,\n"
        f"  Until: {on_end}:00, 1.0,\n"
        "  Until: 24:00, 0.0;\n"
    )


def _inject_chw_plant_off(text: str, *, start_h: int, end_h: int) -> str:
    """Force CHW loop AvailabilityManager:Scheduled = 0 during DR window."""
    sched = (
        "Schedule:Compact,\n"
        "  CHW_DR_Avail, On/Off,\n"
        "  Through: 12/31,\n"
        "  For: AllDays,\n"
        f"  Until: {start_h}:00, 1.0,\n"
        f"  Until: {end_h}:00, 0.0,\n"
        "  Until: 24:00, 1.0;\n"
        "\n"
        "AvailabilityManager:Scheduled,\n"
        "  CHW_DR_Scheduled Off,\n"
        "  CHW_DR_Avail;\n"
        "\n"
    )
    new_list = (
        "AvailabilityManagerAssignmentList,\n"
        "  Chilled Water Loop Availability List,                    !- Name\n"
        "  AvailabilityManager:Scheduled,                          !- Availability Manager Object Type\n"
        "  CHW_DR_Scheduled Off;                                   !- Availability Manager Name"
    )
    if not _CHW_AM_LIST_RE.search(text):
        raise RuntimeError("Chilled Water Loop Availability List not found")
    text = _CHW_AM_LIST_RE.sub(new_list, text, count=1)
    # Insert schedule + manager just before the assignment list we replaced
    anchor = "AvailabilityManagerAssignmentList,\n  Chilled Water Loop Availability List,"
    if anchor not in text:
        text = text + "\n" + sched
    else:
        text = text.replace(anchor, sched + anchor, 1)
    return text


def _apply_setpoint_raise(
    text: str,
    *,
    month: int,
    day: int,
    start_h: int,
    end_h: int,
    delta_f: float,
    occupied_clg_c: float,
    july_dat: dict[str, float],
) -> str:
    shed_c = round(occupied_clg_c + _delta_c(delta_f), 4)
    clg = _clg_loadshed_block(
        month=month,
        day=day,
        start_h=start_h,
        end_h=end_h,
        occupied_c=occupied_clg_c,
        shed_c=shed_c,
    )
    if not _CLG_RE.search(text):
        raise RuntimeError("Clg-SetP-Sch not found")
    text = _CLG_RE.sub(clg, text, count=1)
    for name, july_c in july_dat.items():
        shed_dat = round(july_c + _delta_c(delta_f), 4)
        block = _dump_july_loadshed(
            name,
            month=month,
            day=day,
            start_h=start_h,
            end_h=end_h,
            july_c=july_c,
            shed_c=shed_dat,
        )
        if not _DUMP_RE[name].search(text):
            raise RuntimeError(f"{name} not found")
        text = _DUMP_RE[name].sub(block, text, count=1)
    return text


def _apply_deadband_widen(
    text: str,
    *,
    month: int,
    day: int,
    start_h: int,
    end_h: int,
    target_db_f: float,
    occupied_htg_c: float,
    occupied_clg_c: float,
    july_dat: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Widen zone deadband to target_db_f during DR window (cooling-biased).

    Summer DR: hold Htg, raise Clg so (Clg − Htg) = target_db_f, and raise Dump
    DAT by the same Δ so the air-side follows (zone-only Clg was DAT-limited on
    this Twin and produced ~0 ΔkW).
    """
    july_dat = july_dat or {"Dump_AHU1_DAT_SP": 11.44, "Dump_AHU2_DAT_SP": 7.55}
    shed_htg = occupied_htg_c
    shed_clg = round(occupied_htg_c + _delta_c(target_db_f), 4)
    clg_delta_f = round((shed_clg - occupied_clg_c) * 9.0 / 5.0, 4)
    clg = _clg_loadshed_block(
        month=month,
        day=day,
        start_h=start_h,
        end_h=end_h,
        occupied_c=occupied_clg_c,
        shed_c=shed_clg,
    )
    htg = _htg_loadshed_block(
        month=month,
        day=day,
        start_h=start_h,
        end_h=end_h,
        occupied_c=occupied_htg_c,
        shed_c=shed_htg,
    )
    if not _CLG_RE.search(text):
        raise RuntimeError("Clg-SetP-Sch not found")
    if not _HTG_RE.search(text):
        raise RuntimeError("Htg-SetP-Sch not found")
    text = _CLG_RE.sub(clg, text, count=1)
    text = _HTG_RE.sub(htg, text, count=1)
    for name, july_c in july_dat.items():
        shed_dat = round(july_c + _delta_c(clg_delta_f), 4)
        block = _dump_july_loadshed(
            name,
            month=month,
            day=day,
            start_h=start_h,
            end_h=end_h,
            july_c=july_c,
            shed_c=shed_dat,
        )
        if not _DUMP_RE[name].search(text):
            raise RuntimeError(f"{name} not found")
        text = _DUMP_RE[name].sub(block, text, count=1)
    return {
        "text": text,
        "shed_clg_c": shed_clg,
        "clg_delta_f": clg_delta_f,
        "dat_delta_f": clg_delta_f,
    }


def _clg_precool_shift_block(
    *,
    month: int,
    day: int,
    occupied_c: float,
    precool_c: float,
    relax_c: float,
    precool_start_h: int,
    precool_end_h: int,
    relax_end_h: int,
) -> str:
    """Event-day Clg: setback → precool → afternoon relax → occupied → setback."""
    prev = _through_prev(month, day)
    return (
        f"Schedule:Compact,\n"
        f"    Clg-SetP-Sch, Temperature,\n"
        f"    Through: {_through_prev(month, day)},\n"
        f"    For: Weekdays SummerDesignDay,\n"
        f"    Until: 6:00, 30.0, Until: 22:00, {occupied_c}, Until: 24:00, 30.0,\n"
        f"    For: Saturday,\n"
        f"    Until: 6:00, 30.0, Until: 18:00, {occupied_c}, Until: 24:00, 30.0,\n"
        f"    For: AllOtherDays, Until: 24:00, 30.0,\n"
        f"    Through: {month}/{day},\n"
        f"    For: Weekdays SummerDesignDay,\n"
        f"    Until: {precool_start_h}:00, 30.0,\n"
        f"    Until: {precool_end_h}:00, {precool_c},\n"
        f"    Until: {relax_end_h}:00, {relax_c},\n"
        f"    Until: 22:00, {occupied_c},\n"
        f"    Until: 24:00, 30.0,\n"
        f"    For: Saturday,\n"
        f"    Until: 6:00, 30.0, Until: 18:00, {occupied_c}, Until: 24:00, 30.0,\n"
        f"    For: AllOtherDays, Until: 24:00, 30.0,\n"
        f"    Through: 12/31,\n"
        f"    For: Weekdays SummerDesignDay,\n"
        f"    Until: 6:00, 30.0, Until: 22:00, {occupied_c}, Until: 24:00, 30.0,\n"
        f"    For: Saturday,\n"
        f"    Until: 6:00, 30.0, Until: 18:00, {occupied_c}, Until: 24:00, 30.0,\n"
        f"    For: AllOtherDays, Until: 24:00, 30.0;\n"
    )


def _htg_precool_shift_block(
    *,
    month: int,
    day: int,
    occupied_c: float,
    relax_c: float,
    precool_end_h: int,
    relax_end_h: int,
    setback_c: float = 15.6,
) -> str:
    """Afternoon Htg drop widens deadband after noon (precool morning keeps occupied Htg)."""
    prev = _through_prev(month, day)
    return (
        f"Schedule:Compact,\n"
        f"    Htg-SetP-Sch, Temperature,\n"
        f"    Through: {prev},\n"
        f"    For: Weekdays SummerDesignDay,\n"
        f"    Until: 6:00, {setback_c}, Until: 22:00, {occupied_c}, Until: 24:00, {setback_c},\n"
        f"    For: Saturday,\n"
        f"    Until: 6:00, {setback_c}, Until: 18:00, {occupied_c}, Until: 24:00, {setback_c},\n"
        f"    For: AllOtherDays, Until: 24:00, {setback_c},\n"
        f"    Through: {month}/{day},\n"
        f"    For: Weekdays SummerDesignDay,\n"
        f"    Until: 6:00, {setback_c},\n"
        f"    Until: {precool_end_h}:00, {occupied_c},\n"
        f"    Until: {relax_end_h}:00, {relax_c},\n"
        f"    Until: 22:00, {occupied_c},\n"
        f"    Until: 24:00, {setback_c},\n"
        f"    For: Saturday,\n"
        f"    Until: 6:00, {setback_c}, Until: 18:00, {occupied_c}, Until: 24:00, {setback_c},\n"
        f"    For: AllOtherDays, Until: 24:00, {setback_c},\n"
        f"    Through: 12/31,\n"
        f"    For: Weekdays SummerDesignDay,\n"
        f"    Until: 6:00, {setback_c}, Until: 22:00, {occupied_c}, Until: 24:00, {setback_c},\n"
        f"    For: Saturday,\n"
        f"    Until: 6:00, {setback_c}, Until: 18:00, {occupied_c}, Until: 24:00, {setback_c},\n"
        f"    For: AllOtherDays, Until: 24:00, {setback_c};\n"
    )


def _dump_precool_shift(
    name: str,
    *,
    month: int,
    day: int,
    july_c: float,
    precool_c: float,
    relax_c: float,
    precool_end_h: int,
    relax_end_h: int,
) -> str:
    """Dump DAT cooler in morning, warmer after noon on event day."""
    prev = _through_prev(month, day)
    months = {
        "Dump_AHU1_DAT_SP": [
            (1, 31, 27.78),
            (2, 28, 1.11),
            (3, 31, 10.5),
            (4, 30, 10.5),
            (5, 31, 11.0),
            (6, 30, 9.5),
            (8, 31, 11.67),
            (9, 30, 11.11),
            (10, 31, 15.5),
            (11, 30, 26.67),
            (12, 31, 27.78),
        ],
        "Dump_AHU2_DAT_SP": [
            (1, 31, 27.78),
            (2, 28, 1.0),
            (3, 31, 6.8),
            (4, 30, 6.8),
            (5, 31, 7.2),
            (6, 30, 5.8),
            (8, 31, 7.78),
            (9, 30, 7.22),
            (10, 31, 11.5),
            (11, 30, 26.67),
            (12, 31, 27.78),
        ],
    }
    lines = ["Schedule:Compact,", f"  {name},", "  Temperature,"]
    for mm, dd, val in months[name]:
        if mm < month:
            lines += [f"  Through: {mm}/{dd},", "  For: AllDays,", "  Until: 24:00,", f"  {val},"]
    lines += [
        f"  Through: {prev},",
        "  For: AllDays,",
        "  Until: 24:00,",
        f"  {july_c},",
        f"  Through: {month}/{day},",
        "  For: AllDays,",
        f"  Until: {precool_end_h}:00,",
        f"  {precool_c},",
        f"  Until: {relax_end_h}:00,",
        f"  {relax_c},",
        "  Until: 24:00,",
        f"  {july_c},",
        f"  Through: {_through_month_end(month)},",
        "  For: AllDays,",
        "  Until: 24:00,",
        f"  {july_c},",
    ]
    for mm, dd, val in months[name]:
        if mm > month:
            lines += [f"  Through: {mm}/{dd},", "  For: AllDays,", "  Until: 24:00,", f"  {val},"]
    lines[-1] = lines[-1].rstrip(",") + ";"
    return "\n".join(lines) + "\n"


def _apply_precool_shift(
    text: str,
    *,
    month: int,
    day: int,
    occupied_clg_c: float,
    occupied_htg_c: float,
    july_dat: dict[str, float],
    precool_f: float = 2.0,
    relax_clg_f: float = 5.0,
    relax_htg_f: float = 2.5,
    precool_start_h: int = 6,
    precool_end_h: int = 12,
    relax_end_h: int = 18,
) -> dict[str, Any]:
    precool_clg = round(occupied_clg_c - _delta_c(precool_f), 4)
    relax_clg = round(occupied_clg_c + _delta_c(relax_clg_f), 4)
    relax_htg = round(occupied_htg_c - _delta_c(relax_htg_f), 4)
    clg = _clg_precool_shift_block(
        month=month,
        day=day,
        occupied_c=occupied_clg_c,
        precool_c=precool_clg,
        relax_c=relax_clg,
        precool_start_h=precool_start_h,
        precool_end_h=precool_end_h,
        relax_end_h=relax_end_h,
    )
    htg = _htg_precool_shift_block(
        month=month,
        day=day,
        occupied_c=occupied_htg_c,
        relax_c=relax_htg,
        precool_end_h=precool_end_h,
        relax_end_h=relax_end_h,
    )
    if not _CLG_RE.search(text):
        raise RuntimeError("Clg-SetP-Sch not found")
    if not _HTG_RE.search(text):
        raise RuntimeError("Htg-SetP-Sch not found")
    text_out = _CLG_RE.sub(clg, text, count=1)
    text_out = _HTG_RE.sub(htg, text_out, count=1)
    for name, july_c in july_dat.items():
        block = _dump_precool_shift(
            name,
            month=month,
            day=day,
            july_c=july_c,
            precool_c=round(july_c - _delta_c(precool_f), 4),
            relax_c=round(july_c + _delta_c(relax_clg_f), 4),
            precool_end_h=precool_end_h,
            relax_end_h=relax_end_h,
        )
        if not _DUMP_RE[name].search(text_out):
            raise RuntimeError(f"{name} not found")
        text_out = _DUMP_RE[name].sub(block, text_out, count=1)
    meta = {
        "precool_f": precool_f,
        "relax_clg_f": relax_clg_f,
        "relax_htg_f": relax_htg_f,
        "precool_window": f"{precool_start_h}:00–{precool_end_h}:00",
        "relax_window": f"{precool_end_h}:00–{relax_end_h}:00",
        "precool_clg_c": precool_clg,
        "relax_clg_c": relax_clg,
        "relax_htg_c": relax_htg,
        "text": text_out,
    }
    return meta


def _apply_precool_only(
    text: str,
    *,
    month: int,
    day: int,
    occupied_clg_c: float,
    july_dat: dict[str, float],
    precool_f: float = 2.0,
    precool_start_h: int = 6,
    precool_end_h: int = 12,
) -> str:
    """Morning precool only (used with plant-off peak). Afternoon returns to occupied Clg."""
    precool_clg = round(occupied_clg_c - _delta_c(precool_f), 4)
    clg = _clg_precool_shift_block(
        month=month,
        day=day,
        occupied_c=occupied_clg_c,
        precool_c=precool_clg,
        relax_c=occupied_clg_c,
        precool_start_h=precool_start_h,
        precool_end_h=precool_end_h,
        relax_end_h=22,
    )
    if not _CLG_RE.search(text):
        raise RuntimeError("Clg-SetP-Sch not found")
    text = _CLG_RE.sub(clg, text, count=1)
    for name, july_c in july_dat.items():
        block = _dump_precool_shift(
            name,
            month=month,
            day=day,
            july_c=july_c,
            precool_c=round(july_c - _delta_c(precool_f), 4),
            relax_c=july_c,
            precool_end_h=precool_end_h,
            relax_end_h=22,
        )
        if not _DUMP_RE[name].search(text):
            raise RuntimeError(f"{name} not found")
        text = _DUMP_RE[name].sub(block, text, count=1)
    return text


def patch_idf(
    src: Path,
    dst: Path,
    *,
    month: int,
    day: int,
    year: int,
    dow: str,
    mode: Mode = "baseline",
    delta_f: float = 5.0,
    target_db_f: float = 10.0,
    start_h: int = 14,
    end_h: int = 16,
    occupied_clg_c: float = 24.0,
    occupied_htg_c: float = 21.0,
    july_dat: dict[str, float] | None = None,
    precool_f: float = 2.0,
    relax_clg_f: float = 5.0,
    relax_htg_f: float = 2.5,
    precool_start_h: int = 6,
    precool_end_h: int = 12,
    relax_end_h: int = 18,
) -> dict[str, Any]:
    text = src.read_text(encoding="utf-8", errors="replace")
    text = _patch_runperiod(text, month=month, day=day, year=year, dow=dow)
    text = _ensure_hourly_meters(text)
    july_dat = july_dat or {"Dump_AHU1_DAT_SP": 11.44, "Dump_AHU2_DAT_SP": 7.55}
    story: dict[str, Any] = {"mode": mode, "window": f"{start_h}:00–{end_h}:00"}

    if mode == "setpoint_raise":
        text = _apply_setpoint_raise(
            text,
            month=month,
            day=day,
            start_h=start_h,
            end_h=end_h,
            delta_f=delta_f,
            occupied_clg_c=occupied_clg_c,
            july_dat=july_dat,
        )
        story["delta_f"] = delta_f
        story["algorithm"] = (
            f"Clg-SetP-Sch +{delta_f:g}°F and Dump_AHU*_DAT_SP +{delta_f:g}°F during "
            f"{start_h}:00–{end_h}:00"
        )
    elif mode == "deadband_widen":
        current_db_f = round((occupied_clg_c - occupied_htg_c) * 9.0 / 5.0, 2)
        meta = _apply_deadband_widen(
            text,
            month=month,
            day=day,
            start_h=start_h,
            end_h=end_h,
            target_db_f=target_db_f,
            occupied_htg_c=occupied_htg_c,
            occupied_clg_c=occupied_clg_c,
            july_dat=july_dat,
        )
        text = meta["text"]
        story["target_db_f"] = target_db_f
        story["occupied_db_f"] = current_db_f
        story["htg_delta_f"] = 0.0
        story["clg_delta_f"] = meta["clg_delta_f"]
        story["dat_delta_f"] = meta["dat_delta_f"]
        story["algorithm"] = (
            f"Zone deadband {current_db_f:g}°F → {target_db_f:g}°F cooling-biased "
            f"(Htg held {occupied_htg_c}°C, Clg → {meta['shed_clg_c']}°C / "
            f"+{meta['clg_delta_f']:g}°F + Dump DAT +{meta['dat_delta_f']:g}°F) "
            f"during {start_h}:00–{end_h}:00"
        )
    elif mode == "chiller_off":
        text = _inject_chw_plant_off(text, start_h=start_h, end_h=end_h)
        story["algorithm"] = (
            f"Chilled Water Loop AvailabilityManager:Scheduled OFF during "
            f"{start_h}:00–{end_h}:00 (AHUs remain available)"
        )
    elif mode == "hvac_off":
        fan = _fan_avail_with_window_off(start_h=start_h, end_h=end_h)
        if not _FAN_RE.search(text):
            raise RuntimeError("FanAvailSched not found")
        text = _FAN_RE.sub(fan, text, count=1)
        text = _inject_chw_plant_off(text, start_h=start_h, end_h=end_h)
        story["algorithm"] = (
            f"FanAvailSched=0 and CHW plant Scheduled OFF during "
            f"{start_h}:00–{end_h}:00 (all HVAC shed)"
        )
    elif mode == "precool_shift":
        meta = _apply_precool_shift(
            text,
            month=month,
            day=day,
            occupied_clg_c=occupied_clg_c,
            occupied_htg_c=occupied_htg_c,
            july_dat=july_dat,
            precool_f=precool_f,
            relax_clg_f=relax_clg_f,
            relax_htg_f=relax_htg_f,
            precool_start_h=precool_start_h,
            precool_end_h=precool_end_h,
            relax_end_h=relax_end_h,
        )
        text = meta.pop("text")
        story.update(meta)
        story["window"] = meta["relax_window"]
        story["algorithm"] = (
            f"Load SHIFT: precool Clg/DAT −{precool_f:g}°F "
            f"{precool_start_h}:00–{precool_end_h}:00; then relax "
            f"Clg +{relax_clg_f:g}°F / Htg −{relax_htg_f:g}°F "
            f"{precool_end_h}:00–{relax_end_h}:00"
        )
    elif mode == "precool_chiller_off":
        text = _apply_precool_only(
            text,
            month=month,
            day=day,
            occupied_clg_c=occupied_clg_c,
            july_dat=july_dat,
            precool_f=precool_f,
            precool_start_h=precool_start_h,
            precool_end_h=precool_end_h,
        )
        text = _inject_chw_plant_off(text, start_h=start_h, end_h=end_h)
        story["precool_f"] = precool_f
        story["precool_window"] = f"{precool_start_h}:00–{precool_end_h}:00"
        story["algorithm"] = (
            f"Precool Clg/DAT −{precool_f:g}°F {precool_start_h}:00–{precool_end_h}:00; "
            f"CHW plant OFF {start_h}:00–{end_h}:00 (thermal mass through peak)"
        )
    else:
        story["algorithm"] = "baseline (no DR patch)"

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    return story


def parse_hourly_facility_kw(eplusout_csv: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with eplusout_csv.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return rows
        col = None
        for i, name in enumerate(header):
            if "Electricity:Facility" in name and "Hourly" in name:
                col = i
                break
        if col is None:
            raise RuntimeError(f"No Electricity:Facility Hourly in {eplusout_csv}")
        for row in reader:
            if len(row) <= col:
                continue
            stamp = row[0] if row else ""
            try:
                val_j = float(row[col])
            except ValueError:
                continue
            hour = None
            m = re.search(r"(\d{1,2}):\d{2}:\d{2}", stamp)
            if m:
                hour = int(m.group(1)) or 24
            if hour is None:
                continue
            rows.append({"hour": hour, "kw": val_j / 3_600_000.0})
    by_h: dict[int, float] = {}
    for r in rows:
        by_h[int(r["hour"])] = float(r["kw"])
    return [{"hour": h, "kw": round(by_h[h], 3)} for h in range(1, 25) if h in by_h]


def _event_mean(hourly: list[dict[str, float]], start_h: int = 14, end_h: int = 16) -> float | None:
    vals = [r["kw"] for r in hourly if start_h < r["hour"] <= end_h]
    if not vals:
        vals = [r["kw"] for r in hourly if start_h <= r["hour"] <= end_h]
    if not vals:
        return None
    return sum(vals) / len(vals)


def run_case(
    twin_idf: Path,
    epw: Path,
    out_dir: Path,
    label: str,
    *,
    day_meta: dict[str, Any],
    mode: Mode,
    mode_kwargs: dict[str, Any],
    engine: str = "auto",
) -> dict[str, Any]:
    """Run one patched single-day sim.

    ``engine``: ``native`` (host energyplus.exe), ``docker``, or ``auto``
    (native if exe present, else docker).
    """
    case_dir = out_dir / f"sim_{label}"
    case_dir.mkdir(parents=True, exist_ok=True)
    idf = out_dir / f"{label}.idf"
    story = patch_idf(
        twin_idf,
        idf,
        month=day_meta["month"],
        day=day_meta["day"],
        year=day_meta["year"],
        dow=day_meta["dow"],
        mode=mode,
        **mode_kwargs,
    )
    local_epw = idf.with_suffix(".epw")
    shutil.copy2(epw, local_epw)

    eng = (engine or "auto").lower().strip()
    if eng == "auto":
        try:
            from native_energyplus import native_energyplus_available

            eng = "native" if native_energyplus_available() else "docker"
        except Exception:
            # tools/ may not be on path — try ml/
            ml = Path(__file__).resolve().parent.parent / "ml"
            if str(ml) not in sys.path:
                sys.path.insert(0, str(ml))
            try:
                from native_energyplus import native_energyplus_available

                eng = "native" if native_energyplus_available() else "docker"
            except Exception:
                eng = "docker"

    if eng == "native":
        ml = Path(__file__).resolve().parent.parent / "ml"
        if str(ml) not in sys.path:
            sys.path.insert(0, str(ml))
        from native_energyplus import run_energyplus_native

        proc = run_energyplus_native(idf, local_epw, case_dir, readvars=True, timeout=7200)
    else:
        from wattlab.energyplus.docker import run_energyplus

        proc = run_energyplus(idf, local_epw, case_dir, readvars=True, timeout=7200)

    csv_path = case_dir / "eplusout.csv"
    if not csv_path.is_file():
        found = list(case_dir.rglob("eplusout.csv"))
        csv_path = found[0] if found else csv_path
    hourly = parse_hourly_facility_kw(csv_path) if csv_path.is_file() else []
    mean_kw = _event_mean(hourly)
    return {
        "label": label,
        "day": f"{day_meta['year']}-{day_meta['month']:02d}-{day_meta['day']:02d}",
        "dow": day_meta["dow"],
        "max_db_c": day_meta.get("max_db_c"),
        "mode": mode,
        "engine": eng,
        "story": story,
        "rc": getattr(proc, "returncode", None),
        "eplusout_csv": str(csv_path) if csv_path.is_file() else None,
        "hourly_kw": hourly,
        "event_mean_kw_14_16": None if mean_kw is None else round(mean_kw, 2),
        "peak_kw": None if not hourly else round(max(r["kw"] for r in hourly), 2),
    }


def _reload_case(out_dir: Path, label: str, meta: dict[str, Any], mode: Mode) -> dict[str, Any]:
    csv_path = out_dir / f"sim_{label}" / "eplusout.csv"
    if not csv_path.is_file():
        found = (
            list((out_dir / f"sim_{label}").rglob("eplusout.csv"))
            if (out_dir / f"sim_{label}").is_dir()
            else []
        )
        csv_path = found[0] if found else csv_path
    hourly = parse_hourly_facility_kw(csv_path) if csv_path.is_file() else []
    mean_kw = _event_mean(hourly)
    return {
        "label": label,
        "day": f"{meta['year']}-{meta['month']:02d}-{meta['day']:02d}",
        "dow": meta["dow"],
        "max_db_c": meta.get("max_db_c"),
        "mode": mode,
        "hourly_kw": hourly,
        "event_mean_kw_14_16": None if mean_kw is None else round(mean_kw, 2),
        "peak_kw": None if not hourly else round(max(r["kw"] for r in hourly), 2),
    }


def _window_kwh(hourly: list[dict[str, float]], start_h: int, end_h: int) -> float | None:
    """Integrate kW over hour-ending (start_h, end_h] → approx kWh (1 h bins)."""
    vals = [r["kw"] for r in hourly if start_h < r["hour"] <= end_h]
    if not vals:
        return None
    return round(sum(vals), 2)


def _deltas_vs_baseline(payload: dict[str, Any]) -> None:
    base_case = payload["cases"].get("weekday_baseline") or {}
    base = base_case.get("event_mean_kw_14_16")
    base_h = base_case.get("hourly_kw") or []
    if base is None:
        return
    for label, case in payload["cases"].items():
        if label == "weekday_baseline" or case.get("mode") == "baseline":
            continue
        s = case.get("event_mean_kw_14_16")
        if s is None:
            continue
        dkw = round(base - s, 2)
        case["delta_kw_vs_weekday_baseline"] = dkw
        case["kwh_event_vs_weekday_baseline"] = round(dkw * 2.0, 2)
        # Load-shift shape: morning (06–12) vs afternoon (12–18) energy vs baseline
        ch = case.get("hourly_kw") or []
        bm = _window_kwh(base_h, 6, 12)
        ba = _window_kwh(base_h, 12, 18)
        cm = _window_kwh(ch, 6, 12)
        ca = _window_kwh(ch, 12, 18)
        if bm is not None and cm is not None:
            case["morning_kwh_delta_6_12"] = round(cm - bm, 2)
        if ba is not None and ca is not None:
            case["afternoon_kwh_delta_12_18"] = round(ca - ba, 2)
        payload.setdefault("deltas_vs_weekday_baseline", {})[label] = {
            "delta_kw_14_16": dkw,
            "kwh_event_14_16": round(dkw * 2.0, 2),
            "morning_kwh_delta_6_12": case.get("morning_kwh_delta_6_12"),
            "afternoon_kwh_delta_12_18": case.get("afternoon_kwh_delta_12_18"),
        }
    # Back-compat keys for prior Demand tab
    ls = payload["cases"].get("weekday_loadshed_p5f") or {}
    if ls.get("event_mean_kw_14_16") is not None:
        payload["loadshed_delta_kw"] = ls.get("delta_kw_vs_weekday_baseline")
        payload["loadshed_kwh_event"] = ls.get("kwh_event_vs_weekday_baseline")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--twin-idf", default=str(IDF))
    ap.add_argument("--epw", default=str(EPW))
    ap.add_argument("--out-dir", default=str(OUT))
    ap.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Optional case labels to run (default: all). Existing cases merge from JSON.",
    )
    ap.add_argument("--skip-sim", action="store_true")
    ap.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Skip cases that already have eplusout.csv under sim_<label>/",
    )
    args = ap.parse_args(argv)

    twin = Path(args.twin_idf)
    epw = Path(args.epw)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not twin.is_file() or not epw.is_file():
        print("missing idf/epw", twin, epw, file=sys.stderr)
        return 2

    days = _pick_hot_july_days(epw)
    out_json = out_dir / "july_demand_profiles.json"
    prior: dict[str, Any] = {}
    if out_json.is_file():
        try:
            prior = json.loads(out_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prior = {}

    payload: dict[str, Any] = {
        "twin_id": TWIN_ID,
        "twin_idf": str(twin),
        "epw": str(epw),
        "best_model": True,
        "algorithm": (
            "DR portfolio on hot July weekday: "
            "+5°F Clg+DAT shed 14–16; deadband 5→10°F; CHW OFF; HVAC OFF; "
            "precool−2°F 06–12 then relax DB 12–18 (load shift); "
            "precool + CHW OFF 14–16"
        ),
        "days_selected": days,
        "window": "14:00–16:00",
        "cases": dict(prior.get("cases") or {}),
    }

    only = set(args.only) if args.only else None
    for label, day_key, mode, mode_kwargs in CASE_SPECS:
        if only is not None and label not in only:
            continue
        meta = days[day_key]
        csv_exists = (out_dir / f"sim_{label}" / "eplusout.csv").is_file() or bool(
            list((out_dir / f"sim_{label}").rglob("eplusout.csv"))
            if (out_dir / f"sim_{label}").is_dir()
            else []
        )
        if args.skip_sim or (args.reuse_existing and csv_exists):
            print(f"reload {label} …", flush=True)
            payload["cases"][label] = _reload_case(out_dir, label, meta, mode)
        else:
            print(f"sim {label} {meta} mode={mode} …", flush=True)
            payload["cases"][label] = run_case(
                twin, epw, out_dir, label, day_meta=meta, mode=mode, mode_kwargs=mode_kwargs
            )
            print(
                f"  peak={payload['cases'][label].get('peak_kw')} "
                f"event_mean={payload['cases'][label].get('event_mean_kw_14_16')}",
                flush=True,
            )

    _deltas_vs_baseline(payload)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("wrote", out_json)
    print(json.dumps(payload.get("deltas_vs_weekday_baseline") or {}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
