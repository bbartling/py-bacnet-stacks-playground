from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

_TIMESTAMP_NAMES = ("timestamp", "datetime", "date_time", "time", "date")
_VALUE_HINT = re.compile(r"(power|kw|electric|energy|kwh|meter|demand)", re.I)


def iter_csv_files(root: Path):
    yield from sorted(path for path in root.rglob("*.csv") if path.is_file())


def infer_timestamp_column(frame: pd.DataFrame) -> str:
    normalized = {str(col).strip().lower(): str(col) for col in frame.columns}
    for candidate in _TIMESTAMP_NAMES:
        if candidate in normalized:
            return normalized[candidate]
    for column in list(frame.columns)[:5]:
        parsed = pd.to_datetime(frame[column], errors="coerce")
        if len(parsed) and parsed.notna().mean() >= 0.9:
            return str(column)
    raise ValueError("Could not infer a timestamp column; bind it explicitly")


def value_candidates(columns) -> list[str]:
    return [str(col) for col in columns if _VALUE_HINT.search(str(col))]


def build_inventory(root: Path) -> pd.DataFrame:
    rows: list[dict] = []
    for path in iter_csv_files(root):
        relative = path.relative_to(root)
        try:
            sample = pd.read_csv(path, nrows=50)
            try:
                timestamp = infer_timestamp_column(sample)
            except ValueError:
                timestamp = None
            rows.append({
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "columns": len(sample.columns),
                "timestamp_candidate": timestamp,
                "value_candidates": "|".join(value_candidates(sample.columns)),
                "column_names": "|".join(map(str, sample.columns)),
                "read_status": "OK",
            })
        except Exception as exc:
            rows.append({
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "columns": None,
                "timestamp_candidate": None,
                "value_candidates": "",
                "column_names": "",
                "read_status": f"ERROR:{type(exc).__name__}:{exc}",
            })
    return pd.DataFrame(rows)


def load_point_csv(path: Path, timestamp_column: str | None = None, value_column: str | None = None) -> pd.Series:
    frame = pd.read_csv(path)
    timestamp_column = timestamp_column or infer_timestamp_column(frame)
    if timestamp_column not in frame.columns:
        raise KeyError(f"Timestamp column {timestamp_column!r} not found")
    timestamps = pd.to_datetime(frame[timestamp_column], errors="coerce")
    if timestamps.isna().any():
        raise ValueError(f"Timestamp parsing failed for {int(timestamps.isna().sum())} rows")

    if value_column is None:
        numeric_candidates = []
        for column in frame.columns:
            if column == timestamp_column:
                continue
            numeric = pd.to_numeric(frame[column], errors="coerce")
            if numeric.notna().mean() >= 0.95:
                numeric_candidates.append(str(column))
        if len(numeric_candidates) != 1:
            raise ValueError(f"Value column is ambiguous; bind it explicitly. Candidates: {numeric_candidates}")
        value_column = numeric_candidates[0]

    values = pd.to_numeric(frame[value_column], errors="coerce")
    if values.isna().any():
        raise ValueError(f"Non-numeric/null values found in {value_column!r}")
    series = pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(timestamps), name=value_column).sort_index()
    if series.index.has_duplicates:
        raise ValueError("Duplicate timestamps found; resolve before aggregation")
    return series


def aggregate_power_kw(power_kw: pd.Series, rule: str, max_gap_factor: float = 4.0) -> pd.DataFrame:
    """Aggregate sampled kW using left-hold integration and measured-sample peak."""
    if len(power_kw) < 2:
        raise ValueError("At least two power samples are required")
    if not isinstance(power_kw.index, pd.DatetimeIndex):
        raise TypeError("power_kw must use a DatetimeIndex")

    power_kw = power_kw.sort_index().astype(float)
    deltas = power_kw.index.to_series().shift(-1) - power_kw.index.to_series()
    hours = deltas.iloc[:-1].dt.total_seconds() / 3600.0
    if (hours <= 0).any():
        raise ValueError("Timestamps must be strictly increasing")
    median_hours = float(np.median(hours.to_numpy()))
    if float(hours.max()) > median_hours * max_gap_factor:
        raise ValueError(f"Telemetry gap exceeds fail-closed threshold: max={hours.max():.3f}h median={median_hours:.3f}h")

    delta_hours = deltas.dt.total_seconds() / 3600.0
    delta_hours.iloc[-1] = median_hours
    interval_kwh = pd.Series(power_kw.to_numpy() * delta_hours.to_numpy(), index=power_kw.index)
    return pd.DataFrame({
        "energy_kwh": interval_kwh.resample(rule).sum(min_count=1),
        "peak_kw": power_kw.resample(rule).max(),
        "mean_kw": power_kw.resample(rule).mean(),
        "samples": power_kw.resample(rule).count(),
    }).dropna(how="all")
