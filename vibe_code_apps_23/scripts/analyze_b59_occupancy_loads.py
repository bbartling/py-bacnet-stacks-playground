#!/usr/bin/env python3
"""Derive traceable Building 59 occupancy and internal-load evidence.

The output is deliberately an evidence ledger and schedule-prior aid.  It does
not assign a civil timezone, turn connected devices into people, or certify an
EnergyPlus calibration.  Each profile remains in the native, naive source
clock of its CSV until a reviewer freezes a per-file time transformation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

SOURCE_SPECS: dict[str, dict[str, Any]] = {
    "occupancy_camera": {
        "filename": "occ.csv",
        "timestamp_format": "%Y-%m-%d %H:%M:%S",
        "columns": ("occ_third_south", "occ_fourth_south"),
        "scope": "camera-derived counts for southern portions of the third and fourth office floors",
        "unit": "camera-derived count; not a whole-office population",
    },
    "wifi": {
        "filename": "wifi.csv",
        "timestamp_format": "%Y/%m/%d %H:%M",
        "columns": ("wifi_first_south", "wifi_second_south", "wifi_third_south", "wifi_fourth_south"),
        "scope": "connected devices by south-labelled access-point grouping; not a people count",
        "unit": "connected devices; not people",
    },
    "electricity": {
        "filename": "ele.csv",
        "timestamp_format": "%Y/%m/%d %H:%M",
        "columns": ("mels_S", "mels_N", "lig_S"),
        "scope": "two measured plug panels and south-wing lighting panel; north-wing lighting is absent",
        "unit": "reported kW samples",
    },
}


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest without materializing raw telemetry."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_number(value: Any) -> float | None:
    """Turn finite numerical values into stable JSON values."""
    number = float(value)
    return round(number, 4) if np.isfinite(number) else None


def _read_source(raw_root: Path, name: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    spec = SOURCE_SPECS[name]
    path = raw_root / str(spec["filename"])
    if not path.is_file():
        raise FileNotFoundError(f"missing required telemetry file: {path}")
    frame = pd.read_csv(path)
    required = ["date", *spec["columns"]]
    absent = [column for column in required if column not in frame.columns]
    if absent:
        raise ValueError(f"{path.name} is missing required columns: {absent}")
    parsed = pd.to_datetime(frame["date"], format=spec["timestamp_format"], errors="coerce")
    if parsed.isna().any():
        raise ValueError(f"{path.name} contains {int(parsed.isna().sum())} unparseable timestamps")
    values = frame.loc[:, list(spec["columns"])].apply(pd.to_numeric, errors="coerce")
    values.index = pd.DatetimeIndex(parsed)
    values = values.sort_index()
    duplicate_rows = int(values.index.duplicated(keep=False).sum())
    audit = {
        "file": str(spec["filename"]),
        "sha256": sha256_file(path),
        "rows": int(len(values)),
        "coverage_start_source_clock": values.index.min().isoformat(sep=" "),
        "coverage_end_source_clock": values.index.max().isoformat(sep=" "),
        "timestamp_format": spec["timestamp_format"],
        "explicit_timezone_or_offset": False,
        "duplicate_timestamp_rows": duplicate_rows,
        "null_or_non_numeric_values": {column: int(values[column].isna().sum()) for column in values.columns},
        "scope": spec["scope"],
        "unit": spec["unit"],
    }
    return values, audit


def _cadence_audit(index: pd.DatetimeIndex) -> dict[str, Any]:
    ordered = index.sort_values()
    seconds = ordered.to_series().diff().dropna().dt.total_seconds()
    counts = seconds.value_counts()
    cadence = int(counts.index[0]) if not counts.empty else None
    return {
        "dominant_cadence_seconds": cadence,
        "dominant_cadence_rows": int(counts.iloc[0]) if not counts.empty else 0,
        "distinct_positive_cadences_seconds": [int(item) for item in sorted(seconds[seconds > 0].unique())[:12]],
        "source_clock_dst_caveat": "Naive timestamps carry no offset. DST/civil-time semantics must be resolved per file before EnergyPlus schedule use.",
    }


def _federal_holidays(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    calendar = USFederalHolidayCalendar()
    dates = calendar.holidays(start=index.min().normalize(), end=index.max().normalize())
    return set(pd.DatetimeIndex(dates).normalize())


def _profile(values: pd.Series, *, label: str) -> dict[str, Any]:
    """Return median day/hour profiles without source-time conversion or fill."""
    if not isinstance(values.index, pd.DatetimeIndex):
        raise TypeError("profile values need a DatetimeIndex")
    ambiguous = values.index.duplicated(keep=False)
    observed = values.loc[~ambiguous].dropna().astype(float)
    if observed.empty:
        raise ValueError(f"{label} has no observed non-duplicate values")
    frame = observed.to_frame("value")
    frame["source_date"] = frame.index.normalize()
    frame["hour"] = frame.index.hour
    federal_holidays = _federal_holidays(frame.index)
    is_holiday = frame["source_date"].isin(federal_holidays)
    frame["day_type"] = np.select(
        [is_holiday, frame.index.dayofweek >= 5],
        ["us_federal_holiday", "weekend"],
        default="weekday_non_holiday",
    )
    # Collapse native minute/fifteen-minute values to a day-hour before taking
    # the cross-day median, so source sample frequency cannot overweight a day.
    day_hour = frame.groupby(["source_date", "day_type", "hour"], observed=True)["value"].mean()
    profiles: dict[str, Any] = {}
    daily_means: dict[str, float | None] = {}
    active_hours: dict[str, list[int]] = {}
    for day_type in ("weekday_non_holiday", "weekend", "us_federal_holiday"):
        subset = day_hour.xs(day_type, level="day_type", drop_level=False) if day_type in day_hour.index.get_level_values("day_type") else pd.Series(dtype=float)
        daily = subset.groupby(level="source_date").mean() if not subset.empty else pd.Series(dtype=float)
        hourly = subset.groupby(level="hour").median() if not subset.empty else pd.Series(dtype=float)
        full = hourly.reindex(range(24))
        profiles[day_type] = [_json_number(value) for value in full]
        daily_means[day_type] = _json_number(daily.median()) if not daily.empty else None
        if hourly.empty:
            active_hours[day_type] = []
        else:
            low, high = float(hourly.min()), float(hourly.max())
            active_hours[day_type] = [int(hour) for hour, value in hourly.items() if value >= low + 0.2 * (high - low)]
    return {
        "label": label,
        "observed_rows_after_dropping_ambiguous_and_null": int(len(observed)),
        "ambiguous_duplicate_rows_excluded": int(ambiguous.sum()),
        "hours": list(range(24)),
        "hourly_median_by_source_day_type": profiles,
        "median_daily_mean_by_source_day_type": daily_means,
        "source_clock_active_hours_by_day_type": active_hours,
        "holiday_definition": "US federal holiday calendar, used only as a diagnostic; it is not evidence of a Building 59 closure calendar.",
    }


def _normalized_profile(profile: dict[str, Any], *, background_subtract: bool) -> list[float | None]:
    source = profile["hourly_median_by_source_day_type"]["weekday_non_holiday"]
    finite = [value for value in source if value is not None]
    if not finite:
        return [None] * 24
    baseline = min(finite) if background_subtract else 0.0
    denominator = max(finite) - baseline
    if denominator <= 0:
        return [0.0 if value is not None else None for value in source]
    return [None if value is None else _json_number((value - baseline) / denominator) for value in source]


def _yearly_daily_median(values: pd.Series) -> dict[str, float | None]:
    observed = values.loc[~values.index.duplicated(keep=False)].dropna().astype(float)
    if observed.empty:
        return {}
    daily = observed.groupby(observed.index.normalize()).mean()
    return {str(year): _json_number(group.median()) for year, group in daily.groupby(daily.index.year)}


def _regime_daily_median(values: pd.Series) -> dict[str, float | None]:
    observed = values.loc[~values.index.duplicated(keep=False)].dropna().astype(float)
    ranges = {
        "2018": ("2018-01-01", "2019-01-01"),
        "2019": ("2019-01-01", "2020-01-01"),
        "2020_pre_shelter_in_place_through_2020_03_17": ("2020-01-01", "2020-03-18"),
        "2020_shelter_in_place_from_2020_03_18": ("2020-03-18", "2021-01-01"),
    }
    result: dict[str, float | None] = {}
    for name, (start, end) in ranges.items():
        selected = observed.loc[(observed.index >= start) & (observed.index < end)]
        daily = selected.groupby(selected.index.normalize()).mean()
        result[name] = _json_number(daily.median()) if not daily.empty else None
    return result


def _hourly_observed(values: pd.Series) -> pd.Series:
    clean = values.loc[~values.index.duplicated(keep=False)].dropna().astype(float)
    return clean.groupby(clean.index.floor("h")).mean()


def _best_lag_hours(
    first: pd.Series,
    second: pd.Series,
    *,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """Compare native-clock hourly shapes; this is diagnostic, not conversion."""
    left, right = _hourly_observed(first), _hourly_observed(second)
    if start is not None:
        left, right = left.loc[left.index >= start], right.loc[right.index >= start]
    if end is not None:
        left, right = left.loc[left.index < end], right.loc[right.index < end]
    options: list[tuple[int, int, float, float]] = []
    for shift in range(-12, 13):
        shifted = left.copy()
        shifted.index = shifted.index + pd.Timedelta(hours=shift)
        paired = pd.concat([shifted.rename("first"), right.rename("second")], axis=1).dropna()
        if len(paired) < 24:
            continue
        options.append((shift, len(paired), float(paired["first"].corr(paired["second"], method="spearman")), float(paired["first"].corr(paired["second"], method="pearson"))))
    if not options:
        return {"status": "INSUFFICIENT_OVERLAP"}
    best = max(options, key=lambda item: (item[2], item[3]))
    return {
        "status": "DIAGNOSTIC_ONLY",
        "best_shift_hours_applied_to_first": best[0],
        "paired_hours": best[1],
        "spearman": _json_number(best[2]),
        "pearson": _json_number(best[3]),
        "analysis_window_source_clock": [start, end],
        "interpretation": "A shape lag is not proof of a timezone or DST conversion.",
    }


def build_evidence(raw_root: Path) -> dict[str, Any]:
    """Build the JSON-serializable, non-calibration evidence ledger."""
    raw_root = Path(raw_root)
    occupancy, occ_audit = _read_source(raw_root, "occupancy_camera")
    wifi, wifi_audit = _read_source(raw_root, "wifi")
    electricity, ele_audit = _read_source(raw_root, "electricity")
    for values, audit in ((occupancy, occ_audit), (wifi, wifi_audit), (electricity, ele_audit)):
        audit.update(_cadence_audit(values.index))

    occ_south = occupancy.sum(axis=1, min_count=len(occupancy.columns)).rename("camera_south_office_sum")
    wifi_south = wifi[["wifi_third_south", "wifi_fourth_south"]].sum(axis=1, min_count=2).rename("wifi_south_office_sum")
    mels_south = electricity["mels_S"].rename("mels_south_kw")
    mels_north = electricity["mels_N"].rename("mels_north_kw")
    mels_total = electricity[["mels_S", "mels_N"]].sum(axis=1, min_count=2).rename("mels_total_kw")
    lighting_south = electricity["lig_S"].rename("lighting_south_kw")

    profiles = {
        "camera_south_office_sum": _profile(occ_south, label="camera occupancy, south office only"),
        "wifi_south_office_sum": _profile(wifi_south, label="Wi-Fi devices, south office only"),
        "lighting_south_kw": _profile(lighting_south, label="south-wing lighting panel"),
        "mels_south_kw": _profile(mels_south, label="south-wing MEL panel"),
        "mels_north_kw": _profile(mels_north, label="north-wing MEL panel"),
        "mels_total_kw": _profile(mels_total, label="north plus south MEL panels"),
    }
    profiles["camera_south_office_sum"]["weekday_fraction_of_weekday_peak"] = _normalized_profile(
        profiles["camera_south_office_sum"], background_subtract=False
    )
    profiles["wifi_south_office_sum"]["weekday_background_subtracted_fraction"] = _normalized_profile(
        profiles["wifi_south_office_sum"], background_subtract=True
    )
    for name in ("lighting_south_kw", "mels_south_kw", "mels_north_kw", "mels_total_kw"):
        profiles[name]["weekday_fraction_of_weekday_peak"] = _normalized_profile(profiles[name], background_subtract=False)

    source_data = {
        "occupancy_camera": occ_audit,
        "wifi": wifi_audit,
        "electricity": ele_audit,
    }
    return {
        "schema": "vibe23.b59_occupancy_load_evidence.v1",
        "claim_status": "DIAGNOSTIC_EVIDENCE_AND_BOUNDED_PRIORS_ONLY",
        "allowed_use": "Reviewable schedule and internal-load hypotheses after per-file time-basis, scope, and point-binding approval. Not an EnergyPlus calibration claim.",
        "source_release": {
            "dataset_url": "https://bbd.labworks.org/ds/bbd/lbnlbldg59",
            "dataset_scope": "The published dataset covers the two office floors, not the building mechanical or NERSC/HPC floor loads.",
            "raw_root_not_published": True,
        },
        "method": {
            "time_axis": "SOURCE_CLOCK_NAIVE_PER_FILE_UNRESOLVED",
            "aggregation": "Observed native samples -> source-date/hour mean -> median across source dates; no added interpolation or timezone conversion.",
            "day_types": "weekday_non_holiday, weekend, and US-federal-holiday diagnostic. Holidays do not prove a Building 59 closure.",
            "upstream_curation_caveat": "The distributed clean release was already curated upstream; this script does not add imputation but cannot identify every publisher-filled value.",
        },
        "source_data": source_data,
        "profiles": profiles,
        "yearly_daily_median_kw_or_count": {
            "camera_south_office_sum": _yearly_daily_median(occ_south),
            "wifi_south_office_sum": _yearly_daily_median(wifi_south),
            "lighting_south_kw": _yearly_daily_median(lighting_south),
            "mels_total_kw": _yearly_daily_median(mels_total),
        },
        "pandemic_regime_daily_median_kw_or_count": {
            "camera_south_office_sum": _regime_daily_median(occ_south),
            "wifi_south_office_sum": _regime_daily_median(wifi_south),
            "lighting_south_kw": _regime_daily_median(lighting_south),
            "mels_total_kw": _regime_daily_median(mels_total),
            "interpretation": "Post-2020-03-17 internal-load changes are disturbance/regime evidence, not a normal-office schedule prior.",
        },
        "native_clock_shape_lag_checks": {
            "camera_south_count_vs_mels_total": _best_lag_hours(
                occ_south, mels_total, start="2018-05-22", end="2018-07-12"
            ),
            "camera_south_count_vs_wifi_south_devices": _best_lag_hours(
                occ_south, wifi_south, start="2018-05-22", end="2018-07-12"
            ),
            "wifi_south_devices_vs_mels_total": _best_lag_hours(
                wifi_south, mels_total, start="2018-05-22", end="2018-07-12"
            ),
        },
        "modeling_constraints": [
            "Do not convert camera counts or Wi-Fi devices into whole-office people without a reviewed spatial/count reconciliation.",
            "Do not infer north-wing lighting from lig_S; the released electricity file does not contain lig_N.",
            "Keep south and north MEL amplitudes distinct unless a panel/space mapping supports aggregation.",
            "Do not use raw clock hours as EnergyPlus local times until each file's UTC/local/DST semantics are independently frozen.",
            "Do not use 2020 post-shelter-in-place profiles as normal-office priors; model them only as a named pandemic/control regime.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True, help="Directory containing occ.csv, wifi.csv, and ele.csv")
    parser.add_argument("--output", type=Path, required=True, help="JSON evidence-ledger path; raw telemetry is never copied")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence = build_evidence(args.raw_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "claim_status": evidence["claim_status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
