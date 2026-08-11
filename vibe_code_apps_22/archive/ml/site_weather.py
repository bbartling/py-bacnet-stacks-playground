"""Load site measured weather / demand CSVs for attaching OAT/RH/GHI to farm rows.

These are real site files under ``$LAKESIDE_SITE_ROOT`` — not training labels.
Training labels come only from native EnergyPlus farm parquet.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TZ = "America/Chicago"


def load_hourly_demand(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    df = pd.read_csv(path)
    ts = pd.to_datetime(df["hour_utc"], utc=True)
    local = ts.dt.tz_convert(TZ)
    out = pd.DataFrame(
        {
            "timestamp_utc": ts,
            "timestamp_local": local,
            "facility_kw_bas": pd.to_numeric(df["kw_avg"], errors="coerce"),
            "oat_f": pd.to_numeric(df["oat_f"], errors="coerce"),
            "day_type": df["day_type"].astype(str),
        }
    )
    out["hour_ending"] = local.dt.hour.astype(int)
    out["day"] = local.dt.strftime("%Y-%m-%d")
    out["month"] = local.dt.month.astype(int)
    out["doy"] = local.dt.dayofyear.astype(int)
    out["dow"] = local.dt.day_name()
    out["is_weekend"] = (local.dt.dayofweek >= 5).astype(float)
    out["occupied"] = (
        (out["is_weekend"] < 0.5)
        & (out["hour_ending"] >= 7)
        & (out["hour_ending"] < 16)
    ).astype(float)
    return out.dropna(subset=["facility_kw_bas", "oat_f"])


def load_weather_hourly(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=["day", "hour_ending", "rh_pct", "ghi"])
    w = pd.read_csv(path)
    ts = pd.to_datetime(w["timestamp_utc"], utc=True)
    local = ts.dt.tz_convert(TZ)
    w = w.copy()
    w["day"] = local.dt.strftime("%Y-%m-%d")
    w["hour_ending"] = local.dt.hour.astype(int)
    w["rh_pct"] = pd.to_numeric(w["web-outside-air-humidity"], errors="coerce")
    w["ghi"] = pd.to_numeric(w["shortwave_radiation_wm2"], errors="coerce")
    return (
        w.groupby(["day", "hour_ending"], as_index=False)
        .agg(rh_pct=("rh_pct", "mean"), ghi=("ghi", "mean"))
    )
