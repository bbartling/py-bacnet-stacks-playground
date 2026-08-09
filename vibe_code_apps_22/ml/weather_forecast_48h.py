"""48h hourly weather forecast → hybrid weather_forecast_96 / _192.

Primary: OpenWeatherMap (OPENWEATHERMAP_API_KEY).
Fallback / CI: Open-Meteo (no key). Coords hardcoded for Creekside / Madison.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any

import numpy as np

# Lakeside / Creekside (Madison WI area)
SITE_LAT = 43.0731
SITE_LON = -89.4012
STEPS_15 = 96
STEPS_15_48H = 192


def fetch_open_meteo_hourly_48(
    *,
    lat: float = SITE_LAT,
    lon: float = SITE_LON,
    timeout_s: float = 30.0,
) -> dict[str, list[float]]:
    """Return 48 hourly points: oat_f, rh_pct, ghi (W/m2 approx from shortwave)."""
    q = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,relative_humidity_2m,shortwave_radiation",
            "temperature_unit": "fahrenheit",
            "forecast_hours": 48,
            "timezone": "America/Chicago",
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{q}"
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        doc = json.loads(resp.read().decode("utf-8"))
    h = doc["hourly"]
    oat = [float(x) for x in h["temperature_2m"][:48]]
    rh = [float(x) if x is not None else 50.0 for x in h["relative_humidity_2m"][:48]]
    ghi = [float(x) if x is not None else 0.0 for x in h.get("shortwave_radiation", [0.0] * 48)[:48]]
    while len(oat) < 48:
        oat.append(oat[-1] if oat else 20.0)
        rh.append(rh[-1] if rh else 50.0)
        ghi.append(ghi[-1] if ghi else 0.0)
    return {"oat_f": oat[:48], "rh_pct": rh[:48], "ghi": ghi[:48], "source": "open_meteo"}


def fetch_owm_hourly_48(
    api_key: str,
    *,
    lat: float = SITE_LAT,
    lon: float = SITE_LON,
    timeout_s: float = 30.0,
) -> dict[str, list[float]]:
    """OWM One Call 3.0 hourly (up to 48h). Requires paid/key-enabled endpoint."""
    q = urllib.parse.urlencode(
        {
            "lat": lat,
            "lon": lon,
            "exclude": "minutely,daily,alerts",
            "units": "imperial",
            "appid": api_key,
        }
    )
    url = f"https://api.openweathermap.org/data/3.0/onecall?{q}"
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        doc = json.loads(resp.read().decode("utf-8"))
    hours = doc.get("hourly") or []
    oat, rh, ghi = [], [], []
    for row in hours[:48]:
        oat.append(float(row.get("temp", 20.0)))
        rh.append(float(row.get("humidity", 50.0)))
        # OWM clouds 0–100 → crude GHI proxy
        clouds = float(row.get("clouds", 50.0))
        ghi.append(max(0.0, 800.0 * (1.0 - clouds / 100.0)))
    while len(oat) < 48:
        oat.append(oat[-1] if oat else 20.0)
        rh.append(rh[-1] if rh else 50.0)
        ghi.append(0.0)
    return {"oat_f": oat[:48], "rh_pct": rh[:48], "ghi": ghi[:48], "source": "openweathermap"}


def hourly_to_15min(hourly: list[float], n_steps: int) -> list[float]:
    """Repeat each hour into four 15-min slots (piecewise-constant)."""
    out: list[float] = []
    for v in hourly:
        out.extend([float(v)] * 4)
    if len(out) < n_steps:
        out.extend([out[-1] if out else 0.0] * (n_steps - len(out)))
    return out[:n_steps]


def weather_forecast_from_hourly48(
    hourly: dict[str, list[float]],
    *,
    hours: int = 24,
) -> dict[str, Any]:
    """Build hybrid contract weather block for 24h (96) or 48h (192) steps."""
    n_h = 24 if hours <= 24 else 48
    n_steps = STEPS_15 if n_h == 24 else STEPS_15_48H
    return {
        "oat_f": hourly_to_15min(hourly["oat_f"][:n_h], n_steps),
        "rh_pct": hourly_to_15min(hourly["rh_pct"][:n_h], n_steps),
        "ghi": hourly_to_15min(hourly["ghi"][:n_h], n_steps),
        "source": hourly.get("source", "unknown"),
        "n_steps": n_steps,
    }


def load_forecast_48h(*, prefer_owm: bool = True) -> dict[str, list[float]]:
    key = os.environ.get("OPENWEATHERMAP_API_KEY", "").strip()
    if prefer_owm and key:
        return fetch_owm_hourly_48(key)
    return fetch_open_meteo_hourly_48()


def synthetic_hourly_48(*, seed: int = 0, mean_f: float = 10.0) -> dict[str, list[float]]:
    """Deterministic offline forecast for unit tests (no network)."""
    rng = np.random.default_rng(seed)
    h = np.arange(48)
    oat = mean_f + 8.0 * np.sin((h - 14) * np.pi / 12.0) + rng.normal(0, 0.5, size=48)
    rh = np.clip(55.0 + rng.normal(0, 5, size=48), 20, 95)
    ghi = np.clip(300.0 * np.maximum(0.0, np.sin((h - 6) * np.pi / 12.0)), 0, 800)
    return {
        "oat_f": [float(x) for x in oat],
        "rh_pct": [float(x) for x in rh],
        "ghi": [float(x) for x in ghi],
        "source": "synthetic",
    }
