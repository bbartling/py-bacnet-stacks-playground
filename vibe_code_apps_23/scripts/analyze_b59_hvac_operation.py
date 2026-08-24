#!/usr/bin/env python3
"""Extract reproducible, source-clock HVAC operating evidence from B59 telemetry.

The public files are already cleaned/imputed and contain timezone-naive timestamps.
Consequently this program reports evidence in the recorded source clock and never
silently promotes inferred schedules or sensor values to calibrated parameters.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCHEMA = "vibe23.b59_hvac_operating_evidence.v1"
SOURCE_CLOCK = "timezone-naive recorded source clock"
TIME_BASIS_STATUS = (
    "The publisher files do not embed a timezone. Hour-of-day results use the recorded source clock; "
    "conversion to America/Los_Angeles is prohibited until the BAS time basis and DST convention are confirmed."
)
PANDEMIC_CUTOFF = pd.Timestamp("2020-03-18 00:00:00")
REPORTED_HEATING_CHANGE_CUTOFF = pd.Timestamp("2019-04-01 00:00:00")


@dataclass(frozen=True)
class FileSpec:
    filename: str
    role: str
    unit: str
    nominal_minutes: int
    activity_threshold: float | None = None
    sample_every: int = 60


SPECS = (
    FileSpec("rtu_fan_spd.csv", "rtu_fan_speed_feedback", "%", 1, 5.0),
    FileSpec("rtu_sa_t_sp.csv", "rtu_supply_air_temperature_setpoint", "degF", 1),
    FileSpec("rtu_sa_t.csv", "rtu_supply_air_temperature", "degF", 1),
    FileSpec("rtu_sa_fr.csv", "rtu_supply_air_flow", "cfm", 1, 100.0),
    FileSpec("rtu_sa_p_sp.csv", "rtu_supply_static_pressure_setpoint", "publisher-labeled psi", 1),
    FileSpec("rtu_oa_fr.csv", "rtu_outdoor_air_flow", "cfm", 1, 100.0),
    FileSpec("rtu_oa_damper.csv", "rtu_outdoor_air_damper_position", "%", 1, 5.0),
    FileSpec("rtu_econ_sp.csv", "rtu_economizer_setpoint", "degF", 1),
    FileSpec("zone_temp_exterior.csv", "exterior_zone_air_temperature", "degF", 1),
    FileSpec("zone_temp_sp_c.csv", "zone_cooling_temperature_setpoint", "degF", 5),
    FileSpec("zone_temp_sp_h.csv", "zone_heating_temperature_setpoint", "degF", 5),
    FileSpec("uft_fan_spd.csv", "uft_fan_speed", "%", 1, 20.5),
    FileSpec("uft_hw_valve.csv", "uft_heating_water_valve_position", "%", 1, 5.0),
    FileSpec("occ.csv", "partial_south_half_occupant_count", "persons", 1, 0.0),
)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def _finite(values: pd.Series | np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return array[np.isfinite(array)]


@dataclass
class OnlineStats:
    count: int = 0
    total: float = 0.0
    total_sq: float = 0.0
    minimum: float = math.inf
    maximum: float = -math.inf
    zero_count: int = 0
    activity_count: int = 0
    samples: list[np.ndarray] = field(default_factory=list)

    def update(
        self,
        values: pd.Series | np.ndarray,
        *,
        threshold: float | None = None,
        sample_mask: np.ndarray | None = None,
    ) -> None:
        array = np.asarray(values, dtype=float)
        valid = np.isfinite(array)
        finite = array[valid]
        if finite.size == 0:
            return
        self.count += int(finite.size)
        self.total += float(finite.sum())
        self.total_sq += float(np.square(finite).sum())
        self.minimum = min(self.minimum, float(finite.min()))
        self.maximum = max(self.maximum, float(finite.max()))
        self.zero_count += int(np.count_nonzero(np.isclose(finite, 0.0, atol=1e-9)))
        if threshold is not None:
            self.activity_count += int(np.count_nonzero(finite > threshold))
        sampled = array if sample_mask is None else array[sample_mask]
        sampled = sampled[np.isfinite(sampled)]
        if sampled.size:
            self.samples.append(sampled.astype(np.float32, copy=False))

    def result(self, threshold: float | None = None) -> dict[str, Any]:
        if not self.count:
            return {"valid_count": 0}
        variance = max(self.total_sq / self.count - (self.total / self.count) ** 2, 0.0)
        sample = np.concatenate(self.samples) if self.samples else np.array([], dtype=float)
        result: dict[str, Any] = {
            "valid_count": self.count,
            "min": round(self.minimum, 4),
            "p05_sampled": _rounded_quantile(sample, 0.05),
            "p25_sampled": _rounded_quantile(sample, 0.25),
            "median_sampled": _rounded_quantile(sample, 0.50),
            "p75_sampled": _rounded_quantile(sample, 0.75),
            "p95_sampled": _rounded_quantile(sample, 0.95),
            "max": round(self.maximum, 4),
            "mean": round(self.total / self.count, 4),
            "std": round(math.sqrt(variance), 4),
            "zero_fraction": round(self.zero_count / self.count, 6),
            "percentile_method": "deterministic row-stride sample",
            "percentile_sample_count": int(sample.size),
        }
        if threshold is not None:
            result["activity_threshold"] = threshold
            result["fraction_above_activity_threshold"] = round(self.activity_count / self.count, 6)
        return result


def _rounded_quantile(values: np.ndarray, quantile: float) -> float | None:
    if values.size == 0:
        return None
    return round(float(np.quantile(values, quantile)), 4)


def regime_labels(timestamps: pd.Series) -> np.ndarray:
    values = timestamps.to_numpy(dtype="datetime64[ns]")
    result = np.full(len(values), "2018", dtype=object)
    heating_change = np.datetime64(REPORTED_HEATING_CHANGE_CUTOFF.to_datetime64())
    pandemic = np.datetime64(PANDEMIC_CUTOFF.to_datetime64())
    result[(values >= np.datetime64("2019-01-01")) & (values < heating_change)] = (
        "2019_pre_reported_march_change"
    )
    result[(values >= heating_change) & (values < np.datetime64("2020-01-01"))] = (
        "2019_post_reported_march_change"
    )
    result[(values >= np.datetime64("2020-01-01")) & (values < pandemic)] = (
        "2020_pre_shelter_in_place"
    )
    result[values >= pandemic] = "2020_shelter_in_place"
    return result


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if column != "date" and not column.startswith("Unnamed:")]


def analyze_file(path: Path, spec: FileSpec, *, chunksize: int) -> dict[str, Any]:
    overall: dict[str, OnlineStats] = {}
    regimes: dict[str, OnlineStats] = {}
    hours: dict[int, OnlineStats] = {hour: OnlineStats() for hour in range(24)}
    weekdays = OnlineStats()
    weekends = OnlineStats()
    rows = 0
    valid_timestamp_rows = 0
    duplicate_timestamps = 0
    nonmonotonic_timestamps = 0
    irregular_intervals = 0
    material_gaps = 0
    first_timestamp: pd.Timestamp | None = None
    last_timestamp: pd.Timestamp | None = None
    previous_timestamp: pd.Timestamp | None = None
    first_nonzero_timestamp: pd.Timestamp | None = None
    columns: list[str] | None = None
    row_offset = 0

    for chunk in pd.read_csv(path, chunksize=chunksize, low_memory=False):
        rows += len(chunk)
        if "date" not in chunk:
            raise ValueError(f"{path.name} lacks required date column")
        timestamps = pd.to_datetime(chunk["date"], errors="coerce")
        good_time = timestamps.notna()
        valid_timestamp_rows += int(good_time.sum())
        chunk = chunk.loc[good_time].copy()
        timestamps = timestamps.loc[good_time]
        if chunk.empty:
            continue
        if columns is None:
            columns = _numeric_columns(chunk)
            if not columns:
                raise ValueError(f"{path.name} has no measurement columns")
            overall = {column: OnlineStats() for column in columns}
        elif columns != _numeric_columns(chunk):
            raise ValueError(f"{path.name} columns changed while streaming")

        current_first = timestamps.iloc[0]
        current_last = timestamps.iloc[-1]
        first_timestamp = current_first if first_timestamp is None else min(first_timestamp, current_first)
        last_timestamp = current_last if last_timestamp is None else max(last_timestamp, current_last)
        diffs = timestamps.diff()
        if previous_timestamp is not None:
            diffs.iloc[0] = current_first - previous_timestamp
        duplicate_timestamps += int((diffs == pd.Timedelta(0)).sum())
        nonmonotonic_timestamps += int((diffs < pd.Timedelta(0)).sum())
        expected = pd.Timedelta(minutes=spec.nominal_minutes)
        irregular_intervals += int(((diffs.notna()) & (diffs != expected)).sum())
        material_gaps += int((diffs > expected * 1.5).sum())
        previous_timestamp = current_last

        numeric = chunk[columns].apply(pd.to_numeric, errors="coerce")
        all_values = numeric.to_numpy(dtype=float)
        nonzero_rows = np.any(np.isfinite(all_values) & (np.abs(all_values) > 1e-9), axis=1)
        if first_nonzero_timestamp is None and nonzero_rows.any():
            first_nonzero_timestamp = timestamps.iloc[int(np.flatnonzero(nonzero_rows)[0])]

        sample_mask = ((np.arange(len(chunk)) + row_offset) % max(spec.sample_every, 1)) == 0
        labels = regime_labels(timestamps)
        hour_values = timestamps.dt.hour.to_numpy()
        weekday_mask = timestamps.dt.dayofweek.to_numpy() < 5
        for column in columns:
            values = numeric[column].to_numpy(dtype=float)
            overall[column].update(values, threshold=spec.activity_threshold, sample_mask=sample_mask)
            for regime in np.unique(labels):
                mask = labels == regime
                regimes.setdefault(str(regime), OnlineStats()).update(
                    values[mask], threshold=spec.activity_threshold, sample_mask=sample_mask[mask]
                )
            for hour in range(24):
                mask = hour_values == hour
                hours[hour].update(
                    values[mask],
                    threshold=spec.activity_threshold,
                    sample_mask=sample_mask[mask],
                )
            weekdays.update(
                values[weekday_mask],
                threshold=spec.activity_threshold,
                sample_mask=sample_mask[weekday_mask],
            )
            weekends.update(
                values[~weekday_mask],
                threshold=spec.activity_threshold,
                sample_mask=sample_mask[~weekday_mask],
            )
        row_offset += len(chunk)

    if columns is None:
        raise ValueError(f"{path.name} has no readable rows")
    return {
        "role": spec.role,
        "unit": spec.unit,
        "source_clock": SOURCE_CLOCK,
        "rows": rows,
        "valid_timestamp_rows": valid_timestamp_rows,
        "first_timestamp": first_timestamp.isoformat() if first_timestamp is not None else None,
        "last_timestamp": last_timestamp.isoformat() if last_timestamp is not None else None,
        "first_nonzero_timestamp": first_nonzero_timestamp.isoformat() if first_nonzero_timestamp is not None else None,
        "nominal_interval_minutes": spec.nominal_minutes,
        "duplicate_timestamps": duplicate_timestamps,
        "nonmonotonic_timestamps": nonmonotonic_timestamps,
        "irregular_intervals": irregular_intervals,
        "material_gaps": material_gaps,
        "point_count": len(columns),
        "points": {column: overall[column].result(spec.activity_threshold) for column in columns},
        "aggregate_by_regime": {
            regime: stats.result(spec.activity_threshold) for regime, stats in sorted(regimes.items())
        },
        "aggregate_by_source_clock_hour": {
            f"{hour:02d}": hours[hour].result(spec.activity_threshold) for hour in range(24)
        },
        "aggregate_weekday": weekdays.result(spec.activity_threshold),
        "aggregate_weekend": weekends.result(spec.activity_threshold),
    }


def _load_indexed_numeric(path: Path, columns: list[str]) -> pd.DataFrame:
    """Load selected columns and preserve only exact, unique source timestamps."""
    frame = pd.read_csv(path, usecols=["date", *columns], low_memory=False)
    timestamps = pd.to_datetime(frame.pop("date"), errors="coerce")
    if timestamps.isna().any():
        raise ValueError(f"{path.name} has {int(timestamps.isna().sum())} invalid timestamps")
    values = frame.apply(pd.to_numeric, errors="coerce")
    values.index = pd.DatetimeIndex(timestamps)
    ambiguous = values.index.duplicated(keep=False)
    values = values.loc[~ambiguous]
    values.attrs["ambiguous_duplicate_rows_excluded"] = int(ambiguous.sum())
    return values.sort_index()


def _aligned_numeric_frames(
    left_path: Path,
    right_path: Path,
    left_columns: list[str],
    right_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Inner-align two histories without interpolation, resampling, or clock conversion."""
    left = _load_indexed_numeric(left_path, left_columns)
    right = _load_indexed_numeric(right_path, right_columns)
    common = left.index.intersection(right.index, sort=True)
    if common.empty:
        raise ValueError(f"paired histories have no exact timestamp overlap: {left_path.name}, {right_path.name}")
    return left.loc[common], right.loc[common]


