"""Local Feather cache for historian CSV → pandas loads (mtime-invalidated)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .timeseries_grid import FIVE_MINUTES_SEC, maybe_downsample_to_5min

_CACHE_ROOT = Path(__file__).resolve().parent.parent / "csv_fdd_dashboard" / ".cache" / "feather"


def _cache_paths(csv_path: Path) -> tuple[Path, Path]:
    key = hashlib.sha256(str(csv_path.resolve()).encode()).hexdigest()[:20]
    base = _CACHE_ROOT / key
    return base.with_suffix(".meta.json"), base.with_suffix(".feather")


def _normalize_history_df(df: pd.DataFrame, tz: str) -> pd.DataFrame:
    if "timestamp" not in df.columns and "timestamp_utc" in df.columns:
        df = df.copy()
        df["timestamp"] = df["timestamp_utc"]
    if "timestamp" in df.columns:
        df = df.copy()
        df["timestamp_local"] = df["timestamp"].dt.tz_convert(tz)
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def _prepare_history_df(df: pd.DataFrame, tz: str) -> pd.DataFrame:
    df = _normalize_history_df(df, tz)
    df = maybe_downsample_to_5min(df, ts_col="timestamp", target_sec=FIVE_MINUTES_SEC)
    if "timestamp" in df.columns:
        df = df.copy()
        df["timestamp_local"] = df["timestamp"].dt.tz_convert(tz)
    return df


def read_history_csv(csv_path: Path, *, tz: str) -> pd.DataFrame:
    """Load history_wide.csv; reuse Feather sidecar when CSV mtime unchanged."""
    meta_path, feather_path = _cache_paths(csv_path)
    try:
        csv_mtime = csv_path.stat().st_mtime_ns
        if meta_path.is_file() and feather_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("mtime_ns") == csv_mtime and meta.get("source") == str(csv_path):
                df = pd.read_feather(feather_path)
                if "effective_poll_seconds" not in df.attrs:
                    df.attrs["effective_poll_seconds"] = meta.get("effective_poll_seconds", FIVE_MINUTES_SEC)
                return df
    except (OSError, json.JSONDecodeError, ImportError, ValueError):
        pass

    df = pd.read_csv(csv_path, parse_dates=["timestamp_utc"], low_memory=False)
    df = _prepare_history_df(df, tz)
    poll = int(df.attrs.get("effective_poll_seconds", FIVE_MINUTES_SEC))

    try:
        _CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        df.to_feather(feather_path)
        meta_path.write_text(
            json.dumps({
                "mtime_ns": csv_path.stat().st_mtime_ns,
                "source": str(csv_path),
                "effective_poll_seconds": poll,
            }),
            encoding="utf-8",
        )
    except (OSError, ImportError, ValueError):
        pass

    return df
