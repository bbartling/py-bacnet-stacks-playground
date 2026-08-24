#!/usr/bin/env python3
"""Build the bounded-hybrid 2020 Building 59 EPW from prepared inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vibe23.b59_weather import build_2020_amy_epw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--measured",
        type=Path,
        default=Path("data/raw/building_59/Bldg59_clean data/site_weather.csv"),
    )
    parser.add_argument(
        "--auxiliary",
        type=Path,
        default=Path("data/processed/b59_weather/b59_auxiliary_fixed_pst_2020.csv"),
    )
    parser.add_argument(
        "--substitution",
        type=Path,
        default=Path("data/processed/b59_weather/b59_measured_tail_substitution_2021-01-01.csv"),
    )
    parser.add_argument("--output", type=Path, default=Path("weather/b59_2020_bounded_hybrid_amy.epw"))
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--latitude", type=float, default=37.876)
    parser.add_argument("--longitude", type=float, default=-122.249)
    parser.add_argument("--elevation-m", type=float, default=270.1668)
    args = parser.parse_args()
    manifest = build_2020_amy_epw(
        args.measured,
        args.auxiliary,
        args.output,
        latitude_deg=args.latitude,
        longitude_deg=args.longitude,
        elevation_m=args.elevation_m,
        measured_substitution_path=args.substitution,
        auxiliary_provenance={
            "provider": "Open-Meteo Historical Weather API (reanalysis)",
            "source_url": "https://open-meteo.com/en/docs/historical-weather-api",
            "requested_coordinates": [args.latitude, args.longitude],
            "returned_coordinates": [37.855885, -122.21181],
        },
        city="Berkeley",
        state="CA",
        country="USA",
        source="LBNL-Site-plus-OpenMeteo",
    )
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