def analyze_sat_tracking(raw_root: Path, chunksize: int) -> dict[str, Any]:
    del chunksize  # Pairing uses an exact timestamp intersection, not row position.
    actual_path = raw_root / "rtu_sa_t.csv"
    setpoint_path = raw_root / "rtu_sa_t_sp.csv"
    actual_columns = [f"rtu_{rtu:03d}_sa_temp" for rtu in range(1, 5)]
    setpoint_columns = [f"rtu_{rtu:03d}_sat_sp_tn" for rtu in range(1, 5)]
    actual, setpoint = _aligned_numeric_frames(actual_path, setpoint_path, actual_columns, setpoint_columns)
    aggregate = OnlineStats()
    per_rtu = {rtu: OnlineStats() for rtu in range(1, 5)}
    within_two = 0
    paired_count = 0
    for rtu in range(1, 5):
        actual_values = actual[f"rtu_{rtu:03d}_sa_temp"].to_numpy(float)
        sp_values = setpoint[f"rtu_{rtu:03d}_sat_sp_tn"].to_numpy(float)
        error = actual_values - sp_values
        valid = np.isfinite(error) & (sp_values > 30) & (sp_values < 100)
        finite_error = error[valid]
        sample_mask = np.arange(len(finite_error)) % 60 == 0
        aggregate.update(finite_error, sample_mask=sample_mask)
        per_rtu[rtu].update(finite_error, sample_mask=sample_mask)
        paired_count += int(valid.sum())
        within_two += int(np.count_nonzero(np.abs(finite_error) <= 2.0))
    return {
        "definition": "measured supply-air temperature minus recorded supply-air temperature setpoint",
        "unit": "delta_degF",
        "paired_valid_count": paired_count,
        "fraction_within_2F": round(within_two / paired_count, 6) if paired_count else None,
        "aggregate_error": aggregate.result(),
        "per_rtu_error": {f"RTU-{rtu}": per_rtu[rtu].result() for rtu in per_rtu},
    }


