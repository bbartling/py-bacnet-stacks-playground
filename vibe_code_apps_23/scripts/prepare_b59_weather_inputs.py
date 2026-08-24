#!/usr/bin/env python3
"""Prepare strict fixed-PST B59 weather inputs from saved Open-Meteo JSON.

This is offline-only: URLs are provenance labels supplied by the caller; the
script never contacts Open-Meteo.  It combines the 2020 UTC response with the
first eight UTC hours of 2021 so fixed-PST calendar year 2020 is complete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PST = "Etc/GMT+8"
YEAR = 2020
AUX_COLUMNS = ["timestamp_utc", "pressure_pa", "wind_direction_deg", "wind_speed_m_s", "dni_w_m2", "dhi_w_m2", "precipitation_mm", "total_sky_cover_tenths", "opaque_sky_cover_tenths"]
TAIL_COLUMNS = ["timestamp_utc", "dry_bulb_c", "dew_point_c", "relative_humidity_pct", "ghi_w_m2"]
API_FIELDS = {"surface_pressure": "hPa", "wind_speed_10m": "m/s", "wind_direction_10m": "°", "direct_normal_irradiance": "W/m²", "diffuse_radiation": "W/m²", "cloud_cover": "%", "precipitation": "mm"}
TAIL_FIELDS = {"temperature_2m": "°C", "dew_point_2m": "°C", "relative_humidity_2m": "%", "shortwave_radiation": "W/m²"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def _coordinates(metadata: dict) -> list[object]:
    return [metadata.get("latitude"), metadata.get("longitude")]


def _load(path: Path, required_units: dict[str, str]) -> tuple[dict, pd.DataFrame]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("utc_offset_seconds") != 0 or data.get("timezone") not in {"GMT", "UTC"}:
        raise ValueError(f"{path} must declare UTC API timestamps")
    hourly, units = data.get("hourly"), data.get("hourly_units")
    if not isinstance(hourly, dict) or not isinstance(units, dict) or units.get("time") != "iso8601":
        raise ValueError(f"{path} lacks Open-Meteo hourly/hourly_units metadata")
    for field, unit in required_units.items():
        if units.get(field) != unit:
            raise ValueError(f"{path} {field} unit must be {unit!r}; got {units.get(field)!r}")
        if field not in hourly:
            raise ValueError(f"{path} lacks hourly {field}")
    columns = ["time", *required_units]
    if any(len(hourly.get(column, [])) != len(hourly["time"]) for column in columns):
        raise ValueError(f"{path} has unequal hourly array lengths")
    frame = pd.DataFrame({column: hourly[column] for column in columns})
    frame["time"] = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    if frame["time"].isna().any() or frame["time"].duplicated().any():
        raise ValueError(f"{path} has invalid/duplicate UTC timestamps")
    if frame.drop(columns="time").isna().any().any():
        raise ValueError(f"{path} has null weather values")
    return data, frame


def _aux_frame(main: pd.DataFrame, tail: pd.DataFrame) -> pd.DataFrame:
    joined = pd.concat([main, tail], ignore_index=True).sort_values("time")
    local = joined["time"].dt.tz_convert(PST)
    source = joined.loc[local.dt.year == YEAR].copy()
    source["timestamp_utc"] = source.pop("time")
    result = pd.DataFrame({
        "timestamp_utc": source["timestamp_utc"], "pressure_pa": pd.to_numeric(source.surface_pressure) * 100,
        "wind_direction_deg": source.wind_direction_10m, "wind_speed_m_s": source.wind_speed_10m,
        "dni_w_m2": source.direct_normal_irradiance, "dhi_w_m2": source.diffuse_radiation,
        "precipitation_mm": source.precipitation, "total_sky_cover_tenths": pd.to_numeric(source.cloud_cover) / 10,
        "opaque_sky_cover_tenths": pd.to_numeric(source.cloud_cover) / 10,
    })
    expected = pd.date_range("2020-01-01", "2021-01-01", freq="h", inclusive="left", tz=PST)
    actual = pd.DatetimeIndex(result.timestamp_utc).tz_convert(PST)
    if not actual.equals(expected) or len(result) != 8784:
        raise ValueError("combined auxiliary response does not cover exactly fixed-PST 2020 (8784 rows)")
    if (result.total_sky_cover_tenths > 10).any() or (result.total_sky_cover_tenths < 0).any():
        raise ValueError("cloud cover conversion is outside EPW tenths bounds")
    return result.loc[:, AUX_COLUMNS]


def _tail_substitution(tail: pd.DataFrame) -> pd.DataFrame:
    expected = pd.date_range("2021-01-01T00:00:00Z", periods=8, freq="h")
    tail = tail.loc[tail.time.isin(expected)].sort_values("time")
    if not pd.DatetimeIndex(tail.time).equals(expected):
        raise ValueError("tail response must contain exactly 00:00–07:00 UTC on 2021-01-01")
    return pd.DataFrame({"timestamp_utc": tail.time, "dry_bulb_c": tail.temperature_2m, "dew_point_c": tail.dew_point_2m, "relative_humidity_pct": tail.relative_humidity_2m, "ghi_w_m2": tail.shortwave_radiation}).loc[:, TAIL_COLUMNS]


def prepare(aux_path: Path, tail_path: Path, output_dir: Path, *, aux_url: str, tail_url: str, requested_coordinates: list[float]) -> dict:
    aux_meta, aux = _load(aux_path, API_FIELDS)
    tail_meta, tail_all = _load(tail_path, {**API_FIELDS, **TAIL_FIELDS})
    aux_csv, tail_csv = _aux_frame(aux, tail_all), _tail_substitution(tail_all)
    output_dir.mkdir(parents=True, exist_ok=True)
    aux_out, tail_out = output_dir / "b59_auxiliary_fixed_pst_2020.csv", output_dir / "b59_measured_tail_substitution_2021-01-01.csv"
    aux_csv.to_csv(aux_out, index=False)
    tail_csv.to_csv(tail_out, index=False)
    if not all(isinstance(value, (int, float)) for value in [*_coordinates(aux_meta), *_coordinates(tail_meta)]):
        raise ValueError("Open-Meteo response lacks returned latitude/longitude")
    if len(requested_coordinates) != 2 or not all(isinstance(value, (int, float)) for value in requested_coordinates):
        raise ValueError("requested_coordinates must be [latitude, longitude]")
    manifest = {"schema": "vibe23.b59_open_meteo_weather_prep.v1", "created_at_utc": datetime.now(timezone.utc).isoformat(), "timezone": "UTC source -> fixed PST (UTC-8) output", "sources": {"aux_2020": {"path": str(aux_path), "sha256": sha256(aux_path), "source_url": aux_url, "requested_coordinates": requested_coordinates, "requested_coverage_utc": "2020-01-01T00:00:00Z through 2020-12-31T23:00:00Z", "returned_coordinates": _coordinates(aux_meta)}, "tail_2021": {"path": str(tail_path), "sha256": sha256(tail_path), "source_url": tail_url, "requested_coordinates": requested_coordinates, "requested_coverage_utc": "2021-01-01T00:00:00Z through 2021-01-01T07:00:00Z", "returned_coordinates": _coordinates(tail_meta)}}, "outputs": {"auxiliary_csv": {"path": str(aux_out), "sha256": sha256(aux_out), "rows": len(aux_csv), "columns": AUX_COLUMNS}, "measured_substitution_csv": {"path": str(tail_out), "sha256": sha256(tail_out), "rows": len(tail_csv), "columns": TAIL_COLUMNS, "replacement_hours_utc": tail_csv.timestamp_utc.astype(str).tolist()}}, "conversions": {"surface_pressure": "hPa * 100 -> Pa", "cloud_cover": "% / 10 -> tenths; used for total and opaque because no opaque-cloud field is returned"}}
    manifest_path = output_dir / "b59_weather_prep_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aux-json", type=Path, default=Path("data/raw/weather/open_meteo_aux_2020.json"))
    parser.add_argument("--tail-json", type=Path, default=Path("data/raw/weather/open_meteo_tail_2021-01-01.json"))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--aux-url", required=True)
    parser.add_argument("--tail-url", required=True)
    parser.add_argument("--requested-latitude", required=True, type=float)
    parser.add_argument("--requested-longitude", required=True, type=float)
    args = parser.parse_args()
    print(json.dumps(prepare(args.aux_json, args.tail_json, args.out_dir, aux_url=args.aux_url, tail_url=args.tail_url, requested_coordinates=[args.requested_latitude, args.requested_longitude]), indent=2))


if __name__ == "__main__":
    main()
