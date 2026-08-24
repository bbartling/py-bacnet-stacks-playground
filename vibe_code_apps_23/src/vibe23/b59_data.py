"""Fail-closed Building 59 telemetry audit and measured-target helpers.

This module deliberately makes no whole-building or utility-bill claim.  The
published electrical comparison scope is the explicitly named office subtotal
in :data:`ELECTRICITY_COMPONENTS`; north-wing lighting is not measured.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

B59_TIMEZONE = "America/Los_Angeles"
B59_BINDING_SCHEMA = "vibe23.b59_point_bindings.v2"
ELECTRICITY_COMPONENTS = ("mels_S", "mels_N", "lig_S", "hvac_S", "hvac_N")
MISSING_NORTH_LIGHTING = "lig_N"


class B59DataError(ValueError):
    """Raised when raw telemetry cannot safely support a derived result."""


@dataclass(frozen=True)
class PointBindings:
    electricity_path: Path
    electricity_timestamp_column: str
    electricity_source_timezone: str
    electricity_time_basis_status: str
    electricity_components: tuple[str, ...]
    occupancy_path: Path
    occupancy_timestamp_column: str
    occupancy_source_timezone: str
    occupancy_time_basis_status: str
    occupancy_columns: tuple[str, ...]
    rtu_path: Path
    rtu_timestamp_column: str
    rtu_source_timezone: str
    rtu_time_basis_status: str
    rtu_columns: tuple[str, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise B59DataError(f"{label} keys must be exactly {sorted(expected)}; got {sorted(actual)}")


def _relative_csv(root: Path, raw: object, label: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise B59DataError(f"{label} must be a non-empty relative CSV path")
    candidate = (root / raw).resolve()
    if root.resolve() not in candidate.parents or candidate.suffix.lower() != ".csv":
        raise B59DataError(f"{label} must resolve under the raw root to a CSV")
    if not candidate.is_file():
        raise B59DataError(f"{label} does not exist: {candidate}")
    return candidate


def _columns(path: Path) -> set[str]:
    return set(pd.read_csv(path, nrows=0).columns)


def _section(
    root: Path,
    value: object,
    label: str,
    required_columns: tuple[str, ...] | None = None,
) -> tuple[Path, str, str, str, tuple[str, ...]]:
    if not isinstance(value, Mapping):
        raise B59DataError(f"{label} must be an object")
    _require_exact_keys(
        value,
        {"path", "timestamp_column", "source_timezone", "time_basis_status", "columns"},
        label,
    )
    path = _relative_csv(root, value["path"], f"{label}.path")
    timestamp = value["timestamp_column"]
    source_timezone = value["source_timezone"]
    time_basis_status = value["time_basis_status"]
    columns = value["columns"]
    if not isinstance(timestamp, str) or not timestamp:
        raise B59DataError(f"{label}.timestamp_column must be a non-empty string")
    if not isinstance(source_timezone, str) or not source_timezone:
        raise B59DataError(f"{label}.source_timezone must be a non-empty IANA timezone")
    try:
        pd.Timestamp("2020-01-01", tz=source_timezone)
    except Exception as exc:
        raise B59DataError(f"{label}.source_timezone is not recognized: {source_timezone!r}") from exc
    if not isinstance(time_basis_status, str) or not time_basis_status:
        raise B59DataError(f"{label}.time_basis_status must be a non-empty disclosure")
    if not isinstance(columns, list) or not columns or any(not isinstance(item, str) or not item for item in columns):
        raise B59DataError(f"{label}.columns must be a non-empty list of strings")
    chosen = tuple(columns)
    if len(set(chosen)) != len(chosen):
        raise B59DataError(f"{label}.columns contains duplicates")
    if required_columns is not None and chosen != required_columns:
        raise B59DataError(f"{label}.columns must be exactly {list(required_columns)}")
    available = _columns(path)
    absent = [column for column in (timestamp, *chosen) if column not in available]
    if absent:
        raise B59DataError(f"{label} references missing CSV columns: {absent}")
    return path, timestamp, source_timezone, time_basis_status, chosen


def validate_point_bindings(config: Mapping[str, Any], raw_root: Path) -> PointBindings:
    """Validate exact paths/columns before any telemetry transformation.

    The configuration is intentionally closed: it must name the schema,
    timezone and each of electricity, occupancy and RTU explicitly.  This
    prevents a renamed or guessed point from silently entering a target.
    """
    if not isinstance(config, Mapping):
        raise B59DataError("point bindings must be an object")
    _require_exact_keys(config, {"schema", "timezone", "electricity", "occupancy", "rtu"}, "point bindings")
    if config["schema"] != B59_BINDING_SCHEMA:
        raise B59DataError(f"schema must be {B59_BINDING_SCHEMA!r}")
    if config["timezone"] != B59_TIMEZONE:
        raise B59DataError(f"timezone must be {B59_TIMEZONE!r}")
    root = Path(raw_root).resolve()
    if not root.is_dir():
        raise B59DataError(f"raw root does not exist: {root}")
    ele_path, ele_timestamp, ele_timezone, ele_time_status, ele_columns = _section(
        root, config["electricity"], "electricity", ELECTRICITY_COMPONENTS
    )
    occ_path, occ_timestamp, occ_timezone, occ_time_status, occ_columns = _section(
        root, config["occupancy"], "occupancy"
    )
    rtu_path, rtu_timestamp, rtu_timezone, rtu_time_status, rtu_columns = _section(
        root, config["rtu"], "rtu"
    )
    return PointBindings(
        ele_path,
        ele_timestamp,
        ele_timezone,
        ele_time_status,
        ele_columns,
        occ_path,
        occ_timestamp,
        occ_timezone,
        occ_time_status,
        occ_columns,
        rtu_path,
        rtu_timestamp,
        rtu_timezone,
        rtu_time_status,
        rtu_columns,
    )


def _parse_timestamps(values: pd.Series, label: str, source_timezone: str) -> pd.DatetimeIndex:
    parsed = pd.to_datetime(values, errors="coerce")
    if parsed.isna().any():
        raise B59DataError(f"{label} has {int(parsed.isna().sum())} unparseable timestamps")
    index = pd.DatetimeIndex(parsed)
    if index.tz is not None:
        index = index.tz_convert(source_timezone)
    else:
        try:
            index = index.tz_localize(source_timezone, ambiguous="raise", nonexistent="raise")
        except (ValueError, TypeError) as exc:
            raise B59DataError(f"{label} has unresolved {source_timezone} DST timestamps") from exc
    return index


def _bound(value: str | pd.Timestamp | None, source_timezone: str, label: str) -> pd.Timestamp | None:
    if value is None:
        return None
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise B59DataError(f"{label} must include an explicit timezone")
    return stamp.tz_convert(source_timezone)


def _strict_frame(
    path: Path,
    timestamp_column: str,
    source_timezone: str,
    columns: tuple[str, ...],
    label: str,
    *,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=[timestamp_column, *columns])
    index = _parse_timestamps(frame.pop(timestamp_column), label, source_timezone)
    values = frame.apply(pd.to_numeric, errors="coerce")
    values.index = index
    values = values.sort_index()
    start_at = _bound(start, source_timezone, f"{label} start")
    end_at = _bound(end, source_timezone, f"{label} end")
    if start_at is not None:
        values = values.loc[values.index >= start_at]
    if end_at is not None:
        values = values.loc[values.index < end_at]
    if values.index.has_duplicates:
        raise B59DataError(f"{label} has duplicate timestamps in the selected window")
    if values.isna().any().any():
        raise B59DataError(f"{label} has {int(values.isna().sum().sum())} null/non-numeric values")
    if len(values) < 2:
        raise B59DataError(f"{label} needs at least two samples")
    return values


def _require_regular(index: pd.DatetimeIndex, interval: pd.Timedelta, label: str) -> None:
    deltas = index.to_series().diff().iloc[1:]
    bad = deltas != interval
    if bad.any():
        raise B59DataError(f"{label} has {int(bad.sum())} gaps/non-{interval} intervals")


def build_electricity_targets(
    bindings: PointBindings,
    *,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    aggregation_timezone: str = "UTC",
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Construct 15-minute office electrical targets and derived monthly records.

    The source values are treated as sampled kW.  Each regular 15-minute sample
    contributes ``kW * 0.25 h``.  Any null, duplicate, DST ambiguity or cadence
    departure fails closed; no interpolation or gap filling is performed.
    """
    values = _strict_frame(
        bindings.electricity_path,
        bindings.electricity_timestamp_column,
        bindings.electricity_source_timezone,
        bindings.electricity_components,
        "electricity",
        start=start,
        end=end,
    )
    _require_regular(values.index, pd.Timedelta(minutes=15), "electricity")
    target = values.copy()
    target["office_total_kw"] = target.loc[:, list(ELECTRICITY_COMPONENTS)].sum(axis=1)
    target["office_total_kwh"] = target["office_total_kw"] * 0.25
    monthly_basis = target.tz_convert(aggregation_timezone)
    monthly = pd.DataFrame(
        {
            "energy_kwh": monthly_basis["office_total_kwh"].resample("MS").sum(min_count=1),
            "peak_kw": monthly_basis["office_total_kw"].resample("MS").max(),
            "samples": monthly_basis["office_total_kw"].resample("MS").count(),
        }
    )
    for component in ELECTRICITY_COMPONENTS:
        monthly[f"{component}_kwh"] = (monthly_basis[component] * 0.25).resample("MS").sum(min_count=1)
    monthly["mels_bound_kwh"] = monthly["mels_S_kwh"] + monthly["mels_N_kwh"]
    monthly["lighting_bound_kwh"] = monthly["lig_S_kwh"]
    monthly["hvac_panels_bound_kwh"] = monthly["hvac_S_kwh"] + monthly["hvac_N_kwh"]
    expected_samples = monthly.index.days_in_month * 24 * 4
    monthly["expected_samples"] = expected_samples
    monthly["coverage_pass"] = monthly["samples"] == monthly["expected_samples"]
    negative_counts = {column: int((target[column] < 0).sum()) for column in ELECTRICITY_COMPONENTS}
    provenance = {
        "source_path": str(bindings.electricity_path),
        "source_sha256": sha256_file(bindings.electricity_path),
        "timestamp_column": bindings.electricity_timestamp_column,
        "source_timestamp_timezone": bindings.electricity_source_timezone,
        "source_time_basis_status": bindings.electricity_time_basis_status,
        "aggregation_timezone": aggregation_timezone,
        "selected_window": {
            "start": target.index[0].isoformat(),
            "end_exclusive": (target.index[-1] + pd.Timedelta(minutes=15)).isoformat(),
        },
        "source_unit": "kW",
        "interval_minutes": 15,
        "energy_method": "sampled kW * 0.25 h; no gap filling",
        "office_total_definition": "mels_S + mels_N + lig_S + hvac_S + hvac_N",
        "missing_end_uses": [MISSING_NORTH_LIGHTING],
        "negative_component_sample_counts": negative_counts,
        "negative_value_policy": "retained as published cleaned telemetry; no clipping or imputation",
        "monthly_coverage_pass": bool(monthly["coverage_pass"].all()),
        "scope_warning": "Office electrical subtotal only; not a whole-building meter or utility bill.",
    }
    return target, monthly, provenance


