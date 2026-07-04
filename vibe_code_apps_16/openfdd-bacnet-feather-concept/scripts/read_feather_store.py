#!/usr/bin/env python3
"""Load openfdd-bacnet-feather-concept telemetry into a pandas DataFrame.

Long-format store ready for action rules / live building analytics:

    ts_utc, device_name, device_instance, object_type, object_instance,
    point_name, present_value, units

Install (once):
    pip install -r requirements-pandas.txt

Examples:
    python scripts/read_feather_store.py
    python scripts/read_feather_store.py --by-device
    python scripts/read_feather_store.py --device BensFakeAhu --latest
    python scripts/read_feather_store.py --wide --csv action_ready.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def load_feather_store(store: Path):
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit(
            "pandas is required. Install with:\n  pip install -r requirements-pandas.txt"
        ) from exc

    store = store.expanduser().resolve()

    if store.is_file():
        files = [store]
    elif store.is_dir():
        preferred = store / "telemetry.feather"
        files = [preferred] if preferred.is_file() else sorted(store.glob("*.feather"))
    else:
        raise SystemExit(f"store path not found: {store}")

    if not files:
        print(f"No .feather files in {store}", file=sys.stderr)
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
    if "device_name" not in df.columns:
        df["device_name"] = ""

    subset = [
        c
        for c in (
            "ts_utc",
            "device_name",
            "device_instance",
            "object_type",
            "object_instance",
            "point_name",
        )
        if c in df.columns
    ]
    if subset:
        df = df.sort_values("ts_utc").drop_duplicates(subset=subset, keep="last")
    elif "ts_utc" in df.columns:
        df = df.sort_values("ts_utc")
    return df.reset_index(drop=True)


def latest_snapshot(df):
    """One row per (device_name, point_name) — action-ready current values."""
    if df.empty:
        return df
    keys = [c for c in ("device_name", "point_name") if c in df.columns]
    return (
        df.sort_values("ts_utc")
        .groupby(keys, as_index=False)
        .tail(1)
        .sort_values(keys)
        .reset_index(drop=True)
    )


def wide_snapshot(df):
    """Pivot latest values: index=device_name, columns=point_name."""
    import pandas as pd

    snap = latest_snapshot(df)
    if snap.empty:
        return snap
    return snap.pivot_table(
        index="device_name",
        columns="point_name",
        values="present_value",
        aggfunc="last",
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store",
        type=Path,
        default=root / "data" / "feather_store" / "telemetry.feather",
        help="telemetry.feather path or folder",
    )
    parser.add_argument("--csv", type=Path, default=None, help="write CSV export")
    parser.add_argument("--head", type=int, default=20, help="print first N rows (0=all)")
    parser.add_argument("--device", type=str, default=None, help="filter device_name")
    parser.add_argument(
        "--by-device",
        action="store_true",
        help="print row counts and point lists per device",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="one row per (device, point) — current values only",
    )
    parser.add_argument(
        "--wide",
        action="store_true",
        help="pivot latest values (device × point) for action rules",
    )
    args = parser.parse_args()

    df = load_feather_store(args.store)
    if df.empty:
        print("rows=0")
        return 1

    if args.device:
        df = df[df["device_name"].str.lower() == args.device.lower()].copy()
        if df.empty:
            print(f"no rows for device_name={args.device!r}")
            return 1

    if args.by_device:
        print("=== by device ===")
        for name, g in df.groupby("device_name"):
            points = sorted(g["point_name"].unique())
            print(
                f"{name}: rows={len(g)} devices_id={sorted(g['device_instance'].unique())} "
                f"points={len(points)} {points}"
            )
        print()

    view = df
    if args.wide:
        view = wide_snapshot(df)
        print(f"wide devices={list(view.index)} points={list(view.columns)}")
    elif args.latest:
        view = latest_snapshot(df)
        print(f"latest rows={len(view)}")
    else:
        print(f"rows={len(df)}  columns={list(df.columns)}")
        devices = sorted(df["device_name"].dropna().unique())
        print(f"devices={devices}")

    if args.head and args.head > 0 and not args.wide:
        print(view.head(args.head).to_string(index=False))
    else:
        print(view.to_string())

    if args.csv is not None:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        view.to_csv(args.csv, index=args.wide)
        print(f"\nwrote {args.csv}")

    # Exit 0 only if both expected lab devices appear (when not filtering).
    if not args.device:
        names = {str(n).lower() for n in df["device_name"].dropna().unique()}
        need = {"bens-bench", "bensfakeahu"}
        missing = need - names
        if missing:
            print(f"\nWARN: missing devices in store: {sorted(missing)}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
