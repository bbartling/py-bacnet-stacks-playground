"""Occupancy schedule helpers — configurable lease hours for FDD rollups."""

from __future__ import annotations

from datetime import time
from typing import Any

import pandas as pd

DEFAULT_SCHEDULE: dict[str, Any] = {
    "mon_fri": {"start": "06:00", "end": "17:00", "enabled": True},
    "sat": {"start": "07:00", "end": "14:00", "enabled": True},
    "sun": {"enabled": False},
}


def _parse_hhmm(value: str) -> time:
    parts = str(value).strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return time(h, m)


def default_site_settings(*, timezone: str = "America/Chicago") -> dict[str, Any]:
    return {
        "timezone": timezone,
        "comfort_setpoint_f": 72.0,
        "comfort_band_f": 2.0,
        "occupancy": dict(DEFAULT_SCHEDULE),
    }


def merge_site_settings(overrides: dict[str, Any] | None, *, timezone: str = "America/Chicago") -> dict[str, Any]:
    base = default_site_settings(timezone=timezone)
    if not overrides:
        return base
    out = {**base, **{k: v for k, v in overrides.items() if k in base}}
    if "occupancy" in overrides and isinstance(overrides["occupancy"], dict):
        occ = dict(DEFAULT_SCHEDULE)
        occ.update(overrides["occupancy"])
        out["occupancy"] = occ
    return out


def occupancy_summary(schedule: dict[str, Any] | None = None) -> str:
    s = schedule or DEFAULT_SCHEDULE
    parts: list[str] = []
    mf = s.get("mon_fri") or {}
    if mf.get("enabled", True):
        parts.append(f"Mon–Fri {mf.get('start', '06:00')}–{mf.get('end', '17:00')}")
    sat = s.get("sat") or {}
    if sat.get("enabled", True):
        parts.append(f"Sat {sat.get('start', '07:00')}–{sat.get('end', '14:00')}")
    sun = s.get("sun") or {}
    if not sun.get("enabled", False):
        parts.append("Sun closed")
    return " · ".join(parts) if parts else "Custom schedule"


def is_occupied(ts: pd.Series, schedule: dict[str, Any] | None, tz: str) -> pd.Series:
    """Return boolean Series: True when timestamp is within configured lease hours."""
    s = schedule or DEFAULT_SCHEDULE
    local = ts.dt.tz_convert(tz)
    dow = local.dt.dayofweek
    t = local.dt.time

    wd_mask = pd.Series(False, index=ts.index)
    mf = s.get("mon_fri") or {}
    if mf.get("enabled", True):
        wd_mask = (dow < 5) & (t >= _parse_hhmm(mf.get("start", "06:00"))) & (t < _parse_hhmm(mf.get("end", "17:00")))

    sat_mask = pd.Series(False, index=ts.index)
    sat = s.get("sat") or {}
    if sat.get("enabled", True):
        sat_mask = (dow == 5) & (t >= _parse_hhmm(sat.get("start", "07:00"))) & (t < _parse_hhmm(sat.get("end", "14:00")))

    sun = s.get("sun") or {}
    if sun.get("enabled", False):
        sun_cfg = sun
        sun_mask = (dow == 6) & (t >= _parse_hhmm(sun_cfg.get("start", "08:00"))) & (t < _parse_hhmm(sun_cfg.get("end", "12:00")))
        return wd_mask | sat_mask | sun_mask

    return wd_mask | sat_mask