def telemetry_audit(
    path: Path,
    timestamp_column: str,
    value_columns: tuple[str, ...],
    *,
    source_timezone: str = "UTC",
) -> dict[str, Any]:
    """Return a non-mutating coverage/missingness summary without filling data."""
    frame = pd.read_csv(path, usecols=[timestamp_column, *value_columns])
    parsed = pd.to_datetime(frame[timestamp_column], errors="coerce")
    valid = parsed.dropna().sort_values()
    deltas = valid.diff().dropna()
    years = parsed.dt.year.value_counts(dropna=True).sort_index()
    return {
        "source_path": str(path),
        "source_sha256": sha256_file(path),
        "timestamp_column": timestamp_column,
        "timezone_semantics": source_timezone + " wall-clock as explicitly bound",
        "rows": int(len(frame)),
        "timestamp_parse_failures": int(parsed.isna().sum()),
        "duplicate_timestamps": int(parsed.duplicated().sum()),
        "year_rows": {str(int(year)): int(count) for year, count in years.items()},
        "missing_values": {column: int(frame[column].isna().sum()) for column in value_columns},
        "interval_counts": {str(interval): int(count) for interval, count in deltas.value_counts().head(20).items()},
        "regularity_status": "PASS" if len(deltas) and deltas.nunique() == 1 else "FAIL_CLOSED",
    }


