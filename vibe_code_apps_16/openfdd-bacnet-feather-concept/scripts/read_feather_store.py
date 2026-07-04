#!/usr/bin/env python3
"""Load openfdd-bacnet-feather-concept telemetry into a pandas DataFrame.

Long-format store ready for action rules / live building analytics:

    ts_utc, device_name, device_instance, object_type, object_instance,
    point_name, present_value, units

Enriched columns (``enrich_dataframe``):

    series, series_key, point_key, value_fmt, ts_local

Install (once):
    pip install -r requirements-pandas.txt

Examples:
    python scripts/read_feather_store.py
    python scripts/read_feather_store.py --by-device --latest
    python scripts/read_feather_store.py --device BENS-BENCHTEST-BOX --since 2026-07-04T17:42:13Z
    python scripts/read_feather_store.py --plot --points OA-T,SA-T,ZoneTemp
    python scripts/read_feather_store.py --wide --csv action_ready.csv

Exports (default unless ``--no-export``):
    data/exports/telemetry_long.csv
    data/exports/telemetry_latest.csv   (with ``--latest``)
    data/exports/telemetry_wide.csv     (with ``--wide``)
    data/exports/telemetry_plot.png     (with ``--plot``)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


def _require_pandas():
    try:
        import pandas as pd

        return pd
    except ImportError as exc:
        raise SystemExit(
            "pandas is required. Install with:\n  pip install -r requirements-pandas.txt"
        ) from exc


def load_feather_store(store: Path):
    pd = _require_pandas()

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


def enrich_dataframe(df, *, tz: str = "America/Chicago"):
    """Return an analysis-ready long DataFrame with human-friendly columns."""
    pd = _require_pandas()

    if df.empty:
        return df

    out = df.copy()
    out["present_value"] = pd.to_numeric(out["present_value"], errors="coerce")
    out["units"] = out["units"].fillna("").astype(str)

    out["series_key"] = (
        out["device_name"].astype(str) + "::" + out["point_name"].astype(str)
    )
    out["series"] = (
        out["device_name"].astype(str) + " · " + out["point_name"].astype(str)
    )
    out["point_key"] = (
        out["object_type"].astype(str) + ":" + out["object_instance"].astype(str)
    )

    def _fmt(row) -> str:
        val = row["present_value"]
        units = row["units"].strip()
        if pd.isna(val):
            return "n/a"
        text = f"{val:.4g}"
        return f"{text} {units}".strip()

    out["value_fmt"] = out.apply(_fmt, axis=1)

    if "ts_utc" in out.columns:
        try:
            out["ts_local"] = out["ts_utc"].dt.tz_convert(tz)
        except Exception:  # noqa: BLE001
            out["ts_local"] = out["ts_utc"]

    preferred = [
        "ts_utc",
        "ts_local",
        "device_name",
        "device_instance",
        "point_name",
        "series",
        "series_key",
        "present_value",
        "units",
        "value_fmt",
        "object_type",
        "object_instance",
        "point_key",
    ]
    cols = [c for c in preferred if c in out.columns]
    rest = [c for c in out.columns if c not in cols]
    out = out[cols + rest].sort_values(["ts_utc", "series_key"]).reset_index(drop=True)
    return out


def filter_dataframe(
    df,
    *,
    device: str | None = None,
    points: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
):
    pd = _require_pandas()
    out = df.copy()
    if device:
        out = out[out["device_name"].str.lower() == device.lower()]
    if points:
        wanted = {p.strip().lower() for p in points if p.strip()}
        out = out[out["point_name"].str.lower().isin(wanted)]
    if since:
        out = out[out["ts_utc"] >= pd.Timestamp(since)]
    if until:
        out = out[out["ts_utc"] <= pd.Timestamp(until)]
    return out.reset_index(drop=True)


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
    pd = _require_pandas()

    snap = latest_snapshot(df)
    if snap.empty:
        return snap
    return snap.pivot_table(
        index="device_name",
        columns="point_name",
        values="present_value",
        aggfunc="last",
    )


def summarize_dataframe(df) -> str:
    """Compact text summary for terminal output."""
    pd = _require_pandas()

    if df.empty:
        return "rows=0"

    lines = [
        f"rows={len(df)}  columns={list(df.columns)}",
        f"time_range={df['ts_utc'].min()} → {df['ts_utc'].max()}",
        f"devices={sorted(df['device_name'].dropna().unique())}",
        f"series={df['series_key'].nunique() if 'series_key' in df.columns else 'n/a'}",
    ]
    if "present_value" in df.columns:
        stats = df["present_value"].describe()
        lines.append(
            "present_value: "
            f"min={stats['min']:.4g} max={stats['max']:.4g} mean={stats['mean']:.4g}"
        )
    return "\n".join(lines)


def export_csv(view, path: Path, *, index: bool = False) -> Path:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    view.to_csv(path, index=index)
    return path


def default_export_paths(export_dir: Path, *, latest: bool, wide: bool, plot: bool) -> dict[str, Path]:
    export_dir = export_dir.expanduser().resolve()
    paths = {"long": export_dir / "telemetry_long.csv"}
    if latest:
        paths["latest"] = export_dir / "telemetry_latest.csv"
    if wide:
        paths["wide"] = export_dir / "telemetry_wide.csv"
    if plot:
        paths["plot"] = export_dir / "telemetry_plot.png"
    return paths


def plot_timeseries(
    df,
    *,
    out: Path | None = None,
    title: str = "BACnet telemetry",
    show: bool = False,
    figsize: tuple[float, float] = (12.0, 6.0),
) -> Path | None:
    """Plot present_value vs time, one line per series."""
    pd = _require_pandas()

    if df.empty:
        print("WARN: no rows to plot", file=sys.stderr)
        return None

    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit(
            "matplotlib is required for --plot. Install with:\n"
            "  pip install -r requirements-pandas.txt"
        ) from exc

    plot_df = df.sort_values("ts_utc")
    series_col = "series" if "series" in plot_df.columns else "series_key"
    groups = list(plot_df.groupby(series_col))

    fig, ax = plt.subplots(figsize=figsize)
    for label, group in groups:
        ax.plot(
            group["ts_utc"],
            group["present_value"],
            marker="o",
            markersize=2.5,
            linewidth=1.2,
            label=label,
        )

    ax.set_title(title)
    ax.set_xlabel("UTC time")
    ax.set_ylabel("present_value")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8, framealpha=0.9)
    fig.autofmt_xdate()
    fig.tight_layout()

    saved: Path | None = None
    if out is not None:
        out = out.expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150)
        saved = out
        print(f"wrote plot {out}")

    if show:
        plt.show()
    else:
        plt.close(fig)

    return saved


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store",
        type=Path,
        default=root / "data" / "feather_store" / "telemetry.feather",
        help="telemetry.feather path or folder",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=root / "data" / "exports",
        help="folder for auto CSV/plot exports (default: data/exports)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="optional extra CSV path (in addition to auto export)",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="skip default CSV exports to --export-dir",
    )
    parser.add_argument("--head", type=int, default=20, help="print first N rows (0=all)")
    parser.add_argument("--device", type=str, default=None, help="filter device_name")
    parser.add_argument(
        "--points",
        type=str,
        default=None,
        help="comma-separated point_name filter (e.g. OA-T,SA-T,ZoneTemp)",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="ISO timestamp lower bound (e.g. 2026-07-04T17:42:13Z)",
    )
    parser.add_argument(
        "--until",
        type=str,
        default=None,
        help="ISO timestamp upper bound",
    )
    parser.add_argument(
        "--tz",
        type=str,
        default="America/Chicago",
        help="timezone for ts_local column (default: America/Chicago)",
    )
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
    parser.add_argument(
        "--plot",
        action="store_true",
        help="save a matplotlib time-series plot (needs matplotlib)",
    )
    parser.add_argument(
        "--plot-out",
        type=Path,
        default=None,
        help="plot PNG path (default: data/exports/telemetry_plot.png)",
    )
    parser.add_argument(
        "--show-plot",
        action="store_true",
        help="display plot interactively (implies GUI backend)",
    )
    args = parser.parse_args()

    point_list = [p.strip() for p in args.points.split(",")] if args.points else None

    raw = load_feather_store(args.store)
    if raw.empty:
        print("rows=0")
        return 1

    df = enrich_dataframe(
        filter_dataframe(
            raw,
            device=args.device,
            points=point_list,
            since=args.since,
            until=args.until,
        ),
        tz=args.tz,
    )
    if df.empty:
        print("rows=0 after filters")
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
        print(summarize_dataframe(df))

    if args.head and args.head > 0 and not args.wide:
        print(view.head(args.head).to_string(index=False))
    elif args.wide:
        print(view.to_string())
    elif args.head == 0:
        print(view.to_string())

    exports: list[Path] = []
    if not args.no_export:
        paths = default_export_paths(
            args.export_dir,
            latest=args.latest,
            wide=args.wide,
            plot=args.plot,
        )
        exports.append(export_csv(df, paths["long"]))
        if args.latest:
            exports.append(export_csv(latest_snapshot(df), paths["latest"]))
        if args.wide:
            exports.append(export_csv(view, paths["wide"], index=True))

    if args.csv is not None:
        exports.append(export_csv(view, args.csv, index=args.wide))

    if exports:
        print("\n=== exports ===")
        for path in exports:
            print(f"  {path}")

    if args.plot:
        plot_out = args.plot_out or (
            args.export_dir.expanduser().resolve() / "telemetry_plot.png"
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        title = f"BACnet telemetry ({stamp})"
        if args.device:
            title += f" — {args.device}"
        if point_list:
            title += f" — {', '.join(point_list)}"
        plot_timeseries(
            df,
            out=plot_out,
            title=title,
            show=args.show_plot,
        )

    if not args.device:
        names = {str(n) for n in df["device_name"].dropna().unique() if str(n).strip()}
        if not names:
            print("\nWARN: no device_name values in store", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
