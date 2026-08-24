"""Fail-closed 2020 Building 59 AMY weather and EPW construction."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

UTC = "UTC"
PST = "Etc/GMT+8"  # Fixed UTC-8 local-standard time, not daylight-saving time.
EPW_TIMEZONE = -8
YEAR = 2020
MEASURED_COLUMNS = {
    "timestamp": "date",
    "dry_bulb_c": "air_temp_set_1",
    "dew_point_c": "dew_point_temperature_set_1d",
    "relative_humidity_pct": "relative_humidity_set_1",
    "ghi_w_m2": "solar_radiation_set_1",
}
AUXILIARY_COLUMNS = (
    "timestamp_utc", "pressure_pa", "wind_direction_deg", "wind_speed_m_s",
    "dni_w_m2", "dhi_w_m2", "precipitation_mm", "total_sky_cover_tenths", "opaque_sky_cover_tenths",
)


class B59WeatherError(ValueError):
    """Raised when AMY source data cannot safely make a complete EPW."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_index(values: pd.Series, label: str) -> pd.DatetimeIndex:
    parsed = pd.to_datetime(values, errors="coerce", utc=True)
    if parsed.isna().any():
        raise B59WeatherError(f"{label} has {int(parsed.isna().sum())} unparseable UTC timestamps")
    index = pd.DatetimeIndex(parsed)
    if index.has_duplicates:
        raise B59WeatherError(f"{label} has duplicate UTC timestamps")
    return index


def _strict_numeric(frame: pd.DataFrame, columns: list[str], label: str) -> pd.DataFrame:
    numeric = frame.loc[:, columns].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        raise B59WeatherError(f"{label} has {int(numeric.isna().sum().sum())} null/non-numeric values")
    return numeric


def _require_regular(index: pd.DatetimeIndex, interval: pd.Timedelta, label: str) -> None:
    if len(index) < 2 or not (index.to_series().diff().iloc[1:] == interval).all():
        raise B59WeatherError(f"{label} has gaps or non-{interval} cadence")


def _solar_elevation_deg(index: pd.DatetimeIndex, latitude_deg: float, longitude_deg: float) -> pd.Series:
    """NOAA-style approximate solar elevation for physical night-screening."""
    local = index.tz_convert(PST)
    day = local.dayofyear.to_numpy()
    hour = local.hour.to_numpy() + local.minute.to_numpy() / 60 + local.second.to_numpy() / 3600
    gamma = 2 * np.pi / 365 * (day - 1 + (hour - 12) / 24)
    equation_of_time = 229.18 * (
        0.000075
        + 0.001868 * np.cos(gamma)
        - 0.032077 * np.sin(gamma)
        - 0.014615 * np.cos(2 * gamma)
        - 0.040849 * np.sin(2 * gamma)
    )
    declination = (
        0.006918
        - 0.399912 * np.cos(gamma)
        + 0.070257 * np.sin(gamma)
        - 0.006758 * np.cos(2 * gamma)
        + 0.000907 * np.sin(2 * gamma)
        - 0.002697 * np.cos(3 * gamma)
        + 0.00148 * np.sin(3 * gamma)
    )
    time_offset_minutes = equation_of_time + 4 * longitude_deg - 60 * EPW_TIMEZONE
    hour_angle = np.radians((hour * 60 + time_offset_minutes) / 4 - 180)
    latitude = np.radians(latitude_deg)
    sin_elevation = (
        np.sin(latitude) * np.sin(declination)
        + np.cos(latitude) * np.cos(declination) * np.cos(hour_angle)
    )
    return pd.Series(np.degrees(np.arcsin(sin_elevation)), index=index)