def _zone_name(column: str, suffix: str) -> str | None:
    if not column.startswith("zone_") or not column.endswith(suffix):
        return None
    return column[: -len(suffix)]


def analyze_zone_deadbands(raw_root: Path, chunksize: int) -> dict[str, Any]:
    del chunksize  # Pairing uses an exact timestamp intersection, not row position.
    cooling_path = raw_root / "zone_temp_sp_c.csv"
    heating_path = raw_root / "zone_temp_sp_h.csv"
    cooling_columns = _numeric_columns(pd.read_csv(cooling_path, nrows=0))
    heating_columns = _numeric_columns(pd.read_csv(heating_path, nrows=0))
    cooling_map = {
        zone: column
        for column in cooling_columns
        if (zone := _zone_name(column, "_cooling_sp")) is not None
    }
    heating_map = {
        zone: column
        for column in heating_columns
        if (zone := _zone_name(column, "_heating_sp")) is not None
    }
    common_zones = set(cooling_map) & set(heating_map)
    cooling, heating = _aligned_numeric_frames(
        cooling_path,
        heating_path,
        [cooling_map[zone] for zone in sorted(common_zones)],
        [heating_map[zone] for zone in sorted(common_zones)],
    )
    aggregate = OnlineStats()
    per_zone: dict[str, OnlineStats] = {}
    invalid_zero_or_implausible = 0
    nonpositive_deadband = 0
    paired_raw = 0
    for zone in sorted(common_zones):
        cool = cooling[cooling_map[zone]].to_numpy(float)
        heat = heating[heating_map[zone]].to_numpy(float)
        finite = np.isfinite(cool) & np.isfinite(heat)
        paired_raw += int(finite.sum())
        plausible = finite & (cool >= 50) & (cool <= 90) & (heat >= 45) & (heat <= 85)
        invalid_zero_or_implausible += int(np.count_nonzero(finite & ~plausible))
        deadband = cool - heat
        nonpositive_deadband += int(np.count_nonzero(plausible & (deadband <= 0)))
        valid = plausible & (deadband > 0)
        finite_deadband = deadband[valid]
        sample_mask = np.arange(len(finite_deadband)) % 60 == 0
        aggregate.update(finite_deadband, sample_mask=sample_mask)
        per_zone.setdefault(zone, OnlineStats()).update(finite_deadband, sample_mask=sample_mask)
    return {
        "definition": "recorded cooling setpoint minus recorded heating setpoint",
        "unit": "delta_degF",
        "paired_raw_count": paired_raw,
        "invalid_zero_or_implausible_excluded": invalid_zero_or_implausible,
        "nonpositive_deadband_excluded": nonpositive_deadband,
        "common_zone_count": len(common_zones),
        "valid_deadband": aggregate.result(),
        "per_zone_deadband": {zone: stats.result() for zone, stats in sorted(per_zone.items())},
    }


