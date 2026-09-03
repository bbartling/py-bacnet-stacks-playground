"""Weather provider interfaces for residential DSM."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .residential.model import DEFAULT_EPW_NAME, find_denver_epw


class WeatherProvider(ABC):
    @abstractmethod
    def describe(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def epw_path(self) -> Path | None:
        raise NotImplementedError


class StaticEpwWeatherProvider(WeatherProvider):
    def __init__(self, epw: Path | str | None = None) -> None:
        self._epw = Path(epw).expanduser() if epw else find_denver_epw()

    def describe(self) -> dict[str, Any]:
        return {
            "provider": "StaticEpwWeatherProvider",
            "epw": str(self._epw) if self._epw else None,
            "exists": bool(self._epw and self._epw.is_file()),
        }

    def epw_path(self) -> Path | None:
        return self._epw if self._epw and self._epw.is_file() else None


class FixtureForecastWeatherProvider(WeatherProvider):
    """Load a deterministic forecast JSON fixture (not a live API)."""

    def __init__(self, fixture_path: Path | str) -> None:
        self.path = Path(fixture_path)
        self.payload = json.loads(self.path.read_text(encoding="utf-8"))

    def describe(self) -> dict[str, Any]:
        return {
            "provider": "FixtureForecastWeatherProvider",
            "fixture": str(self.path),
            "day": self.payload.get("day"),
            "intervals": len(self.payload.get("drybulb_c") or []),
            "claim": "ILLUSTRATIVE_FORECAST_FIXTURE",
        }

    def epw_path(self) -> Path | None:
        epw = self.payload.get("epw")
        if epw:
            path = Path(epw)
            if path.is_file():
                return path
        return find_denver_epw()

    def drybulb_c(self) -> list[float]:
        values = self.payload.get("drybulb_c")
        if not isinstance(values, list):
            raise ValueError("fixture missing drybulb_c list")
        return [float(v) for v in values]


def find_default_epw() -> Path | None:
    return find_denver_epw()


__all__ = [
    "DEFAULT_EPW_NAME",
    "FixtureForecastWeatherProvider",
    "StaticEpwWeatherProvider",
    "WeatherProvider",
    "find_default_epw",
]
