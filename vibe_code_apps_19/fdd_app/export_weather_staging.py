#!/usr/bin/env python3
"""Stage weather reference CSV for Rust Parquet ingest (Open-Meteo / WEATHER equipment)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parent
_BACKEND = _APP / "backend"
_ROOT = _APP.parent
for p in (_BACKEND, _ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pandas as pd

import cookbook_engine as ce  # noqa: E402
from shared.data_config import get_config  # noqa: E402


def export_weather_staging(out_dir: Path | None = None) -> dict:
    """Write columns.csv + history_wide.csv for Rust ``ingest_weather_tree``."""
    from haystack_rdf.resolver import get_resolver

    out = out_dir or (_ROOT / ".cache" / "weather_staging")
    out.mkdir(parents=True, exist_ok=True)
    wx = ce.load_weather(get_resolver())
    if wx is None or wx.empty or "wx_oa_t" not in wx.columns:
        return {"ok": False, "reason": "weather not available"}

    cfg = get_config()
    df = pd.DataFrame()
    ts = pd.to_datetime(wx["timestamp"])
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize(cfg.site_timezone(), ambiguous="NaT", nonexistent="NaT")
    df["timestamp_utc"] = ts.dt.tz_convert("UTC").dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    df["outside_air_temp_f"] = pd.to_numeric(wx["wx_oa_t"], errors="coerce")
    if "wx_oa_h" in wx.columns:
        df["relative_humidity_pct"] = pd.to_numeric(wx["wx_oa_h"], errors="coerce")

    hist = out / "history_wide.csv"
    df.to_csv(hist, index=False)
    cols = out / "columns.csv"
    cols.write_text(
        "col,point_role\noutside_air_temp_f,outside_air_temp\nrelative_humidity_pct,oa_humidity\n",
        encoding="utf-8",
    )
    return {"ok": True, "rows": len(df), "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    out = Path(args.out) if args.out else None
    result = export_weather_staging(out)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