def analyze_oa_fraction(raw_root: Path, chunksize: int) -> dict[str, Any]:
    del chunksize  # Pairing uses an exact timestamp intersection, not row position.
    oa_path = raw_root / "rtu_oa_fr.csv"
    sa_path = raw_root / "rtu_sa_fr.csv"
    oa_columns = [f"rtu_{rtu:03d}_oa_flow_tn" for rtu in range(1, 5)]
    sa_columns = [f"rtu_{rtu:03d}_fltrd_sa_flow_tn" for rtu in range(1, 5)]
    oa, sa = _aligned_numeric_frames(oa_path, sa_path, oa_columns, sa_columns)
    aggregate = OnlineStats()
    per_rtu = {rtu: OnlineStats() for rtu in range(1, 5)}
    zero_or_unavailable = 0
    invalid_ratio = 0
    candidate_count = 0
    for rtu in range(1, 5):
        oa_values = oa[f"rtu_{rtu:03d}_oa_flow_tn"].to_numpy(float)
        sa_values = sa[f"rtu_{rtu:03d}_fltrd_sa_flow_tn"].to_numpy(float)
        finite = np.isfinite(oa_values) & np.isfinite(sa_values) & (sa_values > 100)
        candidate_count += int(finite.sum())
        available = finite & (oa_values > 100)
        zero_or_unavailable += int(np.count_nonzero(finite & ~available))
        ratio = oa_values / np.where(sa_values == 0, np.nan, sa_values)
        plausible = available & (ratio >= 0) & (ratio <= 1.2)
        invalid_ratio += int(np.count_nonzero(available & ~plausible))
        finite_ratio = ratio[plausible]
        sample_mask = np.arange(len(finite_ratio)) % 60 == 0
        aggregate.update(finite_ratio, sample_mask=sample_mask)
        per_rtu[rtu].update(finite_ratio, sample_mask=sample_mask)
    return {
        "definition": "recorded outdoor-air flow divided by recorded supply-air flow",
        "claim_boundary": (
            "Rows with outdoor-air flow <=100 cfm are treated as unavailable/zero, not proof of zero ventilation; "
            "publisher metadata limits useful OA-flow availability to Apr-Dec 2020."
        ),
        "candidate_count_with_sa_above_100_cfm": candidate_count,
        "oa_zero_or_unavailable_count": zero_or_unavailable,
        "invalid_ratio_excluded": invalid_ratio,
        "aggregate_ratio": aggregate.result(),
        "per_rtu_ratio": {f"RTU-{rtu}": per_rtu[rtu].result() for rtu in per_rtu},
    }