def _validate_measured(hourly: pd.DataFrame, latitude_deg: float, longitude_deg: float) -> None:
    ranges = {
        "dry_bulb_c": (-90, 70), "dew_point_c": (-100, 60), "relative_humidity_pct": (0, 100), "ghi_w_m2": (0, 1500),
    }
    for column, (low, high) in ranges.items():
        if not hourly[column].between(low, high).all():
            raise B59WeatherError(f"{column} is outside [{low}, {high}]")
    if (hourly["dew_point_c"] > hourly["dry_bulb_c"] + 0.2).any():
        raise B59WeatherError("dew point exceeds dry bulb beyond tolerance")
    # The four quarter-hour samples represent a start-labelled hourly mean
    # centered at 22.5 minutes.  Use civil-night (-6 deg) rather than the hour
    # label itself so dawn/dusk energy is not incorrectly rejected.
    elevation = _solar_elevation_deg(
        hourly.index + pd.Timedelta(minutes=22, seconds=30), latitude_deg, longitude_deg
    ).to_numpy()
    if (hourly["ghi_w_m2"].to_numpy()[elevation < -6] > 5).any():
        raise B59WeatherError("GHI is materially positive during civil night")


def _validate_auxiliary(aux: pd.DataFrame) -> None:
    checks = {
        "pressure_pa": (30_000, 110_000), "wind_direction_deg": (0, 360), "wind_speed_m_s": (0, 100),
        "dni_w_m2": (0, 1500), "dhi_w_m2": (0, 1500), "precipitation_mm": (0, 500),
        "total_sky_cover_tenths": (0, 10), "opaque_sky_cover_tenths": (0, 10),
    }
    for column, (low, high) in checks.items():
        if not aux[column].between(low, high).all():
            raise B59WeatherError(f"auxiliary {column} is outside [{low}, {high}]")
    if (aux["opaque_sky_cover_tenths"] > aux["total_sky_cover_tenths"]).any():
        raise B59WeatherError("opaque cloud cover exceeds total cloud cover")


def _auxiliary_provenance(value: dict[str, Any] | None) -> dict[str, Any] | str:
    if value is None:
        return "NOT_SUPPLIED"
    required = {"provider", "source_url", "requested_coordinates", "returned_coordinates"}
    if set(value) != required or not all(value[key] for key in required):
        raise B59WeatherError(f"auxiliary provenance must contain exactly {sorted(required)}")
    return value


def _coverage(index: pd.DatetimeIndex) -> dict[str, Any]:
    expected = pd.date_range("2020-01-01", "2021-01-01", freq="h", inclusive="left", tz=PST)
    missing = expected.difference(index)
    return {"expected_hourly_rows": len(expected), "observed_hourly_rows": len(index), "missing_hours": [stamp.isoformat() for stamp in missing]}


def _read_measured(path: Path) -> pd.DataFrame:
    source = pd.read_csv(path, usecols=list(MEASURED_COLUMNS.values()))
    index = _utc_index(source.pop(MEASURED_COLUMNS["timestamp"]), "measured weather")
    measured = _strict_numeric(source, [value for key, value in MEASURED_COLUMNS.items() if key != "timestamp"], "measured weather")
    measured.columns = [key for key in MEASURED_COLUMNS if key != "timestamp"]
    measured.index = index.tz_convert(PST)
    measured = measured.loc[(measured.index.year == YEAR)].sort_index()
    _require_regular(measured.index, pd.Timedelta(minutes=15), "measured weather")
    hourly = measured.resample("h").agg(["mean", "count"])
    complete = (hourly.xs("count", axis=1, level=1) == 4).all(axis=1)
    # A partial hour is not promoted to a measured hourly record.  It becomes
    # an explicit coverage gap and can only be restored through the same
    # caller-supplied, hash-bound substitution path as a wholly missing hour.
    hourly = hourly.loc[complete].xs("mean", axis=1, level=1)
    return hourly


