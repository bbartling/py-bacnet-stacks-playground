"""Small fuel-tab helpers: peer EUI bands + optional monthly HDD/CDD."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

DD_BASE_F = 65.0

# EPA Portfolio Manager national median site EUI (kBtu/ft²-yr) + screening p20/p80.
_PEER_BANDS: dict[str, dict[str, Any]] = {
    "office": {
        "property_type": "office",
        "p20": 34.0,
        "p50": 52.9,
        "p80": 71.0,
        "source": "EPA Portfolio Manager U.S. national median site EUI",
    },
    "k12_school": {
        "property_type": "k12_school",
        "p20": 31.0,
        "p50": 48.5,
        "p80": 65.0,
        "source": "EPA Portfolio Manager U.S. national median site EUI",
    },
    "default": {
        "property_type": "commercial_all",
        "p20": 46.0,
        "p50": 70.6,
        "p80": 95.0,
        "source": "EIA CBECS 2018 average U.S. commercial-building site energy",
    },
}


def eui_peer_band(property_type: str | None) -> dict[str, Any]:
    """Return simple hardcoded EPA/CBECS-ish p20/p50/p80 for office / k12 / default."""
    key = (property_type or "default").strip().lower().replace("-", "_").replace(" ", "_")
    if key in ("k12", "school", "k_12_school"):
        key = "k12_school"
    if key not in _PEER_BANDS:
        key = "default"
    return dict(_PEER_BANDS[key])


def degree_days_from_hourly_oat(
    hourly: pd.DataFrame,
    *,
    oat_col: str = "oat_f",
    month_col: str | None = None,
    base_f: float = DD_BASE_F,
) -> pd.DataFrame:
    """Monthly HDD/CDD from hourly OAT °F (65°F base). Empty if no usable OAT."""
    empty = pd.DataFrame(columns=["month", "hdd", "cdd"])
    if hourly is None or hourly.empty or oat_col not in hourly.columns:
        return empty
    work = hourly.copy()
    oat = pd.to_numeric(work[oat_col], errors="coerce")
    if month_col and month_col in work.columns:
        months = work[month_col].astype(str).str[:7]
    elif "local_day" in work.columns:
        months = work["local_day"].astype(str).str[:7]
    elif "timestamp" in work.columns:
        months = pd.to_datetime(work["timestamp"], errors="coerce").dt.strftime("%Y-%m")
    elif "timestamp_utc" in work.columns:
        months = pd.to_datetime(work["timestamp_utc"], errors="coerce").dt.strftime("%Y-%m")
    else:
        return empty
    hdd_h = (base_f - oat).clip(lower=0.0) / 24.0
    cdd_h = (oat - base_f).clip(lower=0.0) / 24.0
    out = (
        pd.DataFrame({"month": months, "hdd": hdd_h, "cdd": cdd_h})
        .dropna(subset=["month"])
        .groupby("month", as_index=False)
        .sum(numeric_only=True)
        .sort_values("month")
        .reset_index(drop=True)
    )
    return out


def degree_days_from_bas_csv(
    path: Path | str | None,
    *,
    base_f: float = DD_BASE_F,
) -> pd.DataFrame:
    """HDD/CDD from a BAS demand×OAT CSV when ``oat_f`` is present."""
    empty = pd.DataFrame(columns=["month", "hdd", "cdd"])
    if path is None:
        return empty
    p = Path(path)
    if not p.is_file():
        return empty
    try:
        raw = pd.read_csv(p)
    except (OSError, pd.errors.ParserError):
        return empty
    cols = {str(c).strip().lower(): c for c in raw.columns}
    oat_c = cols.get("oat_f") or cols.get("oat") or cols.get("temp_f")
    if oat_c is None:
        return empty
    frame = pd.DataFrame({"oat_f": pd.to_numeric(raw[oat_c], errors="coerce")})
    for cand in ("local_day", "timestamp", "timestamp_utc", "month"):
        if cand in cols:
            frame[cand] = raw[cols[cand]]
    return degree_days_from_hourly_oat(frame, base_f=base_f)


def hdd_cdd_monthly(
    lat: float | None,
    lon: float | None,
    months: list[str] | None = None,
    *,
    bas_csv: Path | str | None = None,
    hourly_oat_csv: Path | str | None = None,
) -> pd.DataFrame:
    """Monthly HDD/CDD for fuel analytics.

    Prefers BAS ``oat_f`` from the demand CSV, then a local hourly OAT CSV.
    Open-Meteo fetch is intentionally stubbed (empty) to keep the UI light.
    ``lat`` / ``lon`` are accepted for API compatibility.
    """
    del lat, lon  # reserved for a future Open-Meteo path
    empty = pd.DataFrame(columns=["month", "hdd", "cdd"])
    for src in (bas_csv, hourly_oat_csv):
        dd = degree_days_from_bas_csv(src)
        if not dd.empty:
            if months:
                want = {str(m)[:7] for m in months}
                dd = dd[dd["month"].isin(want)]
            return dd.reset_index(drop=True)
    return empty


__all__ = [
    "DD_BASE_F",
    "eui_peer_band",
    "degree_days_from_hourly_oat",
    "degree_days_from_bas_csv",
    "hdd_cdd_monthly",
]
