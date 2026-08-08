#!/usr/bin/env python
"""CLI: multi-resolution EnergyPlus validation → JSON + optional plots.

Keeps utility-bill monthly and interval-aggregated monthly as separate products.
Uses eplus_validation_contract for alignment (design-day dedupe, shape reject).
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
from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_multires_metrics import (  # noqa: E402
    build_validation_document,
    cross_correlation_lags,
)
from eplus_validation_contract import (  # noqa: E402
    build_hourly_and_15min,
    chronological_splits,
    interval_monthly_from_aligned_hourly,
    score_aligned,
    utility_monthly_from_trial_sim,
)


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

    sim = root / "eplus" / "dsm_native" / "runs" / "dsm_repair_v1_full" / "sim"
    if not sim.is_dir():
        print(f"missing repaired sim {sim}", file=sys.stderr)
        return 2

    products = build_hourly_and_15min(root, sim)
    aligned = products["hourly"]
    aligned_15 = products["q15"]

    hourly_block = score_aligned(aligned, resolution="hourly")
    q15_block = score_aligned(aligned_15, resolution="15min")
    monthly_utility = utility_monthly_from_trial_sim(root, sim)
    monthly_interval = interval_monthly_from_aligned_hourly(aligned)
    periods = chronological_splits(aligned)

    xcorr = cross_correlation_lags(
        aligned["observed_kw"], aligned["simulated_kw"], max_lag=24
    )
    interval_counts = {
        "n_hourly_aligned": int(len(aligned)),
        "n_15min_aligned": int(len(aligned_15)),
        "n_monthly_utility": (monthly_utility or {}).get("n"),
        "n_monthly_interval": (monthly_interval or {}).get("n"),
        "hourly_span_utc": [
            str(aligned["interval_end_utc"].min()) if len(aligned) else None,
            str(aligned["interval_end_utc"].max()) if len(aligned) else None,
        ],
        "design_day_dedupe": products.get("dedupe_dropped"),
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
            "shape_mismatch": "reject",
            "duplicate_timestamps": "reject (E+ design-day: keep_last)",
        },
        "cross_correlation": {
            "best_lag_h": xcorr.get("best_lag"),
            "best_corr": xcorr.get("best_corr"),
            "note": xcorr.get("note"),
        },
        "interval_counts": interval_counts,
        "dst_note": "Measured series may cross DST; E+ stamps never use DST",
        "provenance": {
            "measured": products.get("measured_provenance"),
            "modeled": products.get("modeled_provenance"),
        },
    }

    doc = build_validation_document(
        monthly_utility=monthly_utility,
        monthly_interval=monthly_interval,
        hourly=hourly_block,
        q15=q15_block,
        physics_label=elig.get("honesty")
        or "IdealLoads + fixed-COP electrical proxy (not GSHP/GLHE)",
        idf_sha256=elig.get("staged_sha256"),
        epw_sha256=sha256_file(epw).upper() if epw.is_file() else None,
        alignment=alignment,
        chronological_periods=periods,
    )
    if not doc["overall"]["hourly_pass"]:
        doc["overall"]["operational_dsm_readiness"] = "BLOCKED"
        doc["overall"]["recommendation_allowed"] = False
        doc["overall"]["blocker_reason"] = (
            doc["overall"].get("blocker_reason")
            or "hourly demand validation failed"
        )

    out_json = out / "eplus_multires_validation.json"
    out_json.write_text(json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8")

    # Aligned series for desktop / notebooks
    aligned.to_csv(out / "aligned_hourly_kw.csv", index=False)
    aligned_15.to_csv(out / "aligned_15min_kw.csv", index=False)

    desk = _APP / "desktop" / "artifacts" / "mvm"
    desk.mkdir(parents=True, exist_ok=True)
    (desk / "eplus_multires_validation.json").write_text(
        out_json.read_text(encoding="utf-8"), encoding="utf-8"
    )

    if args.plots and len(aligned):
        a = aligned.copy()
        a["ts"] = pd.to_datetime(a["interval_end_utc"], utc=True)
        fig, ax = plt.subplots(figsize=(10, 4))
        sample = a.iloc[: 24 * 7]
        ax.plot(sample["ts"], sample["observed_kw"], label="measured", lw=1)
        ax.plot(sample["ts"], sample["simulated_kw"], label="modeled", lw=1, alpha=0.8)
        ax.set_title("Aligned hourly — first week (design-day deduped; no lag shift)")
        ax.set_ylabel("kW")
        ax.legend()
        fig.tight_layout()
        fig.savefig(plot_dir / "hourly_week_overlay.png", dpi=120)
        plt.close(fig)

        # Residual by hour of day
        a["hod"] = a["ts"].dt.hour
        resid = a["simulated_kw"] - a["observed_kw"]
        by_h = resid.groupby(a["hod"]).mean()
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.bar(by_h.index, by_h.values)
        ax.set_xlabel("hour of day (UTC)")
        ax.set_ylabel("mean residual kW (sim−obs)")
        ax.set_title("Residual by hour of day")
        fig.tight_layout()
        fig.savefig(plot_dir / "residual_by_hour.png", dpi=120)
        plt.close(fig)

        # Load duration
        fig, ax = plt.subplots(figsize=(8, 3))
        obs_sorted = np.sort(a["observed_kw"].to_numpy())[::-1]
        sim_sorted = np.sort(a["simulated_kw"].to_numpy())[::-1]
        x = np.arange(len(obs_sorted)) / max(len(obs_sorted), 1)
        ax.plot(x, obs_sorted, label="measured")
        ax.plot(x, sim_sorted, label="modeled", alpha=0.8)
        ax.set_xlabel("fraction of hours")
        ax.set_ylabel("kW")
        ax.set_title("Load-duration curves")
        ax.legend()
        fig.tight_layout()
        fig.savefig(plot_dir / "load_duration.png", dpi=120)
        plt.close(fig)

        lags = xcorr.get("lags") or {}
        if lags:
            fig, ax = plt.subplots(figsize=(8, 3))
            keys = sorted(int(k) for k in lags)
            ax.bar(keys, [lags[str(k)] for k in keys], width=0.8)
            ax.axvline(0, color="k", lw=0.5)
            ax.set_xlabel("lag (h)")
            ax.set_ylabel("corr")
            ax.set_title("Cross-correlation −24..+24 h (no auto-shift)")
            fig.tight_layout()
            fig.savefig(plot_dir / "xcorr_lags.png", dpi=120)
            plt.close(fig)

    print(json.dumps({
        "overall": doc["overall"],
        "monthly_utility": {
            "n": (monthly_utility or {}).get("n"),
            "nmbe_pct": (monthly_utility or {}).get("nmbe_pct"),
            "cvrmse_pct": (monthly_utility or {}).get("cvrmse_pct"),
            "status": (monthly_utility or {}).get("status"),
            "label": (monthly_utility or {}).get("label"),
        },
        "monthly_interval": {
            "n": (monthly_interval or {}).get("n"),
            "nmbe_pct": (monthly_interval or {}).get("nmbe_pct"),
            "cvrmse_pct": (monthly_interval or {}).get("cvrmse_pct"),
            "status": (monthly_interval or {}).get("status"),
            "label": (monthly_interval or {}).get("label"),
        },
        "hourly": {
            "n": hourly_block.get("n"),
            "nmbe_pct": hourly_block.get("nmbe_pct"),
            "cvrmse_pct": hourly_block.get("cvrmse_pct"),
            "rmse_kw": hourly_block.get("rmse_kw"),
            "mae_kw": hourly_block.get("mae_kw"),
            "status": hourly_block.get("status"),
        },
        "q15": {
            "n": q15_block.get("n"),
            "cvrmse_pct": q15_block.get("cvrmse_pct"),
            "rmse_kw": q15_block.get("rmse_kw"),
            "mae_kw": q15_block.get("mae_kw"),
        },
        "wrote": str(out_json),
    }, indent=2, default=str))
    return 0 if doc["overall"]["hourly_pass"] and doc["overall"]["monthly_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
