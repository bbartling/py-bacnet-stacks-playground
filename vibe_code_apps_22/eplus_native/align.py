"""UTC measured demand ↔ EnergyPlus local-standard-time alignment.

EnergyPlus weather / CSV stamps are **local standard time** (no DST). For Lakeside
(southern WI / Madison AMY), that is fixed **CST = UTC−6**. Do **not** apply
America/Chicago DST when converting E+ LST stamps to UTC.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

TZ_CHICAGO = ZoneInfo("America/Chicago")
TZ_UTC = ZoneInfo("UTC")

# EnergyPlus LST for this site (Madison AMY built as CST-6) — never DST.
EPLUS_LST_OFFSET = timezone(timedelta(hours=-6))
CST = EPLUS_LST_OFFSET


def utc_to_chicago_local(ts_utc: pd.Series) -> pd.Series:
    """Convert UTC timestamps to America/Chicago (DST-aware wall clock).

    Use for **measured** BAS/utility series, not for EnergyPlus LST stamps.
    """
    s = pd.to_datetime(ts_utc, utc=True)
    return s.dt.tz_convert(TZ_CHICAGO)


def chicago_local_to_utc(ts_local: pd.Series) -> pd.Series:
    """DST-aware Chicago wall clock → UTC (measured series only)."""
    s = pd.to_datetime(ts_local)
    if s.dt.tz is None:
        s = s.dt.tz_localize(TZ_CHICAGO, ambiguous="infer", nonexistent="shift_forward")
    return s.dt.tz_convert(TZ_UTC)


def eplus_lst_to_utc(ts_lst: pd.Series) -> pd.Series:
    """Convert EnergyPlus LST (fixed CST−6) timestamps to UTC."""
    s = pd.to_datetime(ts_lst)
    if getattr(s.dt, "tz", None) is None:
        s = s.dt.tz_localize(EPLUS_LST_OFFSET)
    else:
        s = s.dt.tz_convert(EPLUS_LST_OFFSET)
    return s.dt.tz_convert(TZ_UTC)


def aggregate_5min_to_hourly_mean(df: pd.DataFrame, *, ts_col: str, kw_col: str) -> pd.DataFrame:
    """5-minute kW → hourly mean kW. Timestamp = interval end (hour ending)."""
    out = df[[ts_col, kw_col]].copy()
    out[ts_col] = pd.to_datetime(out[ts_col], utc=True)
    out = out.set_index(ts_col).sort_index()
    hourly = out[kw_col].resample("1h", label="right", closed="right").mean().to_frame("kw_mean")
    hourly["n_intervals"] = out[kw_col].resample("1h", label="right", closed="right").count()
    return hourly.reset_index().rename(columns={ts_col: "timestamp_utc"})


def aggregate_5min_to_15min_mean(df: pd.DataFrame, *, ts_col: str, kw_col: str) -> pd.DataFrame:
    """5-minute kW → 15-minute mean kW (tariff / model convention). Never use max of 5-min as 15-min demand."""
    out = df[[ts_col, kw_col]].copy()
    out[ts_col] = pd.to_datetime(out[ts_col], utc=True)
    out = out.set_index(ts_col).sort_index()
    q = out[kw_col].resample("15min", label="right", closed="right").mean().to_frame("kw_mean")
    q["n_intervals"] = out[kw_col].resample("15min", label="right", closed="right").count()
    return q.reset_index().rename(columns={ts_col: "timestamp_utc"})


def parse_eplus_csv_timestamp(stamp: str, year_hint: int | None = None) -> datetime | None:
    """Parse EnergyPlus CSV Date/Time like '01/15  14:15:00' or '01/15  24:00:00' as LST.

    Returns timezone-aware datetime in **fixed CST (UTC−6)** marking **interval end**.
    ``24:00`` becomes next day 00:00. Does **not** use America/Chicago DST.
    """
    s = str(stamp).strip()
    m = re_match_eplus(s)
    if not m:
        return None
    month, day, hour, minute, second = m
    y = year_hint or 2025
    if hour == 24:
        # end of day → next calendar day 00:00
        base = datetime(y, month, day, 0, 0, 0) + timedelta(days=1)
        return base.replace(tzinfo=EPLUS_LST_OFFSET)
    try:
        return datetime(y, month, day, hour, minute, second, tzinfo=EPLUS_LST_OFFSET)
    except ValueError:
        return None


def re_match_eplus(s: str):
    import re

    m = re.match(
        r"^(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2}):(\d{2})$",
        s,
    )
    if not m:
        return None
    return (
        int(m.group(1)),
        int(m.group(2)),
        int(m.group(3)),
        int(m.group(4)),
        int(m.group(5)),
    )


def mae_rmse_mbe(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true, y_pred = y_true[mask], y_pred[mask]
    n = len(y_true)
    if n == 0:
        return {"n": 0, "mae": float("nan"), "rmse": float("nan"), "mbe": float("nan"), "nmbe_pct": float("nan")}
    err = y_pred - y_true
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    mbe = float(np.mean(err))
    mean_obs = float(np.mean(y_true))
    nmbe = float(np.sum(y_true - y_pred) / (n * mean_obs) * 100.0) if abs(mean_obs) > 1e-12 else float("nan")
    return {"n": n, "mae": mae, "rmse": rmse, "mbe": mbe, "nmbe_pct": nmbe}


def cvrmse_pct(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """CVRMSE with denominator = |mean(observed)| (Guideline 14 style)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true, y_pred = y_true[mask], y_pred[mask]
    n = len(y_true)
    if n < 2:
        return {"n": n, "cvrmse_pct": float("nan"), "denominator": "mean_obs"}
    mean_obs = float(np.mean(y_true))
    mse = float(np.sum((y_true - y_pred) ** 2) / (n - 1))
    cv = float(np.sqrt(mse) / abs(mean_obs) * 100.0) if abs(mean_obs) > 1e-12 else float("nan")
    return {"n": n, "cvrmse_pct": cv, "denominator": "mean_obs", "mean_obs": mean_obs}


def peak_magnitude_timing_error(
    measured: pd.Series,
    modeled: pd.Series,
) -> dict[str, float]:
    """Daily peak magnitude (kW) and timing (hours) error on aligned series."""
    if measured.empty or modeled.empty:
        return {"peak_mag_err_kw": float("nan"), "peak_time_err_h": float("nan")}
    i_m = int(np.nanargmax(measured.to_numpy()))
    i_p = int(np.nanargmax(modeled.to_numpy()))
    mag_err = float(modeled.iloc[i_p] - measured.iloc[i_m])
    # assume hourly index positions
    time_err = float(i_p - i_m)
    return {
        "meas_peak_kw": float(measured.iloc[i_m]),
        "mod_peak_kw": float(modeled.iloc[i_p]),
        "peak_mag_err_kw": mag_err,
        "peak_time_err_h": time_err,
    }
