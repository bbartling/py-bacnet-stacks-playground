"""Metering rollups — monthly kWh/gas + degree days."""

from __future__ import annotations

import pandas as pd

from app.metering import (
    build_meter_monthly_table,
    integrate_rate_to_monthly,
    meter_scatter_frame,
    monthly_degree_days,
)


def test_integrate_kw_to_monthly_kwh():
    idx = pd.date_range("2024-01-01", periods=12, freq="h", tz="UTC")
    # Constant 10 kW for 12 hourly samples → ~120 kWh in January
    rate = pd.Series([10.0] * 12, index=idx)
    monthly = integrate_rate_to_monthly(rate, energy_col="kwh")
    assert len(monthly) == 1
    assert abs(float(monthly.iloc[0]["kwh"]) - 120.0) < 1.0


def test_monthly_cdd_hdd():
    idx = pd.date_range("2024-07-01", periods=3, freq="D", tz="UTC")
    # Daily means 80, 70, 60 → CDD (15+5+0)=20, HDD (0+0+5)=5 at base 65
    oat = pd.Series([80.0, 70.0, 60.0], index=idx)
    cdd = monthly_degree_days(oat, kind="cdd", base_f=65.0)
    hdd = monthly_degree_days(oat, kind="hdd", base_f=65.0)
    assert abs(float(cdd.iloc[0]) - 20.0) < 0.01
    assert abs(float(hdd.iloc[0]) - 5.0) < 0.01


def test_build_meter_electric_with_weather():
    idx = pd.date_range("2024-01-01", periods=48, freq="h", tz="UTC")
    meter = pd.DataFrame({"kw": [5.0] * 48}, index=idx)
    meter.attrs["equipment_type"] = "METER"
    wx = pd.DataFrame({"web-outside-air-temp": [40.0] * 48}, index=idx)
    frames = {"ELEC_1": meter}
    role_map = {"ELEC_1": {"elec-power": "kw", "equipment_type": "METER"}}
    monthly, stats, reason = build_meter_monthly_table(
        frames, role_map, kind="electric", weather=wx, equipment_types=("METER",)
    )
    assert reason == ""
    assert not monthly.empty
    assert "kwh" in monthly.columns
    assert "cdd" in monthly.columns
    assert not stats.empty
    sc = meter_scatter_frame(monthly, kind="electric")
    assert not sc.empty
    assert {"x", "y", "equipment_id"} <= set(sc.columns)
