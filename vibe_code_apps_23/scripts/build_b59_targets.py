#!/usr/bin/env python3
"""Build hash-bound 2020 Building 59 office-subtotal calibration targets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vibe23.b59_data import build_electricity_targets, sha256_file, validate_point_bindings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, default=Path("config/b59_point_bindings.json"))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--start", default="2020-01-01T00:00:00Z")
    parser.add_argument("--end", default="2021-01-01T00:00:00Z")
    parser.add_argument("--aggregation-timezone", default="UTC")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = json.loads(args.bindings.read_text(encoding="utf-8"))
    bindings = validate_point_bindings(config, args.raw_root)
    interval, monthly, provenance = build_electricity_targets(
        bindings,
        start=args.start,
        end=args.end,
        aggregation_timezone=args.aggregation_timezone,
    )
    if len(monthly) != 12 or not bool(monthly["coverage_pass"].all()):
        raise SystemExit("target window is not twelve complete monthly records; refusing publication")
    provenance.pop("source_path", None)
    provenance["source_path_relative_to_raw_root"] = config["electricity"]["path"]
    provenance["raw_root_not_published"] = True

    args.out_dir.mkdir(parents=True, exist_ok=True)
    interval_path = args.out_dir / "b59_2020_office_subtotal_15min.csv"
    monthly_path = args.out_dir / "b59_2020_monthly_records.csv"
    manifest_path = args.out_dir / "b59_2020_target_manifest.json"
    interval.to_csv(interval_path, index_label="timestamp")
    monthly.to_csv(monthly_path, index_label="month")
    manifest = {
        "schema": "vibe23.b59_calibration_target.v1",
        "claim_boundary": "derived office electrical subtotal; not utility bills or whole-building electricity",
        "record_year": 2020,
        "record_count": int(len(monthly)),
        "bindings": {"path": str(args.bindings), "sha256": sha256_file(args.bindings)},
        "provenance": provenance,
        "outputs": {
            "interval": {"path": str(interval_path), "sha256": sha256_file(interval_path), "rows": int(len(interval))},
            "monthly": {"path": str(monthly_path), "sha256": sha256_file(monthly_path), "rows": int(len(monthly))},
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "monthly_records": len(monthly), "coverage_pass": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