def _read_measured_substitution(path: Path, expected_missing: pd.DatetimeIndex) -> pd.DataFrame:
    columns = ["timestamp_utc", *[key for key in MEASURED_COLUMNS if key != "timestamp"]]
    source = pd.read_csv(path)
    if set(source.columns) != set(columns):
        raise B59WeatherError(f"measured substitution columns must be exactly {columns}")
    index = _utc_index(source.pop("timestamp_utc"), "measured substitution").tz_convert(PST)
    values = _strict_numeric(source, columns[1:], "measured substitution")
    values.index = index
    values = values.sort_index()
    if not values.index.equals(expected_missing):
        raise B59WeatherError("measured substitution must cover exactly and only the documented missing local-standard hours")
    return values


def _read_auxiliary(path: Path) -> pd.DataFrame:
    aux = pd.read_csv(path)
    if set(aux.columns) != set(AUXILIARY_COLUMNS):
        raise B59WeatherError(f"auxiliary columns must be exactly {list(AUXILIARY_COLUMNS)}")
    index = _utc_index(aux.pop("timestamp_utc"), "auxiliary weather").tz_convert(PST)
    aux = _strict_numeric(aux, list(aux.columns), "auxiliary weather")
    aux.index = index
    aux = aux.loc[(aux.index.year == YEAR)].sort_index()
    _require_regular(aux.index, pd.Timedelta(hours=1), "auxiliary weather")
    if len(aux) != 8784:
        raise B59WeatherError(f"2020 local-standard auxiliary weather must have 8784 hourly rows; got {len(aux)}")
    _validate_auxiliary(aux)
    return aux


def _epw_lines(hourly: pd.DataFrame, *, city: str, state: str, country: str, source: str, latitude_deg: float, longitude_deg: float, elevation_m: float) -> list[str]:
    header = [
        f"LOCATION,{city},{state},{country},{source},B59-AMY,{latitude_deg:.3f},{longitude_deg:.3f},{EPW_TIMEZONE},{elevation_m:.1f}",
        "DESIGN CONDITIONS,0", "TYPICAL/EXTREME PERIODS,0", "GROUND TEMPERATURES,0", "HOLIDAYS/DAYLIGHT SAVINGS,Yes,0,0,0",
        "COMMENTS 1,Measured B59 site_weather (UTC) aggregated to fixed PST; auxiliary fields explicitly supplied.",
        "COMMENTS 2,Not TMY. DNI/DHI and pressure/wind/precip/cloud are not derived from GHI.", "DATA PERIODS,1,1,Data,Sunday,1/1,12/31",
    ]
    lines = header[:]
    for stamp, row in hourly.iterrows():
        values = [
            stamp.year, stamp.month, stamp.day, stamp.hour + 1, 60, "A7A7A7A7A7A7A7A7A7A7",
            row.dry_bulb_c, row.dew_point_c, row.relative_humidity_pct, row.pressure_pa,
            9999, 9999, row.ghi_w_m2, row.dni_w_m2, row.dhi_w_m2,
            999999, 999999, 999999, 9999, row.wind_direction_deg, row.wind_speed_m_s,
            row.total_sky_cover_tenths, row.opaque_sky_cover_tenths, 9999, 99999, 9, 999999999,
            999, 0.999, 999, 99, 999, row.precipitation_mm, 1,
        ]
        lines.append(",".join(str(int(value)) if isinstance(value, (int, float)) and float(value).is_integer() else f"{float(value):.3f}" if isinstance(value, (int, float)) else str(value) for value in values))
    return lines


