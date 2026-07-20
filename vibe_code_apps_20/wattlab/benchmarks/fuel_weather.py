"""Fuel × weather analytics for the Studio Fuel Weather dashboard.

Aligns campus monthly bills with HDD/CDD, fits simple OLS (gas×HDD,
electric×CDD), and builds tidy frames for timelines / intensity heatmaps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from wattlab.benchmarks.meters import (
    KBTU_PER_KWH,
    KBTU_PER_MCF,
    THERMS_PER_MCF,
    Campus,
    latest_complete_window,
)
from wattlab.weather.degree_days import DD_BASE_F, degree_day_meta, monthly_degree_days

MIN_OVERLAP_MONTHS = 6


@dataclass(frozen=True)
class FuelFit:
    fuel: str
    x_name: str
    y_name: str
    unit: str
    n: int
    slope: float
    intercept: float
    r2: float
    base_f: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "fuel": self.fuel,
            "x": self.x_name,
            "y": self.y_name,
            "unit": self.unit,
            "n_months": self.n,
            "slope": round(self.slope, 6),
            "intercept": round(self.intercept, 4),
            "r2": round(self.r2, 4),
            "base_f": self.base_f,
        }


def ols_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Return slope, intercept, R² for y ≈ slope*x + intercept."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    n = int(x.size)
    if n < 2:
        return float("nan"), float("nan"), float("nan")
    if float(np.std(x)) < 1e-12:
        return float("nan"), float("nan"), float("nan")
    try:
        slope, intercept = np.polyfit(x, y, 1)
    except np.linalg.LinAlgError:
        return float("nan"), float("nan"), float("nan")
    y_hat = slope * x + intercept
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return float(slope), float(intercept), float(r2)


def _usage_to_kbtu(usage: float, fuel: str, unit: str) -> float:
    u = (unit or "").lower()
    f = (fuel or "").lower()
    if f.startswith("elec") or u == "kwh":
        return float(usage) * KBTU_PER_KWH
    if u in ("therm", "therms"):
        return float(usage) * 100.0  # 1 therm = 100 kBtu
    # default gas as Mcf
    return float(usage) * KBTU_PER_MCF


def meter_monthly_long(campus: Campus) -> pd.DataFrame:
    """Long frame: month, meter_id, fuel, unit, usage, cost_usd?, demand_kw?, kbtu."""
    rows: list[dict[str, Any]] = []
    for m in campus.meters:
        for _, r in m.bills.iterrows():
            usage = float(r["usage"]) if pd.notna(r["usage"]) else float("nan")
            row: dict[str, Any] = {
                "month": str(r["month"]),
                "meter_id": m.meter_id,
                "fuel": m.fuel,
                "unit": m.unit,
                "usage": usage,
                "kbtu": _usage_to_kbtu(usage, m.fuel, m.unit) if np.isfinite(usage) else float("nan"),
                "serves": ",".join(m.serves),
                "shared": bool(m.shared),
            }
            if "cost_usd" in r and pd.notna(r["cost_usd"]):
                row["cost_usd"] = float(r["cost_usd"])
            if "demand_kw" in r and pd.notna(r["demand_kw"]):
                row["demand_kw"] = float(r["demand_kw"])
            rows.append(row)
    return pd.DataFrame(rows)


def campus_fuel_totals(campus: Campus, window: list[str] | None = None) -> pd.DataFrame:
    """Monthly campus totals by fuel (sum of meters; shared elec counted once)."""
    long = meter_monthly_long(campus)
    if window is not None:
        long = long[long["month"].isin(window)]
    if long.empty:
        return pd.DataFrame(columns=["month", "fuel", "usage", "kbtu", "demand_kw", "unit"])

    parts: list[pd.DataFrame] = []
    for fuel, g in long.groupby("fuel"):
        # One row per meter-month already; summing meters of same fuel is correct
        # (shared electric appears once as one meter).
        aggs: dict[str, Any] = {
            "usage": ("usage", "sum"),
            "kbtu": ("kbtu", "sum"),
            "unit": ("unit", "first"),
        }
        if "demand_kw" in g.columns:
            aggs["demand_kw"] = ("demand_kw", "max")
        agg = g.groupby("month", as_index=False).agg(**aggs)
        agg.insert(1, "fuel", fuel)
        parts.append(agg)
    out = pd.concat(parts, ignore_index=True).sort_values(["month", "fuel"])
    return out.reset_index(drop=True)


def intensity_heatmap_frame(
    campus: Campus,
    *,
    fuel: str,
    window: list[str] | None = None,
) -> pd.DataFrame:
    """Year × month matrix of site kBtu/ft² for one fuel (campus total / total area)."""
    totals = campus_fuel_totals(campus, window)
    fuel_key = "electricity" if fuel.startswith("elec") else "gas"
    sub = totals[totals["fuel"] == fuel_key].copy()
    if sub.empty:
        return pd.DataFrame()
    area = max(campus.total_area_ft2, 1.0)
    sub["intensity_kbtu_ft2"] = sub["kbtu"] / area
    sub["year"] = sub["month"].str[:4].astype(int)
    sub["mon"] = sub["month"].str[5:7].astype(int)
    mat = sub.pivot_table(
        index="year", columns="mon", values="intensity_kbtu_ft2", aggfunc="sum"
    )
    return mat.reindex(columns=range(1, 13)).sort_index(ascending=False)


def demand_heatmap_frame(campus: Campus, window: list[str] | None = None) -> pd.DataFrame:
    """Year × month matrix of billed demand (kW) from electric meters."""
    long = meter_monthly_long(campus)
    if "demand_kw" not in long.columns:
        return pd.DataFrame()
    elec = long[long["fuel"] == "electricity"].copy()
    if window is not None:
        elec = elec[elec["month"].isin(window)]
    if elec.empty:
        return pd.DataFrame()
    elec["year"] = elec["month"].str[:4].astype(int)
    elec["mon"] = elec["month"].str[5:7].astype(int)
    mat = elec.pivot_table(index="year", columns="mon", values="demand_kw", aggfunc="max")
    return mat.reindex(columns=range(1, 13)).sort_index(ascending=False)


def align_fuel_and_degree_days(
    campus: Campus,
    hourly_oat: pd.Series | pd.DataFrame,
    *,
    base_f: float = DD_BASE_F,
    months: int = 12,
) -> tuple[pd.DataFrame, list[str]]:
    """Join campus fuel totals to monthly HDD/CDD; return frame + analysis window."""
    dd = monthly_degree_days(hourly_oat, base_f=base_f)
    totals = campus_fuel_totals(campus)
    month_sets = [set(m.bills["month"]) for m in campus.meters] + [set(dd["month"])]
    window = latest_complete_window(month_sets, months=months)
    if window is None:
        # Fall back to intersection sorted
        common = set.intersection(*month_sets) if month_sets else set()
        window = sorted(common)
    fuel_w = totals[totals["month"].isin(window)].copy() if window else totals.copy()
    merged = fuel_w.merge(dd, on="month", how="inner")
    return merged.sort_values(["month", "fuel"]).reset_index(drop=True), list(window or [])


def fit_weather_responses(
    aligned: pd.DataFrame,
    *,
    base_f: float = DD_BASE_F,
    min_months: int = MIN_OVERLAP_MONTHS,
) -> list[FuelFit]:
    """OLS: gas vs HDD, electricity vs CDD (native meter units)."""
    fits: list[FuelFit] = []
    specs = (
        ("gas", "hdd", "Gas vs HDD"),
        ("electricity", "cdd", "Electric vs CDD"),
    )
    for fuel, x_col, _label in specs:
        sub = aligned[aligned["fuel"] == fuel]
        if len(sub) < min_months:
            continue
        unit = str(sub["unit"].iloc[0])
        slope, intercept, r2 = ols_fit(sub[x_col].to_numpy(), sub["usage"].to_numpy())
        if not np.isfinite(r2):
            continue
        fits.append(
            FuelFit(
                fuel=fuel,
                x_name=x_col,
                y_name="usage",
                unit=unit,
                n=int(len(sub)),
                slope=slope,
                intercept=intercept,
                r2=r2,
                base_f=base_f,
            )
        )
    return fits


def residual_frame(aligned: pd.DataFrame, fit: FuelFit) -> pd.DataFrame:
    sub = aligned[aligned["fuel"] == fit.fuel].copy()
    x = sub[fit.x_name].astype(float)
    y = sub["usage"].astype(float)
    sub["predicted"] = fit.slope * x + fit.intercept
    sub["residual"] = y - sub["predicted"]
    return sub[["month", "usage", "predicted", "residual", fit.x_name]].reset_index(drop=True)


def gas_usage_therms(usage: float, unit: str) -> float:
    u = (unit or "").lower()
    if u in ("therm", "therms"):
        return float(usage)
    return float(usage) * THERMS_PER_MCF


def build_fuel_weather_report(
    campus: Campus,
    hourly_oat: pd.Series | pd.DataFrame,
    *,
    base_f: float = DD_BASE_F,
    weather_source: str = "synthetic_or_open_meteo",
) -> dict[str, Any]:
    """Bundle aligned series, fits, and provenance for Studio / tests."""
    aligned, window = align_fuel_and_degree_days(campus, hourly_oat, base_f=base_f)
    fits = fit_weather_responses(aligned, base_f=base_f)
    return {
        "campus_id": campus.campus_id,
        "label": campus.label,
        "window": {"start": window[0] if window else None, "end": window[-1] if window else None, "months": window},
        "degree_days": degree_day_meta(base_f=base_f, source=weather_source),
        "fits": [f.as_dict() for f in fits],
        "aligned_rows": int(len(aligned)),
        "n_fits": len(fits),
    }


__all__ = [
    "FuelFit",
    "MIN_OVERLAP_MONTHS",
    "align_fuel_and_degree_days",
    "build_fuel_weather_report",
    "campus_fuel_totals",
    "demand_heatmap_frame",
    "fit_weather_responses",
    "gas_usage_therms",
    "intensity_heatmap_frame",
    "meter_monthly_long",
    "ols_fit",
    "residual_frame",
]
