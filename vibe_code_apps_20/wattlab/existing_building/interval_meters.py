"""Interval (sub-hourly/hourly) meter loader with timezone and DST handling.

Expected CSV layout (header required; value columns optional but at least
one must be present)::

    timestamp,electric_kwh,electric_kw,gas_therms,quality
    2025-01-01T00:00:00,12.4,49.6,0.8,good

- ``timestamp`` — interval *start*, either timezone-naive local clock time
  (localized with proper DST handling: spring-forward gaps rejected as
  nonexistent, fall-back duplicates disambiguated by order) or ISO-8601
  with an explicit UTC offset.
- ``electric_kwh`` / ``gas_therms`` — consumption during the interval.
- ``electric_kw`` — average demand during the interval.
- ``quality`` — optional source quality flag; rows whose flag is not in
  ``GOOD_QUALITY_FLAGS`` keep their timestamps but have values masked.

The loader never invents data: missing intervals stay missing (reported in
coverage stats), duplicates are rejected unless exact copies, and cumulative
registers are only converted when explicitly requested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

TIMESTAMP_COLUMN = "timestamp"
VALUE_COLUMNS = ("electric_kwh", "electric_kw", "gas_therms")
QUALITY_COLUMN = "quality"

#: Quality flags treated as trustworthy; anything else is masked to NaN.
GOOD_QUALITY_FLAGS: frozenset[str] = frozenset({"good", "ok", "measured", ""})

#: Interval durations (minutes) accepted without an explicit override.
SUPPORTED_INTERVAL_MINUTES: tuple[int, ...] = (5, 15, 30, 60)


class IntervalLoadError(ValueError):
    """Raised when an interval CSV cannot be loaded safely."""


class CoverageStats(BaseModel):
    """Serializable coverage/quality summary for one interval dataset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    interval_minutes: int = Field(gt=0)
    timezone: str
    start: str
    end: str
    expected_intervals: int = Field(ge=0)
    present_intervals: int = Field(ge=0)
    missing_intervals: int = Field(ge=0)
    duplicate_rows_dropped: int = Field(ge=0)
    bad_quality_rows: int = Field(ge=0)
    coverage_fraction: float = Field(ge=0, le=1)
    columns: list[str]


@dataclass(frozen=True)
class IntervalDataset:
    """Loaded interval data plus its coverage statistics.

    ``frame`` is indexed by timezone-aware interval-start timestamps and is
    reindexed onto the full regular grid, so missing intervals appear as
    NaN rows rather than silently absent ones.
    """

    frame: pd.DataFrame
    stats: CoverageStats
    missing_timestamps: tuple[str, ...] = field(default=())

    @property
    def interval_minutes(self) -> int:
        return self.stats.interval_minutes

    def resample(self, minutes: int) -> pd.DataFrame:
        """Aggregate to a coarser interval (sum energy, mean demand).

        An output interval is NaN if *any* contributing input interval is
        missing, so resampling can never hide coverage holes.
        """
        if minutes % self.stats.interval_minutes != 0 or minutes <= 0:
            raise IntervalLoadError(
                f"cannot resample {self.stats.interval_minutes}-minute data "
                f"to {minutes} minutes: target must be a positive multiple"
            )
        if minutes == self.stats.interval_minutes:
            return self.frame.copy()
        rule = f"{minutes}min"
        pieces: dict[str, pd.Series] = {}
        for col in self.frame.columns:
            grouped = self.frame[col].resample(rule)
            if col == "electric_kw":
                agg = grouped.mean()
            else:
                agg = grouped.sum()
            agg[grouped.count() != grouped.size()] = float("nan")
            pieces[col] = agg
        return pd.DataFrame(pieces)

    def monthly_totals(self, column: str) -> dict[str, float]:
        """Complete-data monthly sums keyed by 'YYYY-MM' (multi-year safe)."""
        series = self.frame[column]
        out: dict[str, float] = {}
        for key, chunk in series.groupby(series.index.strftime("%Y-%m")):
            if chunk.isna().any():
                continue
            out[str(key)] = float(chunk.sum())
        return out


def _localize(timestamps: pd.Series, timezone: str) -> pd.DatetimeIndex:
    parsed = pd.to_datetime(timestamps, errors="raise", utc=False, format="mixed")
    if isinstance(parsed.dtype, pd.DatetimeTZDtype) or getattr(parsed.dt, "tz", None):
        return pd.DatetimeIndex(parsed).tz_convert(timezone)
    try:
        # DST fall-back repeats a local hour: "infer" assigns the first pass
        # DST-on and the second DST-off, which is correct for ordered meter
        # data. Spring-forward clock times do not exist and are hard errors.
        return pd.DatetimeIndex(parsed).tz_localize(
            timezone, ambiguous="infer", nonexistent="raise"
        )
    except Exception as exc:  # pandas raises several exception types here
        raise IntervalLoadError(
            f"could not localize naive timestamps to {timezone!r}: {exc}; "
            "provide explicit UTC offsets in the CSV if the local clock "
            "sequence is not resolvable"
        ) from exc


