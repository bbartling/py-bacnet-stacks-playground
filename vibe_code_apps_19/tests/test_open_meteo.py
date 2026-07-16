"""Unit tests for Open-Meteo fetch (HTTP mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.open_meteo import align_to_index, dew_point_f_from_rh, fetch_open_meteo, geocode


def test_dew_point_magnus():
    # 70°F @ 50% RH → dew point roughly mid-50s °F
    dp = dew_point_f_from_rh(70.0, 50.0)
    assert 45.0 < dp < 60.0


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_open_meteo_hourly_mocked():
    payload = {
        "hourly": {
            "time": [
                "2024-06-01T00:00",
                "2024-06-01T01:00",
                "2024-06-01T02:00",
            ],
            "temperature_2m": [70.0, 71.0, 72.0],
            "relative_humidity_2m": [50.0, 55.0, 60.0],
            "dew_point_2m": [50.0, 52.0, 54.0],
            "wind_speed_10m": [5.0, 6.0, 7.0],
            "wind_direction_10m": [180.0, 190.0, 200.0],
            "surface_pressure": [1013.0, 1012.0, 1011.0],
            "shortwave_radiation": [0.0, 100.0, 200.0],
            "direct_normal_irradiance": [0.0, 80.0, 150.0],
            "diffuse_radiation": [0.0, 20.0, 50.0],
        }
    }
    session = MagicMock()
    session.get.return_value = _Resp(payload)
    df = fetch_open_meteo(
        42.33,
        -83.05,
        "2024-06-01",
        "2024-06-01",
        grid_minutes=60,
        session=session,
    )
    assert isinstance(df.index, pd.DatetimeIndex)
    assert "web-outside-air-temp" in df.columns
    assert len(df) == 3
    assert df.attrs["open_meteo"]["lat"] == pytest.approx(42.33)
    session.get.assert_called_once()


def test_geocode_mocked():
    payload = {
        "results": [
            {
                "name": "Detroit",
                "admin1": "Michigan",
                "country": "United States",
                "latitude": 42.33,
                "longitude": -83.05,
            }
        ]
    }
    session = MagicMock()
    session.get.return_value = _Resp(payload)
    lat, lon, label = geocode("Detroit", session=session)
    assert lat == pytest.approx(42.33)
    assert lon == pytest.approx(-83.05)
    assert "Detroit" in label


def test_align_to_index():
    idx = pd.date_range("2024-06-01", periods=3, freq="1h", tz="UTC")
    wx = pd.DataFrame(
        {"web-outside-air-temp": [70.0, 72.0, 74.0]},
        index=idx,
    )
    fine = pd.date_range("2024-06-01", periods=5, freq="30min", tz="UTC")
    aligned = align_to_index(wx, fine)
    assert len(aligned) == 5
    assert aligned["web-outside-air-temp"].notna().all()