def infer_schedule_summary(
    path: Path,
    timestamp_column: str,
    value_columns: tuple[str, ...],
    *,
    source_timezone: str = "UTC",
    active_threshold: float = 0.0,
) -> dict[str, Any]:
    """Summarize occupancy or RTU activity by weekday and 15-minute local clock bin."""
    values = _strict_frame(path, timestamp_column, source_timezone, value_columns, "schedule telemetry")
    # Schedule inference needs a regular series, but accepts either minute or
    # quarter-hour data.  It reports activity, never fabricates a schedule.
    deltas = values.index.to_series().diff().iloc[1:]
    if deltas.nunique() != 1 or deltas.iloc[0] not in {pd.Timedelta(minutes=1), pd.Timedelta(minutes=15)}:
        raise B59DataError("schedule telemetry has gaps or an unsupported cadence")
    local = values.index.tz_convert(B59_TIMEZONE)
    active = values.gt(active_threshold).mean(axis=1)
    bins = pd.DataFrame({"weekday": local.weekday, "quarter_hour": local.hour * 4 + local.minute // 15, "active_fraction": active.to_numpy()})
    grouped = bins.groupby(["weekday", "quarter_hour"], sort=True)["active_fraction"].mean()
    return {
        "source_path": str(path),
        "source_sha256": sha256_file(path),
        "timezone": B59_TIMEZONE,
        "active_threshold": active_threshold,
        "activity_by_weekday_quarter_hour": {f"{day}:{quarter}": float(value) for (day, quarter), value in grouped.items()},
    }