def _validate_epw_output(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 8 + 8784:
        raise B59WeatherError("EPW output does not contain eight headers and 8784 data rows")
    stamps: list[pd.Timestamp] = []
    for number, line in enumerate(lines[8:], start=1):
        fields = line.split(",")
        # EPW's hourly data record has 34 comma-delimited fields.
        if len(fields) != 34 or any(field == "" for field in fields):
            raise B59WeatherError(f"EPW output row {number} is malformed")
        try:
            year, month, day, hour, minute = map(int, fields[:5])
            if minute != 60 or not 1 <= hour <= 24:
                raise ValueError
            stamps.append(pd.Timestamp(year=year, month=month, day=day, hour=hour - 1, tz=PST))
        except ValueError as exc:
            raise B59WeatherError(f"EPW output row {number} has an invalid local-standard timestamp") from exc
    index = pd.DatetimeIndex(stamps)
    expected = pd.date_range("2020-01-01", "2021-01-01", freq="h", inclusive="left", tz=PST)
    if not index.equals(expected):
        raise B59WeatherError("EPW output has a gap, duplicate, wrong year, or non-PST timestamp sequence")


def build_2020_amy_epw(measured_path: Path, auxiliary_path: Path, output_path: Path, *, latitude_deg: float, longitude_deg: float, elevation_m: float, measured_substitution_path: Path | None = None, auxiliary_provenance: dict[str, Any] | None = None, city: str = "Berkeley", state: str = "CA", country: str = "USA", source: str = "LBNL") -> dict[str, Any]:
    """Build and hash a 2020 fixed-PST EPW from measured and auxiliary sources.

    Raw measurement and auxiliary timestamps are explicitly UTC.  The target
    EPW uses fixed UTC-8 local standard time.  DNI and DHI must already exist
    in the auxiliary table; they are never inferred from measured GHI.
    """
    measured_path, auxiliary_path, output_path = map(Path, (measured_path, auxiliary_path, output_path))
    hourly = _read_measured(measured_path)
    coverage = _coverage(hourly.index)
    if coverage["missing_hours"]:
        if measured_substitution_path is None:
            raise B59WeatherError("measured fixed-PST 2020 coverage is incomplete; no substitution is permitted without an explicit caller-supplied hourly table: " + str(coverage))
        missing_index = pd.DatetimeIndex(pd.to_datetime(coverage["missing_hours"], utc=True)).tz_convert(PST)
        replacement_path = Path(measured_substitution_path)
        replacement = _read_measured_substitution(replacement_path, missing_index)
        hourly = pd.concat([hourly, replacement]).sort_index()
        coverage["substitution"] = {"path": str(replacement_path), "sha256": sha256_file(replacement_path), "hours": coverage["missing_hours"], "fields": [key for key in MEASURED_COLUMNS if key != "timestamp"], "policy": "caller-supplied bounded hybrid; no unlisted hour or field substituted"}
    if len(hourly) != 8784:
        raise B59WeatherError("measured fixed-PST 2020 coverage remains incomplete after substitution: " + str(_coverage(hourly.index)))
    _validate_measured(hourly, latitude_deg, longitude_deg)
    auxiliary = _read_auxiliary(auxiliary_path)
    if not hourly.index.equals(auxiliary.index):
        raise B59WeatherError("measured and auxiliary hourly indices do not align")
    combined = hourly.join(auxiliary, how="inner")
    if len(combined) != 8784:
        raise B59WeatherError("hourly source join is incomplete")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(_epw_lines(combined, city=city, state=state, country=country, source=source, latitude_deg=latitude_deg, longitude_deg=longitude_deg, elevation_m=elevation_m)) + "\n", encoding="utf-8")
    _validate_epw_output(output_path)
    aux_provenance = _auxiliary_provenance(auxiliary_provenance)
    return {
        "schema": "vibe23.b59_amy_epw.v1", "year": YEAR, "timezone_semantics": "fixed PST (UTC-8) EPW local standard time",
        "measured_source": {"path": str(measured_path), "sha256": sha256_file(measured_path), "raw_timestamp_timezone": UTC, "coverage": coverage},
        "auxiliary_source": {"path": str(auxiliary_path), "sha256": sha256_file(auxiliary_path), "raw_timestamp_timezone": UTC, "provenance": aux_provenance},
        "output_epw": {"path": str(output_path), "sha256": sha256_file(output_path), "hourly_rows": len(combined)},
        "measured_columns": MEASURED_COLUMNS, "auxiliary_columns": list(AUXILIARY_COLUMNS),
    }
