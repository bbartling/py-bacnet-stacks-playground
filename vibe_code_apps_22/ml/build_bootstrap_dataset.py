"""Build BAS + synthetic heating DSM hourly parquet for ML training.

Reads:
  reports/demand_vs_web_weather_hourly.csv
  clean_data/LAKESIDE_ES/weather/history_wide.csv (RH / GHI hourly means)

Writes:
  ml/artifacts/heating_dsm_bootstrap_hourly.parquet
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ML = Path(__file__).resolve().parent
_ROOT = _ML.parent
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from artifact_paths import (  # noqa: E402
    bootstrap_parquet_path,
    lakeside_data_root,
    default_artifact_dir,
    demand_hourly_csv,
    weather_history_csv,
)
from seed_proxy_scenarios import expand_day_with_strategies  # noqa: E402

TZ = "America/Chicago"


def _load_hourly_demand(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    ts = pd.to_datetime(df["hour_utc"], utc=True)
    local = ts.dt.tz_convert(TZ)
    out = pd.DataFrame(
        {
            "timestamp_utc": ts,
            "timestamp_local": local,
            "facility_kw_bas": pd.to_numeric(df["kw_avg"], errors="coerce"),
            "oat_f": pd.to_numeric(df["oat_f"], errors="coerce"),
            "day_type": df["day_type"].astype(str),
        }
    )
    out["hour_ending"] = (local.dt.hour + 1).clip(upper=24)  # HE 1..24; midn→24
    # Prefer calendar hour 0..23 as HE = hour of stamp + 1 is odd for ML;
    # use local hour as hour_ending (0–23) for consistency with vibe21-ish HE.
    out["hour_ending"] = local.dt.hour.astype(int)
    out["day"] = local.dt.strftime("%Y-%m-%d")
    out["month"] = local.dt.month.astype(int)
    out["doy"] = local.dt.dayofyear.astype(int)
    out["dow"] = local.dt.day_name()
    out["is_weekend"] = (local.dt.dayofweek >= 5).astype(float)
    # Generic K12 occupied Mon–Fri [07, 16)
    out["occupied"] = (
        (out["is_weekend"] < 0.5)
        & (out["hour_ending"] >= 7)
        & (out["hour_ending"] < 16)
    ).astype(float)
    return out.dropna(subset=["facility_kw_bas", "oat_f"])


def _load_weather_hourly(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=["day", "hour_ending", "rh_pct", "ghi"])
    w = pd.read_csv(path)
    ts = pd.to_datetime(w["timestamp_utc"], utc=True)
    local = ts.dt.tz_convert(TZ)
    w = w.copy()
    w["day"] = local.dt.strftime("%Y-%m-%d")
    w["hour_ending"] = local.dt.hour.astype(int)
    w["rh_pct"] = pd.to_numeric(w["web-outside-air-humidity"], errors="coerce")
    w["ghi"] = pd.to_numeric(w["shortwave_radiation_wm2"], errors="coerce")
    g = (
        w.groupby(["day", "hour_ending"], as_index=False)
        .agg(rh_pct=("rh_pct", "mean"), ghi=("ghi", "mean"))
    )
    return g


def build_bootstrap(
    *,
    demand_csv: Path,
    weather_csv: Path,
    max_days: int | None = None,
) -> tuple[pd.DataFrame, dict]:
    demand = _load_hourly_demand(demand_csv)
    wx = _load_weather_hourly(weather_csv)
    if len(wx):
        demand = demand.merge(wx, on=["day", "hour_ending"], how="left")
    demand["rh_pct"] = demand["rh_pct"].fillna(50.0)
    demand["ghi"] = demand["ghi"].fillna(0.0)

    days = sorted(demand["day"].unique())
    if max_days is not None:
        days = days[: max_days]

    frames = []
    for d in days:
        day_df = demand.loc[demand["day"] == d].copy()
        if len(day_df) < 20:
            continue
        frames.append(expand_day_with_strategies(day_df))

    if not frames:
        raise RuntimeError("No bootstrap days produced")

    out = pd.concat(frames, ignore_index=True)
    # Day-level peak for cost sheets
    peaks = out.groupby("simulation_id")["facility_kw"].transform("max")
    out["day_peak_kw"] = peaks

    summary = {
        "n_rows": int(len(out)),
        "n_days": int(out["day"].nunique()),
        "n_strategies": int(out["strategy_id"].nunique()),
        "n_simulations": int(out["simulation_id"].nunique()),
        "provenance": "BAS_BOOTSTRAP_PROXY",
        "demand_csv": str(demand_csv),
        "weather_csv": str(weather_csv),
        "facility_kw_mean": float(out["facility_kw"].mean()),
        "facility_kw_max": float(out["facility_kw"].max()),
    }
    return out, summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--demand-csv",
        type=Path,
        default=None,
        help="Default: <CREEKSIDE>/reports/demand_vs_web_weather_hourly.csv",
    )
    ap.add_argument(
        "--weather-csv",
        type=Path,
        default=None,
        help="Default: <CREEKSIDE>/clean_data/.../weather/history_wide.csv",
    )
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--max-days", type=int, default=None)
    args = ap.parse_args(argv)

    demand = args.demand_csv or demand_hourly_csv()
    weather = args.weather_csv or weather_history_csv()
    out_path = args.out or bootstrap_parquet_path(prefer_full=True)
    # Always write full train set into local artifacts/ when rebuilding
    if args.out is None:
        out_path = default_artifact_dir() / "heating_dsm_bootstrap_hourly.parquet"
    default_artifact_dir().mkdir(parents=True, exist_ok=True)

    if not demand.is_file():
        print(
            f"missing demand CSV: {demand}\n"
            f"Set VIBE22_CREEKSIDE_ROOT to your sp_lakeside checkout "
            f"(resolved root={lakeside_data_root()})",
            file=sys.stderr,
        )
        return 2

    df, summary = build_bootstrap(
        demand_csv=demand,
        weather_csv=weather,
        max_days=args.max_days,
    )
    df.to_parquet(out_path, index=False)
    summary_path = out_path.with_name("bootstrap_summary.json")
    summary["lakeside_root"] = str(lakeside_data_root())
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**summary, "parquet": str(out_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
