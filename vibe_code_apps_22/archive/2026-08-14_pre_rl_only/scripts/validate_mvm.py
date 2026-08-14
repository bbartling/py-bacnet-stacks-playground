#!/usr/bin/env python
"""Measured vs modeled validation (hourly / 15-min / monthly GL14)."""
from __future__ import annotations

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
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from lakeside.paths import site_root  # noqa: E402
from eplus_native.align import (  # noqa: E402
    aggregate_5min_to_15min_mean,
    aggregate_5min_to_hourly_mean,
    cvrmse_pct,
    mae_rmse_mbe,
    parse_eplus_csv_timestamp,
    utc_to_chicago_local,
)
from eplus_native.extract import load_timestep_proxy_kw, to_hourly_mean_kw  # noqa: E402
from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_gl14 import nmbe_cvrmse, pass_fail  # noqa: E402


def main() -> int:
    os.environ.setdefault(
        "LAKESIDE_SITE_ROOT",
        r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
    )
    root = site_root()
    out = root / "reports" / "eplus" / "mvm"
    out.mkdir(parents=True, exist_ok=True)
    desk = _APP / "desktop" / "artifacts" / "mvm"
    desk.mkdir(parents=True, exist_ok=True)

    meas_path = root / "utilities" / "demand_interval_kw.csv"
    meas = pd.read_csv(meas_path)
    assert "timestamp_utc" in meas.columns and "kw_demand" in meas.columns

    hourly_m = aggregate_5min_to_hourly_mean(meas, ts_col="timestamp_utc", kw_col="kw_demand")
    q15_m = aggregate_5min_to_15min_mean(meas, ts_col="timestamp_utc", kw_col="kw_demand")

    sim = root / "eplus" / "dsm_native" / "runs" / "dsm_repair_v1_full" / "sim"
    if not sim.is_dir():
        print(f"missing repaired sim {sim}", file=sys.stderr)
        return 2
    ts = load_timestep_proxy_kw(sim, interval_hours=0.25)
    # Build modeled hourly with Chicago local → UTC
    rows = []
    for _, r in ts.iterrows():
        # AMY spans 2025-08 .. 2026-07 — year from month
        stamp = str(r["eplus_stamp"])
        month = int(stamp.split("/")[0]) if "/" in stamp else 1
        year = 2025 if month >= 8 else 2026
        dt = parse_eplus_csv_timestamp(stamp, year_hint=year)
        if dt is None:
            continue
        rows.append(
            {
                "timestamp_local": dt,
                "timestamp_utc": dt.astimezone(pd.Timestamp.utcnow().tz).tz_convert("UTC")
                if False
                else dt.astimezone(__import__("datetime").timezone.utc),
                "kw_mod": float(r["site_electric_proxy_kw"]),
            }
        )
    mod = pd.DataFrame(rows)
    if mod.empty:
        print("no modeled rows", file=sys.stderr)
        return 1
    mod["timestamp_utc"] = pd.to_datetime(mod["timestamp_utc"], utc=True)
    # Hourly mean of modeled timestep
    mod_h = (
        mod.set_index("timestamp_utc")["kw_mod"]
        .resample("1h", label="right", closed="right")
        .mean()
        .rename("kw_mod")
        .to_frame()
        .reset_index()
    )

    aligned = hourly_m.merge(mod_h, on="timestamp_utc", how="inner")
    aligned = aligned.rename(columns={"kw_mean": "kw_meas"})
    aligned = aligned.dropna(subset=["kw_meas", "kw_mod"])
    aligned.to_csv(out / "aligned_hourly_kw.csv", index=False)
    aligned.to_csv(desk / "aligned_hourly_kw.csv", index=False)

    stats = mae_rmse_mbe(aligned["kw_meas"].to_numpy(), aligned["kw_mod"].to_numpy())
    cv = cvrmse_pct(aligned["kw_meas"].to_numpy(), aligned["kw_mod"].to_numpy())

    # --- 15-min MVM (primary screening resolution) ---
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
    )
    aligned_15 = aligned_15.dropna(subset=["kw_meas", "kw_mod"])
    # exclude design-day-ish zeros / stamp collisions already filtered upstream
    aligned_15.to_csv(out / "aligned_15min_kw.csv", index=False)
    aligned_15.to_csv(desk / "aligned_15min_kw.csv", index=False)
    stats_15 = mae_rmse_mbe(aligned_15["kw_meas"].to_numpy(), aligned_15["kw_mod"].to_numpy())
    cv_15 = cvrmse_pct(aligned_15["kw_meas"].to_numpy(), aligned_15["kw_mod"].to_numpy())
    # peak: daily 15-min max demand error
    a15 = aligned_15.copy()
    a15["day"] = pd.to_datetime(a15["timestamp_utc"], utc=True).dt.tz_convert("America/Chicago").dt.strftime("%Y-%m-%d")
    peak_errs = []
    for _, g in a15.groupby("day"):
        if len(g) < 80:
            continue
        peak_errs.append(float(g["kw_mod"].max() - g["kw_meas"].max()))
    peak_mag_mae = float(np.mean(np.abs(peak_errs))) if peak_errs else float("nan")

    # Monthly utility vs modeled from scorecard
    sc_path = root / "eplus" / "dsm_native" / "phase1" / "scorecard_after_dsm_v1.json"
    monthly = {}
    if sc_path.is_file():
        sc = json.loads(sc_path.read_text(encoding="utf-8"))
        monthly = {
            "gl14": sc.get("gl14"),
            "gl14_status": sc.get("gl14_status"),
            "note": "Monthly utility calibration (separate from interval demand validation)",
        }

    ptr = root / "eplus" / "models" / "staged" / "DSM_ELIGIBLE.json"
    elig = json.loads(ptr.read_text(encoding="utf-8")) if ptr.is_file() else {}
    epw = root / "eplus" / "weather" / "madison_amy_202508_202607.epw"
    summary = {
        "honesty": "Ideal Loads + fixed-COP electrical proxy — not GSHP plant",
        "alignment_policy": {
            "measured_tz": "UTC",
            "modeled_tz": "E+ LST → UTC via fixed CST−6 (no Chicago DST on E+ stamps)",
            "interval_hourly": "hourly mean of 5-min measured vs hourly mean of 15-min modeled",
            "interval_15min": "15-min mean of 5-min measured vs 15-min modeled timestep",
            "timestamp": "interval end",
        },
        "n_hourly": int(stats["n"]),
        "hourly_mae_kw": stats["mae"],
        "hourly_rmse_kw": stats["rmse"],
        "hourly_mbe_kw": stats["mbe"],
        "hourly_nmbe_pct": stats["nmbe_pct"],
        "hourly_cvrmse_pct": cv["cvrmse_pct"],
        "n_15min": int(stats_15["n"]),
        "q15_mae_kw": stats_15["mae"],
        "q15_rmse_kw": stats_15["rmse"],
        "q15_mbe_kw": stats_15["mbe"],
        "q15_nmbe_pct": stats_15["nmbe_pct"],
        "q15_cvrmse_pct": cv_15["cvrmse_pct"],
        "q15_daily_peak_mag_mae_kw": peak_mag_mae,
        "cvrmse_denominator": cv["denominator"],
        "time_span_utc": [
            str(aligned["timestamp_utc"].min()) if len(aligned) else None,
            str(aligned["timestamp_utc"].max()) if len(aligned) else None,
        ],
        "idf_sha256": elig.get("staged_sha256"),
        "epw_sha256": sha256_file(epw) if epw.is_file() else None,
        "heat_cop": 3.5,
        "cool_cop": 4.5,
        "monthly_utility_gl14": monthly,
        "missingness_note": "inner join only; incomplete months dropped; design-day stamps filtered at extract",
    }
    (out / "mvm_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (desk / "mvm_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    # Plots
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(aligned["timestamp_utc"], aligned["kw_meas"], label="measured hourly mean", lw=0.8)
    ax.plot(aligned["timestamp_utc"], aligned["kw_mod"], label="modeled IdealLoads+COP", lw=0.8, alpha=0.8)
    ax.set_ylabel("kW")
    ax.set_title(
        f"Measured vs modeled hourly kW  MAE={stats['mae']:.1f}  RMSE={stats['rmse']:.1f}  NMBE={stats['nmbe_pct']:.2f}%"
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "mvm_hourly_overlay.png", dpi=140)
    fig.savefig(desk / "mvm_hourly_overlay.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(aligned["kw_meas"], aligned["kw_mod"], s=4, alpha=0.3)
    lim = max(aligned["kw_meas"].max(), aligned["kw_mod"].max())
    ax.plot([0, lim], [0, lim], "k--", lw=1)
    ax.set_xlabel("measured kW")
    ax.set_ylabel("modeled kW")
    ax.set_title("Parity (hourly)")
    fig.tight_layout()
    fig.savefig(out / "mvm_parity.png", dpi=140)
    fig.savefig(desk / "mvm_parity.png", dpi=140)
    plt.close(fig)

    # Monthly bars from scorecard
    if sc_path.is_file():
        months = sc.get("monthly") or []
        if months:
            fig, ax = plt.subplots(figsize=(10, 4))
            x = np.arange(len(months))
            ax.bar(x - 0.2, [m["kwh_obs"] for m in months], width=0.4, label="obs utility kWh")
            ax.bar(x + 0.2, [m["kwh_sim"] for m in months], width=0.4, label="sim proxy kWh")
            ax.set_xticks(x)
            ax.set_xticklabels([m["month"] for m in months], rotation=45, ha="right")
            ax.set_title(
                f"Monthly utility GL14  status={sc.get('gl14_status')}  "
                f"NMBE={sc.get('gl14', {}).get('nmbe_pct')}%  CVRMSE={sc.get('gl14', {}).get('cvrmse_pct')}%"
            )
            ax.legend()
            fig.tight_layout()
            fig.savefig(out / "mvm_monthly_gl14.png", dpi=140)
            fig.savefig(desk / "mvm_monthly_gl14.png", dpi=140)
            plt.close(fig)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    # allow scripts.eplus_gl14 import
    sys.path.insert(0, str(_APP / "scripts"))
    raise SystemExit(main())
