"""Midnight 24-hour hourly forecast for the daily RL obs (office + field).

Office pretrain uses EPW replay as a *pretend* OpenWeatherMap one-shot:
same 24 floats the field sidecar will get from a real forecast API at 00:00.

This is not verified weather. Not BACnet. Not operational MPC.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np

FORECAST_HOURS = 24
PRETEND_OWM = "pretend_openweathermap_hourly_midnight"
EPW_REPLAY = "epw_midnight_replay_perfect_forecast"
OPEN_METEO_FORECAST = "open_meteo_forecast_owm_shaped"


@dataclass
class MidnightHourlyForecast:
    day: str
    temps_c: List[float]
    source: str
    fetched_at_local: str = "00:00"
    provider: str = PRETEND_OWM

    def features(self) -> tuple[float, float, float, float, float, float]:
        arr = np.asarray(self.temps_c, dtype=np.float64)
        if arr.size == 0:
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        morning = arr[:8]
        return (
            float(arr.mean()),
            float(arr.min()),
            float(arr.max()),
            float(morning.min()),
            float(np.sum(arr < 0.0)),
            float(np.sum(arr < -10.0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def hourly_drybulb_from_epw(epw: Path, day: date) -> List[float]:
    """Civil-day EPW dry-bulb (°C), hour order 1..24 (or as stored)."""
    temps: list[float] = []
    text = Path(epw).read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in text:
        if not line or line[0].isalpha() or line.startswith("!"):
            continue
        parts = line.split(",")
        if len(parts) < 7:
            continue
        try:
            mo, dy = int(parts[1]), int(parts[2])
            if mo == day.month and dy == day.day:
                temps.append(float(parts[6]))
        except ValueError:
            continue
        if len(temps) >= FORECAST_HOURS:
            break
    if len(temps) < FORECAST_HOURS:
        temps = (temps + [temps[-1] if temps else 0.0] * FORECAST_HOURS)[:FORECAST_HOURS]
    return temps[:FORECAST_HOURS]


def forecast_from_epw_replay(epw: Path, day: date | str) -> MidnightHourlyForecast:
    d = day if isinstance(day, date) else date.fromisoformat(str(day)[:10])
    temps = hourly_drybulb_from_epw(Path(epw), d)
    return MidnightHourlyForecast(
        day=d.isoformat(),
        temps_c=temps,
        source=EPW_REPLAY,
        provider=PRETEND_OWM,
        fetched_at_local="00:00",
    )


def forecast_from_hourly(day: str, temps_c: Sequence[float], *, source: str = PRETEND_OWM) -> MidnightHourlyForecast:
    arr = [float(x) for x in temps_c][:FORECAST_HOURS]
    if len(arr) < FORECAST_HOURS:
        arr = (arr + [arr[-1] if arr else 0.0] * FORECAST_HOURS)[:FORECAST_HOURS]
    return MidnightHourlyForecast(
        day=str(day)[:10],
        temps_c=arr,
        source=source,
        provider=PRETEND_OWM,
        fetched_at_local="00:00",
    )


def load_midnight_forecast(
    *,
    day: str,
    epw: Path | None = None,
    source: str = "epw_replay",
    hourly_override: Sequence[float] | None = None,
) -> MidnightHourlyForecast:
    """One call at midnight. Default office path = EPW replay (pretend OWM)."""
    if hourly_override is not None:
        return forecast_from_hourly(day, hourly_override, source=source)
    src = str(source).lower()
    if src in {"epw_replay", "pretend_owm", PRETEND_OWM, EPW_REPLAY}:
        if epw is None:
            raise ValueError("epw required for midnight replay forecast")
        return forecast_from_epw_replay(epw, day)
    raise ValueError(
        f"unsupported forecast source={source!r}; "
        "office pretrain uses epw_replay as pretend OpenWeatherMap midnight hourly"
    )
