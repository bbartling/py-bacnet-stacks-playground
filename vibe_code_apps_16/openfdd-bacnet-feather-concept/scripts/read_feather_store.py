#!/usr/bin/env python3
"""Load openfdd-bacnet-feather-concept Feather shards into a pandas DataFrame.

Works on Linux (bench) and Windows after you copy the `data/feather_store` folder.

Install (once):
    pip install -r requirements-pandas.txt

Examples:
    python scripts/read_feather_store.py
    python scripts/read_feather_store.py --store data/feather_store --csv out.csv
    python scripts/read_feather_store.py --store C:\\Users\\you\\Downloads\\feather_store
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def load_feather_store(store_dir: Path):
    """Return a pandas DataFrame of all `*.feather` shards under store_dir."""
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit(
            "pandas is required. Install with:\n  pip install -r requirements-pandas.txt"
        ) from exc

    store_dir = store_dir.expanduser().resolve()
    if not store_dir.is_dir():
        raise SystemExit(f"store directory not found: {store_dir}")

    files = sorted(store_dir.glob("*.feather"))
    if not files:
        print(f"No .feather files in {store_dir}", file=sys.stderr)
        return pd.DataFrame()

    frames = []
    for path in files:
        try:
            frames.append(pd.read_feather(path))
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: skip {path.name}: {exc}", file=sys.stderr)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    if "ts_utc" in df.columns:
        df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
        subset = [
            c
            for c in ("ts_utc", "device_instance", "object_type", "object_instance", "point_name")
            if c in df.columns
        ]
        if subset:
            df = df.sort_values("ts_utc").drop_duplicates(subset=subset, keep="last")
        else:
            df = df.sort_values("ts_utc")
    return df.reset_index(drop=True)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store",
        type=Path,
        default=root / "data" / "feather_store",
        help="folder of *.feather shards (default: data/feather_store)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="optional path to write a CSV export",
    )
    parser.add_argument(
        "--head",
        type=int,
        default=20,
        help="print first N rows (0 = all)",
    )
    args = parser.parse_args()

    df = load_feather_store(args.store)
    print(f"rows={len(df)}  columns={list(df.columns)}")
    if df.empty:
        return 1

    if args.head and args.head > 0:
        print(df.head(args.head).to_string(index=False))
    else:
        print(df.to_string(index=False))

    if args.csv is not None:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.csv, index=False)
        print(f"\nwrote {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
