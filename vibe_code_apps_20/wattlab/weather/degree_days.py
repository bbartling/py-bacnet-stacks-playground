"""Heating / cooling degree days from hourly dry-bulb (°F).

Matches the vibe19 metering convention: base 65°F, daily mean OAT, then
monthly sums. Used by the Studio Fuel Weather dashboard (not by AMY EPW).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

DD_BASE_F = 65.0


def daily_mean_oat_f(hourly: pd.Series | pd.DataFrame, *, col: str = "dry_bulb_f") -> pd.Series:
    """Daily mean outdoor air temperature (°F) from an hourly series/frame."""
    if isinstance(hourly, pd.DataFrame):
        if col not in hourly.columns:
            raise KeyError(f"hourly frame missing {col!r}")
        s = hourly[col]
    else:
        s = hourly
    if not isinstance(s.index, pd.DatetimeIndex):
        raise TypeError("hourly series/frame must have a DatetimeIndex")
    return s.astype(float).groupby(s.index.floor("D")).mean()


def degree_days_from_daily(
    daily_mean_f: pd.Series,
    *,
    base_f: float = DD_BASE_F,
) -> pd.DataFrame:
    """Per-day HDD/CDD from daily mean OAT (°F)."""
    mean = daily_mean_f.astype(float)
    hdd = (base_f - mean).clip(lower=0.0)
    cdd = (mean - base_f).clip(lower=0.0)
    out = pd.DataFrame({"hdd": hdd, "cdd": cdd, "mean_oat_f": mean})
    out.index = pd.DatetimeIndex(out.index)
    return out


def monthly_degree_days(
    hourly: pd.Series | pd.DataFrame,
    *,
    col: str = "dry_bulb_f",
    base_f: float = DD_BASE_F,
) -> pd.DataFrame:
    """Monthly HDD/CDD table: columns month (YYYY-MM), hdd, cdd, mean_oat_f, n_days."""
    daily = degree_days_from_daily(daily_mean_oat_f(hourly, col=col), base_f=base_f)
    g = daily.groupby(daily.index.strftime("%Y-%m"))
    out = g.agg(
        hdd=("hdd", "sum"),
        cdd=("cdd", "sum"),
        mean_oat_f=("mean_oat_f", "mean"),
        n_days=("hdd", "count"),
    ).reset_index(names="month")
    return out.sort_values("month").reset_index(drop=True)


def degree_day_meta(*, base_f: float = DD_BASE_F, source: str = "open-meteo-archive") -> dict[str, Any]:
    return {
        "base_f": float(base_f),
        "source": source,
        "method": "daily_mean_oat_then_monthly_sum",
        "convention": "vibe19_metering_DD_BASE_F",
    }


__all__ = [
    "DD_BASE_F",
    "daily_mean_oat_f",
    "degree_days_from_daily",
    "monthly_degree_days",
    "degree_day_meta",
]
