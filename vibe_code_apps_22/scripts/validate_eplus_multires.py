#!/usr/bin/env python
"""CLI: multi-resolution EnergyPlus validation → JSON + optional plots.

Uses the authoritative ``ml/eplus_multires_metrics`` engine. Does not invent
lag shifts. Labels partial-year monthly calibration when n < 12.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
for p in (_APP, _ML, _APP / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from lakeside.paths import site_root  # noqa: E402
from eplus_native.align import (  # noqa: E402
    aggregate_5min_to_15min_mean,
    aggregate_5min_to_hourly_mean,
    parse_eplus_csv_timestamp,
)
from eplus_native.extract import load_timestep_proxy_kw  # noqa: E402
from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_multires_metrics import (  # noqa: E402
    build_validation_document,
    cross_correlation_lags,
    resolution_block,
)
from eplus_gl14 import nmbe_cvrmse  # noqa: E402


def _load_modeled(sim: Path) -> pd.DataFrame:
    ts = load_timestep_proxy_kw(sim, interval_hours=0.25)
    rows = []
    for _, r in ts.iterrows():
        stamp = str(r["eplus_stamp"])
        month = int(stamp.split("/")[0]) if "/" in stamp else 1
        year = 2025 if month >= 8 else 2026
        dt = parse_eplus_csv_timestamp(stamp, year_hint=year)
        if dt is None:
            continue
        rows.append(
            {
                "timestamp_utc": dt.astimezone(__import__("datetime").timezone.utc),
                "kw_mod": float(r["site_electric_proxy_kw"]),
            }
        )
    mod = pd.DataFrame(rows)
    if mod.empty:
        return mod
    mod["timestamp_utc"] = pd.to_datetime(mod["timestamp_utc"], utc=True)
    return mod


def _monthly_from_scorecard(root: Path) -> dict | None:
    sc_path = root / "eplus" / "dsm_native" / "phase1" / "scorecard_after_dsm_v1.json"
    elig = root / "eplus" / "models" / "staged" / "DSM_ELIGIBLE.json"
    gl14 = None
    if sc_path.is_file():
        sc = json.loads(sc_path.read_text(encoding="utf-8"))
        gl14 = sc.get("gl14") or {}
    elif elig.is_file():
        e = json.loads(elig.read_text(encoding="utf-8"))
        gl14 = {
            "n": None,
            "nmbe_pct": e.get("nmbe_pct"),
            "cvrmse_pct": e.get("cvrmse_pct"),
        }
    if not gl14:
        return None
    n = int(gl14.get("n") or 0)
    # Prefer recomputing if monthly CSV exists
    obs_csv = root / "reports" / "eplus" / "observed_monthly_utility.csv"
    if obs_csv.is_file() and "simulated" in pd.read_csv(obs_csv, nrows=1).columns:
        df = pd.read_csv(obs_csv)
        if {"observed", "simulated"}.issubset(df.columns) or {
            "obs_kwh",
            "sim_kwh",
        }.issubset(df.columns):
            ocol = "observed" if "observed" in df.columns else "obs_kwh"
            scol = "simulated" if "simulated" in df.columns else "sim_kwh"
            return resolution_block(df[ocol], df[scol], resolution="monthly")
    # Fall back to scorecard numbers but stamp n/p honestly
    block = {
        "resolution": "monthly",
        "status": "pass" if (elig.is_file() and json.loads(elig.read_text()).get("gl14_status") == "pass") else "fail",
        "n": n,
        "p": 1,
        "nmbe_pct": gl14.get("nmbe_pct"),
        "cvrmse_pct": gl14.get("cvrmse_pct"),
        "mean_obs": gl14.get("mean_obs"),
        "gates": {"nmbe_abs_max_pct": 5.0, "cvrmse_max_pct": 15.0},
        "labeled_as_gl14": True,
        "partial_year_monthly": 0 < n < 12,
        "formula": "from scorecard (engine preferred when monthly CSV present)",
        "distance_to_gate": None,
    }
    # Re-gate with engine thresholds if numbers present
    if block["nmbe_pct"] is not None and block["cvrmse_pct"] is not None:
        from eplus_multires_metrics import gate_monthly

        block["status"] = gate_monthly(block)
        from eplus_multires_metrics import gl14_distance

        block["distance_to_gate"] = gl14_distance(block)
    return block


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: site reports/eplus/multires)",
    )
    ap.add_argument("--plots", action="store_true", help="Write diagnostic plots")
    args = ap.parse_args(argv)

    os.environ.setdefault(
        "LAKESIDE_SITE_ROOT",
        r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
    )
    root = site_root()
    out = args.out or (root / "reports" / "eplus" / "multires")
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "plots"
    if args.plots:
        plot_dir.mkdir(parents=True, exist_ok=True)

    meas_path = root / "utilities" / "demand_interval_kw.csv"
    if not meas_path.is_file():
        print(f"missing measured demand {meas_path}", file=sys.stderr)
        return 2
    meas = pd.read_csv(meas_path)
    hourly_m = aggregate_5min_to_hourly_mean(meas, ts_col="timestamp_utc", kw_col="kw_demand")
    q15_m = aggregate_5min_to_15min_mean(meas, ts_col="timestamp_utc", kw_col="kw_demand")

    sim = root / "eplus" / "dsm_native" / "runs" / "dsm_repair_v1_full" / "sim"
    if not sim.is_dir():
        print(f"missing repaired sim {sim}", file=sys.stderr)
        return 2
    mod = _load_modeled(sim)
    if mod.empty:
        print("no modeled rows", file=sys.stderr)
        return 1

    mod_h = (
        mod.set_index("timestamp_utc")["kw_mod"]
        .resample("1h", label="right", closed="right")
        .mean()
        .rename("kw_mod")
        .to_frame()
        .reset_index()
    )
    aligned = hourly_m.merge(mod_h, on="timestamp_utc", how="inner").rename(
        columns={"kw_mean": "kw_meas"}
    ).dropna(subset=["kw_meas", "kw_mod"])

    mod_15 = (
        mod.set_index("timestamp_utc")["kw_mod"]
        .resample("15min", label="right", closed="right")
        .mean()
        .rename("kw_mod")
        .to_frame()
        .reset_index()
    )
    aligned_15 = q15_m.merge(mod_15, on="timestamp_utc", how="inner").rename(
        columns={"kw_mean": "kw_meas"}
    ).dropna(subset=["kw_meas", "kw_mod"])

    hourly_block = resolution_block(
        aligned["kw_meas"], aligned["kw_mod"], resolution="hourly"
    )
    q15_block = resolution_block(
        aligned_15["kw_meas"], aligned_15["kw_mod"], resolution="15min"
    )
    monthly_block = _monthly_from_scorecard(root)

    xcorr = cross_correlation_lags(aligned["kw_meas"], aligned["kw_mod"], max_lag=24)
    # Interval count table
    interval_counts = {
        "n_hourly_aligned": int(len(aligned)),
        "n_15min_aligned": int(len(aligned_15)),
        "n_monthly": (monthly_block or {}).get("n"),
        "hourly_span_utc": [
            str(aligned["timestamp_utc"].min()) if len(aligned) else None,
            str(aligned["timestamp_utc"].max()) if len(aligned) else None,
        ],
    }

    ptr = root / "eplus" / "models" / "staged" / "DSM_ELIGIBLE.json"
    elig = json.loads(ptr.read_text(encoding="utf-8")) if ptr.is_file() else {}
    epw = root / "eplus" / "weather" / "madison_amy_202508_202607.epw"

    alignment = {
        "policy": {
            "measured_tz": "UTC",
            "modeled_tz": "E+ LST → UTC via fixed CST−6 (no Chicago DST on E+ stamps)",
            "timestamp": "interval end",
            "lag_shifts_applied": False,
        },
        "cross_correlation": {
            "best_lag_h": xcorr.get("best_lag"),
            "best_corr": xcorr.get("best_corr"),
            "note": xcorr.get("note"),
        },
        "interval_counts": interval_counts,
        "dst_note": "Measured series may cross DST; E+ stamps never use DST",
    }

    doc = build_validation_document(
        monthly=monthly_block,
        hourly=hourly_block,
        q15=q15_block,
        physics_label=elig.get("honesty")
        or "IdealLoads + fixed-COP electrical proxy (not GSHP/GLHE)",
        idf_sha256=elig.get("staged_sha256"),
        epw_sha256=sha256_file(epw).upper() if epw.is_file() else None,
        alignment=alignment,
        extra={
            "legacy_gl14_helper_check": nmbe_cvrmse(
                aligned["kw_meas"].tolist()[:100],
                aligned["kw_mod"].tolist()[:100],
            )
            if len(aligned) >= 100
            else None
        },
    )

    out_json = out / "eplus_multires_validation.json"
    out_json.write_text(json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8")
    # Mirror to desktop artifacts for UI badges
    desk = _APP / "desktop" / "artifacts" / "mvm"
    desk.mkdir(parents=True, exist_ok=True)
    (desk / "eplus_multires_validation.json").write_text(
        out_json.read_text(encoding="utf-8"), encoding="utf-8"
    )

    if args.plots and len(aligned):
        # Winter week overlay (first full week in Jan if present)
        a = aligned.copy()
        a["ts"] = pd.to_datetime(a["timestamp_utc"], utc=True)
        fig, ax = plt.subplots(figsize=(10, 4))
        sample = a.iloc[: 24 * 7]
        ax.plot(sample["ts"], sample["kw_meas"], label="measured", lw=1)
        ax.plot(sample["ts"], sample["kw_mod"], label="modeled", lw=1, alpha=0.8)
        ax.set_title("Aligned hourly — first week sample (no lag shift)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(plot_dir / "hourly_week_overlay.png", dpi=120)
        plt.close(fig)

        # Xcorr bar
        lags = xcorr.get("lags") or {}
        if lags:
            fig, ax = plt.subplots(figsize=(8, 3))
            keys = sorted(int(k) for k in lags)
            ax.bar(keys, [lags[str(k)] for k in keys], width=0.8)
            ax.axvline(0, color="k", lw=0.5)
            ax.set_xlabel("lag (h)")
            ax.set_ylabel("corr")
            ax.set_title("Cross-correlation −24..+24 h (diagnostic; no auto-shift)")
            fig.tight_layout()
            fig.savefig(plot_dir / "xcorr_lags.png", dpi=120)
            plt.close(fig)

    print(json.dumps(doc["overall"], indent=2))
    print(f"wrote {out_json}")
    return 0 if doc["overall"]["hourly_pass"] and doc["overall"]["monthly_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
