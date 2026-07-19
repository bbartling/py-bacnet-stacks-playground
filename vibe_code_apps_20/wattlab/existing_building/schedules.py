"""Weather-responsive hourly availability schedules (Schedule:File builder).

Builds hourly 0/1 fan/HVAC availability series from fixed occupied windows
plus *weather-conditional* extensions, then writes an EnergyPlus
``Schedule:File`` CSV with provenance metadata (source hash, row count, tz).

The core honesty rule: weather extensions are applied only for the specific
hours whose outdoor air temperature actually crosses the configured hot/cold
thresholds — never as a year-long stretch of longer operating hours. Leap
years (8784 rows) and series that cross a calendar-year boundary are
supported because all extension arithmetic walks the contiguous hourly series
by index, not by calendar reconstruction.

Config shape::

    {
        "occupied": {
            "monday_friday": ["07:00", "17:00"],
            "saturday": ["08:00", "12:00"],   # optional; omit/None = closed
            "sunday": None,                    # closed
        },
        "weather_extensions": {
            "hot": {
                "outdoor_air_threshold_f": 88.0,
                "early_start_hours": 2,
                "late_stop_hours": 2,
                "allow_overnight": False,
            },
            "cold": {
                "outdoor_air_threshold_f": 15.0,
                "early_start_hours": 3,
                "late_stop_hours": 3,
                "allow_overnight": True,
            },
        },
    }

All strategies are conceptual screening surrogates for how an existing
building *might* be operated, not a calibrated sequence of operations.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

OatSeries = Sequence[tuple[datetime, float]]

STRATEGIES = (
    "normal_fixed",
    "hot_early_start",
    "cold_early_start",
    "hot_late_stop",
    "cold_late_stop",
    "continuous_above_cooling",
    "continuous_below_heating",
    "weekend_extreme",
    "overnight_extreme",
    "recovery_undersized",
    "manual_override",
    "optimal_start_approx",
)

_DAY_KEYS: dict[str, tuple[int, ...]] = {
    "monday_friday": (0, 1, 2, 3, 4),
    "saturday": (5,),
    "sunday": (6,),
}


def _parse_hhmm(value: str) -> int:
    parts = str(value).split(":")
    if len(parts) != 2:
        raise ValueError(f"Expected 'HH:MM' time, got {value!r}")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 24 and 0 <= minute <= 59):
        raise ValueError(f"Time out of range: {value!r}")
    return hour * 60 + minute


@dataclass(frozen=True)
class DailyWindow:
    """Occupied window in minutes-from-midnight; stop < start wraps overnight."""

    start_minute: int
    stop_minute: int

    def covers_hour(self, hour: int) -> bool:
        m = hour * 60
        if self.start_minute <= self.stop_minute:
            return self.start_minute <= m < self.stop_minute
        return m >= self.start_minute or m < self.stop_minute


@dataclass(frozen=True)
class WeatherExtension:
    """Hot or cold OAT-conditional extension of the occupied window."""

    mode: str  # "hot" | "cold"
    threshold_f: float
    early_start_hours: int = 0
    late_stop_hours: int = 0
    allow_overnight: bool = False

    def crosses(self, oat_f: float) -> bool:
        if self.mode == "hot":
            return oat_f >= self.threshold_f
        return oat_f <= self.threshold_f

    @classmethod
    def from_dict(cls, mode: str, d: Mapping[str, Any]) -> "WeatherExtension":
        return cls(
            mode=mode,
            threshold_f=float(d["outdoor_air_threshold_f"]),
            early_start_hours=int(d.get("early_start_hours", 0)),
            late_stop_hours=int(d.get("late_stop_hours", 0)),
            allow_overnight=bool(d.get("allow_overnight", False)),
        )


@dataclass(frozen=True)
class ScheduleConfig:
    """Parsed occupied windows (per weekday) + hot/cold weather extensions."""

    windows: tuple[DailyWindow | None, ...]  # indexed by weekday() 0-6
    hot: WeatherExtension | None = None
    cold: WeatherExtension | None = None

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ScheduleConfig":
        occupied = d.get("occupied") or {}
        windows: list[DailyWindow | None] = [None] * 7
        for key, weekdays in _DAY_KEYS.items():
            raw = occupied.get(key)
            if raw is None or raw == "closed":
                continue
            start, stop = raw
            window = DailyWindow(_parse_hhmm(start), _parse_hhmm(stop))
            for wd in weekdays:
                windows[wd] = window
        extensions = d.get("weather_extensions") or {}
        hot = cold = None
        if extensions.get("hot"):
            hot = WeatherExtension.from_dict("hot", extensions["hot"])
        if extensions.get("cold"):
            cold = WeatherExtension.from_dict("cold", extensions["cold"])
        return cls(windows=tuple(windows), hot=hot, cold=cold)


def _coerce_config(config: ScheduleConfig | Mapping[str, Any]) -> ScheduleConfig:
    if isinstance(config, ScheduleConfig):
        return config
    return ScheduleConfig.from_dict(config)


def _split_series(oat_series: OatSeries) -> tuple[list[datetime], list[float]]:
    if not oat_series:
        raise ValueError("oat_series must not be empty")
    hours = [t for t, _ in oat_series]
    oat = [float(v) for _, v in oat_series]
    step = timedelta(hours=1)
    for prev, cur in zip(hours, hours[1:]):
        if cur - prev != step:
            raise ValueError(
                "oat_series must be a contiguous hourly series "
                f"(gap between {prev.isoformat()} and {cur.isoformat()})"
            )
    return hours, oat


def build_base_series(
    hours: Sequence[datetime], config: ScheduleConfig | Mapping[str, Any]
) -> list[int]:
    """Fixed occupied-window 0/1 series with no weather extensions."""
    cfg = _coerce_config(config)
    out: list[int] = []
    for t in hours:
        window = cfg.windows[t.weekday()]
        out.append(1 if window is not None and window.covers_hour(t.hour) else 0)
    return out


def _segment_starts(base: Sequence[int]) -> list[int]:
    return [i for i, v in enumerate(base) if v and (i == 0 or not base[i - 1])]


def _segment_stops(base: Sequence[int]) -> list[int]:
    last = len(base) - 1
    return [i for i, v in enumerate(base) if v and (i == last or not base[i + 1])]


def _require(ext: WeatherExtension | None, strategy: str, mode: str) -> WeatherExtension:
    if ext is None:
        raise ValueError(
            f"Strategy {strategy!r} requires weather_extensions.{mode} in the config"
        )
    return ext


def _apply_early_start(
    values: list[int],
    base: Sequence[int],
    hours: Sequence[datetime],
    oat: Sequence[float],
    ext: WeatherExtension,
    *,
    lead: int | None = None,
    conditional: bool = True,
) -> None:
    lead_hours = ext.early_start_hours if lead is None else lead
    for i in _segment_starts(base):
        for k in range(1, lead_hours + 1):
            j = i - k
            if j < 0:
                break
            if not ext.allow_overnight and hours[j].date() != hours[i].date():
                break
            if not conditional or ext.crosses(oat[j]):
                values[j] = 1


def _apply_late_stop(
    values: list[int],
    base: Sequence[int],
    hours: Sequence[datetime],
    oat: Sequence[float],
    ext: WeatherExtension,
    *,
    lag: int | None = None,
    conditional: bool = True,
) -> None:
    lag_hours = ext.late_stop_hours if lag is None else lag
    last = len(values) - 1
    for i in _segment_stops(base):
        for k in range(1, lag_hours + 1):
            j = i + k
            if j > last:
                break
            if not ext.allow_overnight and hours[j].date() != hours[i].date():
                break
            if not conditional or ext.crosses(oat[j]):
                values[j] = 1


def _apply_optimal_start(
    values: list[int],
    base: Sequence[int],
    hours: Sequence[datetime],
    oat: Sequence[float],
    ext: WeatherExtension,
    recovery_rate_f_per_hour: float,
) -> None:
    for i in _segment_starts(base):
        if ext.mode == "hot":
            delta = oat[i] - ext.threshold_f
        else:
            delta = ext.threshold_f - oat[i]
        if delta <= 0:
            continue
        lead = min(
            ext.early_start_hours,
            max(1, math.ceil(delta / recovery_rate_f_per_hour)),
        )
        for k in range(1, lead + 1):
            j = i - k
            if j < 0:
                break
            if not ext.allow_overnight and hours[j].date() != hours[i].date():
                break
            values[j] = 1


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def build_strategy_series(
    strategy: str,
    oat_series: OatSeries,
    config: ScheduleConfig | Mapping[str, Any],
    *,
    manual_overrides: Sequence[Mapping[str, Any]] | None = None,
    recovery_multiplier: float = 2.0,
    recovery_rate_f_per_hour: float = 5.0,
) -> list[int]:
    """Hourly 0/1 availability for one named operating-hypothesis strategy.

    Every strategy is base-occupancy plus *added* hours; extension hours are
    only switched on when the hour's own OAT crosses the relevant threshold
    (except ``manual_override`` windows and the computed ``optimal_start``
    lead, which are unconditional by definition).
    """
    if strategy not in STRATEGIES:
        raise ValueError(
            f"Unknown schedule strategy {strategy!r}; expected one of {STRATEGIES}"
        )
    cfg = _coerce_config(config)
    hours, oat = _split_series(oat_series)
    base = build_base_series(hours, cfg)
    values = list(base)

    if strategy == "normal_fixed":
        pass
    elif strategy == "hot_early_start":
        _apply_early_start(values, base, hours, oat, _require(cfg.hot, strategy, "hot"))
    elif strategy == "cold_early_start":
        _apply_early_start(values, base, hours, oat, _require(cfg.cold, strategy, "cold"))
    elif strategy == "hot_late_stop":
        _apply_late_stop(values, base, hours, oat, _require(cfg.hot, strategy, "hot"))
    elif strategy == "cold_late_stop":
        _apply_late_stop(values, base, hours, oat, _require(cfg.cold, strategy, "cold"))
    elif strategy == "continuous_above_cooling":
        hot = _require(cfg.hot, strategy, "hot")
        for idx, v in enumerate(oat):
            if hot.crosses(v):
                values[idx] = 1
    elif strategy == "continuous_below_heating":
        cold = _require(cfg.cold, strategy, "cold")
        for idx, v in enumerate(oat):
            if cold.crosses(v):
                values[idx] = 1
    elif strategy == "weekend_extreme":
        for idx, t in enumerate(hours):
            if base[idx] or t.weekday() < 5:
                continue
            hot_hit = cfg.hot is not None and cfg.hot.crosses(oat[idx])
            cold_hit = cfg.cold is not None and cfg.cold.crosses(oat[idx])
            if hot_hit or cold_hit:
                values[idx] = 1
    elif strategy == "overnight_extreme":
        # Unoccupied hours run only when extreme AND that mode permits
        # overnight operation (allow_overnight).
        for idx in range(len(hours)):
            if base[idx]:
                continue
            hot_hit = (
                cfg.hot is not None
                and cfg.hot.allow_overnight
                and cfg.hot.crosses(oat[idx])
            )
            cold_hit = (
                cfg.cold is not None
                and cfg.cold.allow_overnight
                and cfg.cold.crosses(oat[idx])
            )
            if hot_hit or cold_hit:
                values[idx] = 1
    elif strategy == "recovery_undersized":
        # Undersized plant needs a longer conditional recovery lead.
        for ext in (cfg.hot, cfg.cold):
            if ext is None or ext.early_start_hours <= 0:
                continue
            lead = math.ceil(ext.early_start_hours * recovery_multiplier)
            _apply_early_start(values, base, hours, oat, ext, lead=lead)
    elif strategy == "manual_override":
        windows = [
            (_as_datetime(o["start"]), _as_datetime(o["end"]))
            for o in (manual_overrides or [])
        ]
        for idx, t in enumerate(hours):
            if any(start <= t < end for start, end in windows):
                values[idx] = 1
    elif strategy == "optimal_start_approx":
        for ext in (cfg.hot, cfg.cold):
            if ext is None or ext.early_start_hours <= 0:
                continue
            _apply_optimal_start(
                values, base, hours, oat, ext, recovery_rate_f_per_hour
            )

    return values


def write_schedule_file(
    dest: Path,
    hours: Sequence[datetime],
    values: Sequence[int],
    *,
    schedule_name: str,
    strategy: str,
) -> dict:
    """Write a Schedule:File CSV (datetime,availability) + provenance metadata."""
    if len(hours) != len(values):
        raise ValueError("hours and values must be the same length")
    dest = Path(dest)
    lines = ["datetime,availability"]
    lines.extend(
        f"{t.strftime('%Y-%m-%d %H:%M')},{int(v)}" for t, v in zip(hours, values)
    )
    csv_text = "\n".join(lines) + "\n"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(csv_text, encoding="utf-8")

    tzinfo = hours[0].tzinfo
    rows = len(values)
    return {
        "schedule_name": schedule_name,
        "strategy": strategy,
        "csv": str(dest),
        "source_sha256": hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
        "rows": rows,
        "hours_on": int(sum(int(v) for v in values)),
        "tz": str(tzinfo) if tzinfo is not None else "local_standard_assumed",
        "leap_year": any(t.month == 2 and t.day == 29 for t in hours),
        "full_year": rows in (8760, 8784),
        "first_hour": hours[0].isoformat(),
        "last_hour": hours[-1].isoformat(),
        # Schedule:File wiring hints for the IDF patch.
        "column_number": 2,
        "rows_to_skip": 1,
        "minutes_per_item": 60,
    }


def build_weather_schedule(
    strategy: str,
    oat_series: OatSeries,
    config: ScheduleConfig | Mapping[str, Any],
    dest: Path,
    *,
    schedule_name: str | None = None,
    manual_overrides: Sequence[Mapping[str, Any]] | None = None,
    recovery_multiplier: float = 2.0,
    recovery_rate_f_per_hour: float = 5.0,
) -> dict:
    """Build one strategy's series, write the Schedule:File CSV, return metadata."""
    values = build_strategy_series(
        strategy,
        oat_series,
        config,
        manual_overrides=manual_overrides,
        recovery_multiplier=recovery_multiplier,
        recovery_rate_f_per_hour=recovery_rate_f_per_hour,
    )
    hours = [t for t, _ in oat_series]
    name = schedule_name or f"WattLab Avail {strategy}"
    meta = write_schedule_file(
        Path(dest), hours, values, schedule_name=name, strategy=strategy
    )
    meta["flags"] = [
        "conceptual_screening_schedule",
        "weather_conditional_extension_hours_only",
    ]
    return meta
