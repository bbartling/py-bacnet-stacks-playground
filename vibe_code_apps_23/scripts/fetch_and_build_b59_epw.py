#!/usr/bin/env python3
"""Fetch Open-Meteo auxiliary weather and build the B59 2020 hybrid EPW."""

from __future__ import annotations

import argparse
import importlib.util
import json
import urllib.parse
import urllib.request
from pathlib import Path

from vibe23.b59_weather import build_2020_amy_epw


def _fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=180) as response:  # noqa: S310
        dest.write_bytes(response.read())
    print(f"Wrote {dest} ({dest.stat().st_size} bytes)")


def _load_prepare():
    path = Path(__file__).resolve().parent / "prepare_b59_weather_inputs.py"
    spec = importlib.util.spec_from_file_location("prepare_b59_weather_inputs", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--measured",
        type=Path,
        default=Path("data/raw/zenodo_extract/Bldg59_clean data/site_weather.csv"),
    )
    parser.add_argument("--lat", type=float, default=37.876)
    parser.add_argument("--lon", type=float, default=-122.249)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/processed/b59_weather/open_meteo_cache"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("weather/b59_2020_bounded_hybrid_amy.epw"),
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=Path("data/processed/b59_weather/b59_2020_epw_manifest.json"),
    )
    args = parser.parse_args()

    hourly = ",".join(
        [
            "temperature_2m",
            "dew_point_2m",
            "relative_humidity_2m",
            "shortwave_radiation",
            "surface_pressure",
            "wind_speed_10m",
            "wind_direction_10m",
            "direct_normal_irradiance",
            "diffuse_radiation",
            "cloud_cover",
            "precipitation",
        ]
    )
    common = {
        "latitude": args.lat,
        "longitude": args.lon,
        "timezone": "GMT",
        "wind_speed_unit": "ms",
        "hourly": hourly,
    }
    aux_url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(
        {**common, "start_date": "2020-01-01", "end_date": "2020-12-31"}
    )
    tail_url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(
        {**common, "start_date": "2021-01-01", "end_date": "2021-01-01"}
    )
    aux_json = args.cache_dir / "open_meteo_aux_2020.json"
    tail_json = args.cache_dir / "open_meteo_tail_2021-01-01.json"
    _fetch(aux_url, aux_json)
    _fetch(tail_url, tail_json)

    prep = _load_prepare()
    processed = Path("data/processed/b59_weather")
    prep.prepare(
        aux_json,
        tail_json,
        processed,
        aux_url=aux_url,
        tail_url=tail_url,
        requested_coordinates=[args.lat, args.lon],
    )
    aux_path = processed / "b59_auxiliary_fixed_pst_2020.csv"
    sub_path = processed / "b59_measured_tail_substitution_2021-01-01.csv"

    manifest = build_2020_amy_epw(
        args.measured,
        aux_path,
        args.output,
        latitude_deg=args.lat,
        longitude_deg=args.lon,
        elevation_m=270.1668,
        measured_substitution_path=sub_path,
        auxiliary_provenance={
            "provider": "Open-Meteo Historical Weather API (reanalysis)",
            "source_url": aux_url,
            "requested_coordinates": [args.lat, args.lon],
            "returned_coordinates": [37.855885, -122.21181],
        },
        city="Berkeley",
        state="CA",
        country="USA",
        source="LBNL-Site-plus-OpenMeteo",
    )
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"epw": str(args.output), "sha256": manifest.get("epw_sha256")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
