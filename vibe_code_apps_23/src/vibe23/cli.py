from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .download import download_dataset
from .ingest import aggregate_power_kw, build_inventory, load_point_csv
from .metrics import score_calibration


def _download(args: argparse.Namespace) -> None:
    print(json.dumps(download_dataset(Path(args.data_dir), force=args.force), indent=2))


def _inventory(args: argparse.Namespace) -> None:
    frame = build_inventory(Path(args.root))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    print(f"wrote {len(frame)} rows -> {out}")


def _aggregate(args: argparse.Namespace) -> None:
    series = load_point_csv(Path(args.csv), args.timestamp_column, args.value_column)
    frame = aggregate_power_kw(series, args.rule, max_gap_factor=args.max_gap_factor)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index_label="timestamp")
    print(f"wrote {len(frame)} rows -> {out}")


def _score(args: argparse.Namespace) -> None:
    frame = pd.read_csv(args.csv)
    result = score_calibration(frame[args.measured_column], frame[args.simulated_column], args.interval, p=args.parameters)
    print(json.dumps(result.as_dict(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="vibe23", description="LBNL Building 59 calibration utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("download", help="Download and safely extract the Dryad dataset")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=_download)

    p = sub.add_parser("inventory", help="Inventory CSV files and candidate columns")
    p.add_argument("--root", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=_inventory)

    p = sub.add_parser("aggregate-power", help="Integrate a sampled kW point into energy/peak targets")
    p.add_argument("--csv", required=True)
    p.add_argument("--timestamp-column")
    p.add_argument("--value-column")
    p.add_argument("--rule", default="1h")
    p.add_argument("--max-gap-factor", type=float, default=4.0)
    p.add_argument("--out", required=True)
    p.set_defaults(func=_aggregate)

    p = sub.add_parser("score", help="Compute Guideline-14-style calibration metrics")
    p.add_argument("--csv", required=True)
    p.add_argument("--measured-column", default="measured")
    p.add_argument("--simulated-column", default="simulated")
    p.add_argument("--interval", choices=["monthly", "hourly"], required=True)
    p.add_argument("--parameters", type=int, default=1)
    p.set_defaults(func=_score)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