def _compact_point_table(section: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "point": point,
            "median": stats.get("median_sampled"),
            "p05": stats.get("p05_sampled"),
            "p95": stats.get("p95_sampled"),
            "mean": stats.get("mean"),
            "active_fraction": stats.get("fraction_above_activity_threshold"),
        }
        for point, stats in section["points"].items()
    ]


def build_evidence(raw_root: Path, *, chunksize: int = 50_000) -> dict[str, Any]:
    missing = [spec.filename for spec in SPECS if not (raw_root / spec.filename).is_file()]
    if missing:
        raise FileNotFoundError(f"missing required B59 telemetry files: {', '.join(missing)}")

    files: dict[str, Any] = {}
    analysis: dict[str, Any] = {}
    for spec in SPECS:
        path = raw_root / spec.filename
        files[spec.filename] = {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "role": spec.role,
            "publisher_unit": spec.unit,
        }
        analysis[spec.role] = analyze_file(path, spec, chunksize=chunksize)

    supporting_root = raw_root.parent
    support_paths = {
        "brick": supporting_root / "Bldg59_w_occ Brick model.ttl",
        "metadata": supporting_root / "Bldg59_w_occ metadata of dataset.json",
    }
    support = {
        name: {"path": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for name, path in support_paths.items()
        if path.is_file()
    }

    relationships = {
        "sat_tracking": analyze_sat_tracking(raw_root, chunksize),
        "zone_deadbands": analyze_zone_deadbands(raw_root, chunksize),
        "outdoor_air_fraction": analyze_oa_fraction(raw_root, chunksize),
    }
    fan = analysis["rtu_fan_speed_feedback"]
    uft_fan = analysis["uft_fan_speed"]
    valve = analysis["uft_heating_water_valve_position"]
    sat_sp = analysis["rtu_supply_air_temperature_setpoint"]
    static_sp = analysis["rtu_supply_static_pressure_setpoint"]
    damper = analysis["rtu_outdoor_air_damper_position"]
    econ = analysis["rtu_economizer_setpoint"]

    constraints = [
        {
            "id": "HVAC-01",
            "status": "INFERRED_FROM_DATA",
            "constraint": "Do not model the RTUs as a simple weekday-only on/off schedule without reconciling fan feedback.",
            "basis": "All eight supply/return fan feedback channels are evaluated at >5% by regime and source-clock hour.",
            "evidence": _compact_point_table(fan),
            "exclusion": "Fan-speed feedback is not a proof of airflow, electric power, or occupancy and may include minimum/override operation.",
        },
        {
            "id": "HVAC-02",
            "status": "INFERRED_FROM_DATA",
            "constraint": "Use the recorded RTU SAT setpoint distributions as bounded schedule/reset candidates by unit and regime.",
            "evidence": _compact_point_table(sat_sp),
            "exclusion": "A BAS setpoint is not proof that the coil met it; retain the separate SAT tracking error evidence.",
        },
        {
            "id": "HVAC-03",
            "status": "INFERRED_FROM_DATA",
            "constraint": "Retain a nonzero zone thermostat deadband and preserve measured zone-to-zone diversity.",
            "evidence": relationships["zone_deadbands"]["valid_deadband"],
            "exclusion": "Zero/implausible setpoints and nonpositive deadbands are excluded, not repaired.",
        },
        {
            "id": "HVAC-04",
            "status": "INFERRED_FROM_DATA",
            "constraint": "Model UFT fan modulation separately from RTU availability; 20% is treated as a candidate minimum, not off.",
            "evidence": {
                "aggregate_by_regime": uft_fan["aggregate_by_regime"],
                "points": _compact_point_table(uft_fan),
            },
            "exclusion": "The publisher calls these fan speeds, while Brick types them as supply-air-flow sensors; actuator semantics remain unresolved.",
        },
        {
            "id": "HVAC-05",
            "status": "INFERRED_FROM_DATA",
            "constraint": "Represent terminal hydronic heating operation explicitly and preserve the 2019 heat-pump regime boundary.",
            "evidence": {"aggregate_by_regime": valve["aggregate_by_regime"]},
            "exclusion": "Valve position is not thermal load; frequent 0%/100% saturation requires control-semantics review.",
        },
        {
            "id": "HVAC-06",
            "status": "INFERRED_FROM_DATA",
            "constraint": "Treat outdoor-air fraction/economizer/static-pressure inputs as measured control priors, not fixed ASHRAE defaults.",
            "evidence": {
                "static_pressure_setpoint": _compact_point_table(static_sp),
                "outdoor_air_damper": _compact_point_table(damper),
                "economizer_setpoint": _compact_point_table(econ),
                "outdoor_air_fraction": relationships["outdoor_air_fraction"],
            },
            "exclusion": (
                "The pressure unit is publisher-labeled psi but magnitude/Brick semantics require verification; OA flow is useful only "
                "for its disclosed availability window; no economizer-effectiveness claim is made without aligned OAT/MAT/RAT analysis."
            ),
        },
    ]

    return {
        "schema": SCHEMA,
        "claim_status": "OPERATING_EVIDENCE_ONLY_NOT_CALIBRATED",
        "building_scope": "two monitored office floors; not full Building 59",
        "period": {"start": "2018-01-01", "end_inclusive": "2020-12-31"},
        "source_clock": SOURCE_CLOCK,
        "time_basis_status": TIME_BASIS_STATUS,
        "regime_definitions": {
            "2018": "calendar 2018",
            "2019_pre_reported_march_change": "2019-01-01 through 2019-03-31",
            "2019_post_reported_march_change": (
                "2019-04-01 through 2019-12-31; the publication reports a change after March, "
                "but the exact commissioning timestamp remains unresolved"
            ),
            "2020_pre_shelter_in_place": "2020-01-01 through 2020-03-17",
            "2020_shelter_in_place": "2020-03-18 onward",
        },
        "method": {
            "streaming_chunksize": chunksize,
            "means_counts_and_activity_fractions": "exact over finite cleaned-file values",
            "percentiles": "deterministic row-stride samples disclosed per source specification",
            "cleaning_disclosure": (
                "Publisher supplied cleaned/curated files; the release README states gaps/outliers were modified using linear "
                "interpolation, KNN and matrix factorization. These results do not represent raw missingness."
            ),
            "activity_thresholds": {spec.role: spec.activity_threshold for spec in SPECS if spec.activity_threshold is not None},
        },
        "sources": files,
        "supporting_sources": support,
        "analysis": analysis,
        "paired_relationships": relationships,
        "modeling_constraints": constraints,
        "prohibited_claims": [
            "Do not call the observed source-clock hours a local civil-time schedule until timezone/DST is confirmed.",
            "Do not treat cleaned-file completeness as raw sensor completeness.",
            "Do not treat fan speed, valve position, damper position, setpoint or airflow as electric or thermal load.",
            "Do not treat partial south-half occupant counts as whole-office occupancy.",
            "Do not infer installed capacity, COP, envelope properties or tariff assignment from this evidence.",
        ],
    }


def _fmt(value: Any, digits: int = 2) -> str:
    return "NA" if value is None else f"{float(value):.{digits}f}"


def render_markdown(evidence: dict[str, Any]) -> str:
    analysis = evidence["analysis"]
    fan = analysis["rtu_fan_speed_feedback"]
    sat_sp = analysis["rtu_supply_air_temperature_setpoint"]
    sat_track = evidence["paired_relationships"]["sat_tracking"]
    deadband = evidence["paired_relationships"]["zone_deadbands"]
    oa_fraction = evidence["paired_relationships"]["outdoor_air_fraction"]
    uft_fan = analysis["uft_fan_speed"]
    valve = analysis["uft_heating_water_valve_position"]

    fan_rows = []
    for point, stats in fan["points"].items():
        fan_rows.append(
            f"| `{point}` | {_fmt(stats.get('median_sampled'))} | {_fmt(stats.get('p05_sampled'))} | "
            f"{_fmt(stats.get('p95_sampled'))} | {_fmt(100 * stats.get('fraction_above_activity_threshold', 0), 1)}% |"
        )
    sat_rows = []
    for point, stats in sat_sp["points"].items():
        sat_rows.append(
            f"| `{point}` | {_fmt(stats.get('median_sampled'))} | {_fmt(stats.get('p05_sampled'))} | "
            f"{_fmt(stats.get('p95_sampled'))} |"
        )
    regime_rows = []
    for regime, stats in fan["aggregate_by_regime"].items():
        regime_rows.append(
            f"| {regime} | {_fmt(stats.get('mean'))} | {_fmt(stats.get('median_sampled'))} | "
            f"{_fmt(100 * stats.get('fraction_above_activity_threshold', 0), 1)}% |"
        )
    uft_rows = []
    for regime in evidence["regime_definitions"]:
        fan_stats = uft_fan["aggregate_by_regime"].get(regime, {})
        valve_stats = valve["aggregate_by_regime"].get(regime, {})
        uft_rows.append(
            f"| {regime} | {_fmt(fan_stats.get('median_sampled'))} | "
            f"{_fmt(100 * fan_stats.get('fraction_above_activity_threshold', 0), 1)}% | "
            f"{_fmt(valve_stats.get('median_sampled'))} | "
            f"{_fmt(100 * valve_stats.get('fraction_above_activity_threshold', 0), 1)}% |"
        )

    return f"""# Building 59 HVAC as-operated evidence

**Claim boundary:** `OPERATING_EVIDENCE_ONLY_NOT_CALIBRATED`

This report converts the public LBNL Building 59 BAS histories into reproducible model constraints for the **two monitored office floors**. It does not establish an as-built sequence of operations, installed capacity, whole-building load, or a calibrated EnergyPlus model.

## Method and clock caveat

The analysis streams each CSV in chunks, hashes every input, calculates exact finite-value counts/means/activity fractions, and estimates percentiles from a deterministic row-stride sample. The source release says these are **cleaned and imputed** files (linear interpolation, KNN and matrix factorization were used), so apparent completeness is not raw sensor completeness.

All timestamps are timezone-naive. Hourly and weekday/weekend findings are therefore in the **recorded source clock**, not proven America/Los_Angeles civil time. This blocks direct copying of source-clock hours into an IDF until BAS timezone and DST behavior are confirmed.

## RTU fan operation

The >5% column is an evidence threshold for nonzero feedback, not a definitive equipment-enable proof.

| Point | median % | p05 % | p95 % | >5% of valid records |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(fan_rows)}

| Regime | mean % | median % | >5% |
| --- | ---: | ---: | ---: |
{chr(10).join(regime_rows)}

**Model consequence:** do not use a simple weekday-only RTU availability schedule unless it can reproduce the pervasive fan feedback. Use continuous/minimum operation plus data-derived modulation candidates, while retaining a possibility that overrides or BAS semantics affect the feedback.

## Supply-air setpoints and tracking

| Point | median °F | p05 °F | p95 °F |
| --- | ---: | ---: | ---: |
{chr(10).join(sat_rows)}

Across {sat_track['paired_valid_count']:,} valid RTU-minute pairs, measured SAT minus SAT setpoint has mean {_fmt(sat_track['aggregate_error'].get('mean'))} °F, median {_fmt(sat_track['aggregate_error'].get('median_sampled'))} °F, p05/p95 {_fmt(sat_track['aggregate_error'].get('p05_sampled'))}/{_fmt(sat_track['aggregate_error'].get('p95_sampled'))} °F, and {100 * sat_track['fraction_within_2F']:.1f}% of pairs lie within ±2 °F. These setpoints should define bounded schedules/resets; the tracking error remains a separate control-performance constraint.

## Zone thermostat evidence

Cooling/heating setpoint histories share {deadband['common_zone_count']} named zones. After excluding {deadband['invalid_zero_or_implausible_excluded']:,} zero/implausible pairs and {deadband['nonpositive_deadband_excluded']:,} nonpositive deadbands, the valid cooling-minus-heating deadband is median {_fmt(deadband['valid_deadband'].get('median_sampled'))} °F and p05/p95 {_fmt(deadband['valid_deadband'].get('p05_sampled'))}/{_fmt(deadband['valid_deadband'].get('p95_sampled'))} °F.

**Model consequence:** retain a dual-setpoint thermostat and measured zone diversity. Do not replace the observed setpoints with a single 90.1 default. ASHRAE 90.1 is a code-compliance prior, while these histories are the as-operated evidence.

## Outdoor air, economizer and static pressure

The publisher describes OA-flow availability as April–December 2020. The first nonzero OA-flow row in the cleaned file is `{analysis['rtu_outdoor_air_flow']['first_nonzero_timestamp']}`. For rows with supply flow >100 cfm and OA flow >100 cfm, the plausible OA/SA ratio has median {_fmt(oa_fraction['aggregate_ratio'].get('median_sampled'), 3)} and p05/p95 {_fmt(oa_fraction['aggregate_ratio'].get('p05_sampled'), 3)}/{_fmt(oa_fraction['aggregate_ratio'].get('p95_sampled'), 3)}. {oa_fraction['invalid_ratio_excluded']:,} ratios above 1.2 were excluded and remain a data-quality signal.

Economizer setpoint, OA-damper and static-pressure distributions are preserved in the JSON evidence. The pressure field is publisher-labeled `psi`, but its magnitude and Brick role require verification before conversion; no economizer-effectiveness claim is made without a separate aligned OAT/MAT/RAT calculation.

## UFT terminal operation and regimes

For UFT fans, `>20.5%` means above the prominent 20% minimum candidate—not simply on. For heating valves, `>5%` is nontrivial position, not delivered heat.

| Regime | UFT fan median % | fan >20.5% | HW valve median % | valve >5% |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(uft_rows)}

The reported post-March-2019 heating-system change and the 2020-03-18 shelter-in-place boundary are kept separate. The exact plant commissioning timestamp remains unresolved. Valve-position saturation and the metadata/Brick disagreement over UFT fan-point semantics must be reviewed before interpreting these as runtime or thermal load.

## Occupancy limitation

`occ.csv` contains camera counts only for the south halves of the third and fourth floors and only for a limited period. It is hashed and summarized here to preserve the operational context, but it is explicitly prohibited as a whole-office occupancy count or a direct people-load multiplier.

## Model constraints to carry forward

1. Start from continuous/minimum RTU operation and data-derived fan modulation; test any weekday shutdown hypothesis against all eight feedback channels.
2. Use measured RTU SAT setpoint distributions and SAT tracking as separate inputs/validation signals.
3. Use measured cooling/heating setpoint histories and deadband diversity rather than one fixed code-default thermostat schedule.
4. Represent terminal fan modulation and hydronic reheat separately; preserve the reported post-March-2019 plant regime boundary and resolve its exact timestamp before model freeze.
5. Use OA-flow evidence only inside its available window; retain damper/economizer/static-pressure signals as bounded priors with unit/semantics caveats.
6. Keep pre-pandemic and pandemic operation separate. Do not fit one annual schedule across the regime change.
7. Validate zone temperature, fan/airflow, terminal behavior and HVAC electric end use in addition to monthly kWh.

## Explicit exclusions

- These data do not identify installed coil capacity, COP, envelope assemblies, full-building occupancy, or the utility tariff.
- Setpoints and commands are not loads; fan feedback is not power; valve/damper position is not flow or heat.
- The cleaned histories can hide original gaps or faults. Raw-data analytics require the separate raw release.
- A numerical Guideline 14 pass on a scope-mismatched subtotal would not remove these physics and boundary limitations.

The machine-readable evidence, source hashes, per-point/regime distributions, source-clock hourly profiles, and exclusions are in `config/b59_hvac_operating_evidence.json`.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True, help="Directory containing Bldg59_clean data CSVs")
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    parser.add_argument("--chunksize", type=int, default=50_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence = build_evidence(args.raw_root, chunksize=args.chunksize)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_out.write_text(render_markdown(evidence), encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, "json": str(args.json_out), "markdown": str(args.markdown_out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