def _infer_interval_minutes(index: pd.DatetimeIndex) -> int:
    deltas = pd.Series(index).diff().dropna()
    if deltas.empty:
        raise IntervalLoadError("need at least 2 rows to infer the interval duration")
    minutes = int(deltas.mode().iloc[0].total_seconds() // 60)
    if minutes not in SUPPORTED_INTERVAL_MINUTES:
        raise IntervalLoadError(
            f"inferred interval of {minutes} minutes is not supported "
            f"{SUPPORTED_INTERVAL_MINUTES}; pass expected_interval_minutes "
            "to override"
        )
    return minutes


def convert_cumulative(series: pd.Series, *, allow_resets: bool = True) -> pd.Series:
    """Convert a cumulative register reading into per-interval consumption.

    The first interval is NaN (no prior reading). Negative steps are meter
    resets/rollovers: with ``allow_resets`` they become NaN (never negative
    consumption); otherwise they raise.
    """
    diffs = series.diff()
    negative = diffs < 0
    if negative.any():
        if not allow_resets:
            raise IntervalLoadError(
                f"cumulative register decreased at "
                f"{list(series.index[negative])[:3]}; refusing to convert"
            )
        diffs[negative] = float("nan")
    return diffs


def load_interval_csv(
    path: str | Path,
    *,
    timezone: str = "UTC",
    expected_interval_minutes: int | None = None,
    cumulative_columns: Iterable[str] = (),
) -> IntervalDataset:
    """Load and validate an interval meter CSV. See module docstring."""
    frame = pd.read_csv(path)
    if TIMESTAMP_COLUMN not in frame.columns:
        raise IntervalLoadError(f"CSV must have a {TIMESTAMP_COLUMN!r} column")
    value_cols = [c for c in VALUE_COLUMNS if c in frame.columns]
    if not value_cols:
        raise IntervalLoadError(
            f"CSV must have at least one of {VALUE_COLUMNS} (got {list(frame.columns)})"
        )
    unexpected = set(frame.columns) - {TIMESTAMP_COLUMN, QUALITY_COLUMN, *VALUE_COLUMNS}
    if unexpected:
        raise IntervalLoadError(f"unexpected columns: {sorted(unexpected)}")

    index = _localize(frame[TIMESTAMP_COLUMN], timezone)
    data = frame[value_cols].astype(float)
    data.index = index

    bad_quality_rows = 0
    if QUALITY_COLUMN in frame.columns:
        flags = frame[QUALITY_COLUMN].fillna("").astype(str).str.strip().str.lower()
        bad = ~flags.isin(GOOD_QUALITY_FLAGS)
        bad_quality_rows = int(bad.sum())
        data.loc[bad.to_numpy(), :] = float("nan")

    # Exact duplicate rows (same timestamp, same values) collapse to one;
    # conflicting duplicates are a data error we refuse to guess about.
    duplicate_rows_dropped = 0
    if data.index.has_duplicates:
        dup_mask = data.index.duplicated(keep=False)
        conflicting: list[str] = []
        for ts, chunk in data[dup_mask].groupby(level=0):
            if len(chunk.drop_duplicates()) > 1:
                conflicting.append(str(ts))
        if conflicting:
            raise IntervalLoadError(
                "conflicting duplicate timestamps (same time, different "
                f"values): {conflicting[:5]}"
            )
        before = len(data)
        data = data[~data.index.duplicated(keep="first")]
        duplicate_rows_dropped = before - len(data)

    data = data.sort_index()

    for col in cumulative_columns:
        if col not in data.columns:
            raise IntervalLoadError(f"cumulative column {col!r} not in CSV")
        data[col] = convert_cumulative(data[col])

    interval_minutes = expected_interval_minutes or _infer_interval_minutes(data.index)
    step = pd.Timedelta(minutes=interval_minutes)

    deltas = pd.Series(data.index).diff().dropna()
    non_multiple = deltas[
        (deltas.dt.total_seconds() % step.total_seconds() != 0)
        | (deltas <= pd.Timedelta(0))
    ]
    if not non_multiple.empty:
        raise IntervalLoadError(
            f"timestamp spacing must be positive multiples of "
            f"{interval_minutes} minutes; found deltas like "
            f"{non_multiple.iloc[0]}"
        )

    full_grid = pd.date_range(data.index[0], data.index[-1], freq=step)
    data = data.reindex(full_grid)
    # A row that exists but was fully masked for quality is still a coverage
    # hole: only rows with at least one real value count as present.
    present_mask = data.notna().any(axis=1)
    missing_index = full_grid[~present_mask.to_numpy()]

    stats = CoverageStats(
        interval_minutes=interval_minutes,
        timezone=timezone,
        start=str(full_grid[0]),
        end=str(full_grid[-1]),
        expected_intervals=len(full_grid),
        present_intervals=int(present_mask.sum()),
        missing_intervals=int((~present_mask).sum()),
        duplicate_rows_dropped=duplicate_rows_dropped,
        bad_quality_rows=bad_quality_rows,
        coverage_fraction=float(present_mask.sum()) / len(full_grid),
        columns=list(data.columns),
    )
    return IntervalDataset(
        frame=data,
        stats=stats,
        missing_timestamps=tuple(str(ts) for ts in missing_index[:100]),
    )
