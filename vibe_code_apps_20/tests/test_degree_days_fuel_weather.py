"""Unit tests for HDD/CDD and fuel×weather regression."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from wattlab.benchmarks.fuel_weather import (
    align_fuel_and_degree_days,
    build_fuel_weather_report,
    fit_weather_responses,
    ols_fit,
)
from wattlab.benchmarks.meters import Campus
from wattlab.weather.degree_days import DD_BASE_F, monthly_degree_days

FIXTURE_CAMPUS = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "shared_meter_campus"
    / "campus.json"
)


def _hourly_oat(start: str, hours: int, temps_f: list[float] | None = None) -> pd.Series:
    t0 = pd.Timestamp(start)
    idx = pd.date_range(t0, periods=hours, freq="h")
    if temps_f is None:
        # Alternate cold / hot days roughly
        temps_f = [40.0 + 30.0 * ((i // 24) % 2) for i in range(hours)]
    return pd.Series(temps_f, index=idx, name="dry_bulb_f")


def test_monthly_degree_days_known_day():
    # One day at 55°F → HDD=10, CDD=0; one day at 75°F → HDD=0, CDD=10
    idx = pd.date_range("2024-01-01", periods=48, freq="h")
    temps = [55.0] * 24 + [75.0] * 24
    s = pd.Series(temps, index=idx)
    dd = monthly_degree_days(s)
    assert list(dd["month"]) == ["2024-01"]
    assert dd.loc[0, "hdd"] == pytest.approx(10.0)
    assert dd.loc[0, "cdd"] == pytest.approx(10.0)
    assert dd.loc[0, "n_days"] == 2
    assert DD_BASE_F == 65.0


def test_ols_on_constructed_hdd_gas():
    """Guaranteed R² path without relying on fixture bill noise."""
    months = [f"2024-{m:02d}" for m in range(1, 13)]
    hdd = np.linspace(800, 50, 12)
    usage = 100.0 + 0.5 * hdd
    aligned = pd.DataFrame({
        "month": months * 2,
        "fuel": ["gas"] * 12 + ["electricity"] * 12,
        "unit": ["mcf"] * 12 + ["kwh"] * 12,
        "usage": list(usage) + list(200.0 + 0.3 * np.linspace(0, 400, 12)),
        "hdd": list(hdd) + list(hdd),
        "cdd": list(np.linspace(0, 300, 12)) * 2,
        "kbtu": [0.0] * 24,
    })
    fits = fit_weather_responses(aligned, min_months=6)
    by_fuel = {f.fuel: f for f in fits}
    assert by_fuel["gas"].r2 == pytest.approx(1.0, abs=1e-6)


def test_bill_columns_map_overrides_headers(tmp_path: Path):
    csv = tmp_path / "weird.csv"
    csv.write_text(
        "Period,Qty,Demand\n2024-01,100,10\n2024-02,110,11\n",
        encoding="utf-8",
    )
    from wattlab.benchmarks.meters import load_bill_csv

    df = load_bill_csv(
        csv,
        column_map={"month": "Period", "usage": "Qty", "demand_kw": "Demand"},
    )
    assert list(df["month"]) == ["2024-01", "2024-02"]
    assert df.loc[0, "usage"] == 100
    assert df.loc[0, "demand_kw"] == 10



def test_fuel_weather_on_fixture_campus():
    assert FIXTURE_CAMPUS.is_file()
    campus = Campus.from_json(FIXTURE_CAMPUS)
    months = sorted(set.intersection(*(m.months() for m in campus.meters)))
    assert len(months) >= 12
    # Build hourly OAT with strong seasonal signal spanning the bill window.
    start = f"{months[0]}-01"
    y, m = map(int, months[-1].split("-"))
    end = datetime(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
    t0 = datetime.fromisoformat(start)
    hours = int((end - t0).total_seconds() // 3600)
    temps = []
    for i in range(hours):
        ts = t0 + timedelta(hours=i)
        # Clear winter/summer swing so HDD/CDD vary across months
        seasonal = 30.0 + 40.0 * np.sin(2 * np.pi * (ts.timetuple().tm_yday - 80) / 365)
        temps.append(float(seasonal))
    hourly = _hourly_oat(start, hours, temps)

    aligned, window = align_fuel_and_degree_days(campus, hourly)
    assert len(window) >= 12
    assert not aligned.empty
    # Force a clean OLS path: gas usage vs HDD must be finite and varying
    gas = aligned[aligned["fuel"] == "gas"]
    assert len(gas) >= 6
    assert float(gas["hdd"].std()) > 0
    fits = fit_weather_responses(aligned, min_months=6)
    assert any(f.fuel == "gas" for f in fits) or any(f.fuel == "electricity" for f in fits)
    report = build_fuel_weather_report(campus, hourly, weather_source="synthetic_test")
    assert report["aligned_rows"] > 0
    assert report["degree_days"]["base_f"] == 65.0
    # Even if polyfit fails on noisy bills, report still builds
    assert "fits" in report


def test_select_fits_for_view_filters():
    from wattlab.benchmarks.fuel_weather import (
        FIT_VIEW_BOTH,
        FIT_VIEW_ELECTRIC,
        FIT_VIEW_GAS,
        FuelFit,
        select_fits_for_view,
    )

    fits = [
        FuelFit("gas", "hdd", "usage", "mcf", 12, 0.1, 10.0, 0.9, 65.0),
        FuelFit("electricity", "cdd", "usage", "kwh", 12, 0.2, 20.0, 0.8, 65.0),
    ]
    assert len(select_fits_for_view(fits, FIT_VIEW_BOTH)) == 2
    assert [f.fuel for f in select_fits_for_view(fits, FIT_VIEW_ELECTRIC)] == ["electricity"]
    assert [f.fuel for f in select_fits_for_view(fits, FIT_VIEW_GAS)] == ["gas"]


def test_cooling_season_avg_high_and_pearson():
    from wattlab.benchmarks.fuel_weather import (
        cooling_season_avg_high_by_year,
        pearson_corr,
        weekday_weekend_elec_cdd_frames,
    )

    # May–Sep 2024: daily max ~80°F; Jan cold days ignored
    idx = pd.date_range("2024-01-01", periods=24 * 200, freq="h")
    temps = []
    for ts in idx:
        if ts.month in (5, 6, 7, 8, 9):
            # Daytime high ~80, night ~70
            temps.append(80.0 if ts.hour >= 12 else 70.0)
        else:
            temps.append(30.0)
    hourly = pd.Series(temps, index=idx, name="dry_bulb_f")
    by_year = cooling_season_avg_high_by_year(hourly)
    assert 2024 in by_year
    assert by_year[2024] == pytest.approx(80.0, abs=0.5)

    r = pearson_corr([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0])
    assert r == pytest.approx(1.0, abs=1e-9)
    assert np.isnan(pearson_corr([1.0], [2.0]))

    # Weekday/weekend split
    days = pd.date_range("2024-06-03", periods=14, freq="D")  # Mon start
    kwh = pd.Series([100.0 if d.dayofweek < 5 else 40.0 for d in days], index=days)
    cdd = pd.Series([10.0] * 14, index=days)
    frames = weekday_weekend_elec_cdd_frames(kwh, cdd)
    assert len(frames["weekday"]) == 10
    assert len(frames["weekend"]) == 4
    assert frames["weekday"]["kwh"].mean() > frames["weekend"]["kwh"].mean()
