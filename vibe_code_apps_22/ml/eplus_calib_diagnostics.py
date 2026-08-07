"""Residual / alignment diagnostic gallery for multi-res calibration campaigns."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from eplus_multires_metrics import cross_correlation_lags, nmbe_cvrmse_pct, resolution_block


def _ensure(dir_path: Path) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def residual_by_hour_of_day(aligned: pd.DataFrame, *, meas_col: str, mod_col: str) -> pd.DataFrame:
    df = aligned.copy()
    df["ts"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["hour"] = df["ts"].dt.tz_convert("America/Chicago").dt.hour
    df["resid"] = df[meas_col] - df[mod_col]
    return df.groupby("hour", as_index=False).agg(
        resid_mean=("resid", "mean"),
        resid_mae=("resid", lambda s: float(np.mean(np.abs(s)))),
        n=("resid", "count"),
    )


def residual_by_month(aligned: pd.DataFrame, *, meas_col: str, mod_col: str) -> pd.DataFrame:
    df = aligned.copy()
    df["ts"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["month"] = df["ts"].dt.tz_convert("America/Chicago").dt.strftime("%Y-%m")
    rows = []
    for month, g in df.groupby("month"):
        stats = nmbe_cvrmse_pct(g[meas_col], g[mod_col], p=1)
        rows.append({"month": month, **stats})
    return pd.DataFrame(rows)


def peak_day_errors(aligned: pd.DataFrame, *, meas_col: str, mod_col: str) -> pd.DataFrame:
    df = aligned.copy()
    df["ts"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["day"] = df["ts"].dt.tz_convert("America/Chicago").dt.strftime("%Y-%m-%d")
    rows = []
    for day, g in df.groupby("day"):
        if len(g) < 20:
            continue
        rows.append(
            {
                "day": day,
                "meas_peak_kw": float(g[meas_col].max()),
                "mod_peak_kw": float(g[mod_col].max()),
                "peak_mag_err_kw": float(g[mod_col].max() - g[meas_col].max()),
                "meas_peak_hour": int(
                    pd.to_datetime(g.loc[g[meas_col].idxmax(), "ts"])
                    .tz_convert("America/Chicago")
                    .hour
                ),
                "mod_peak_hour": int(
                    pd.to_datetime(g.loc[g[mod_col].idxmax(), "ts"])
                    .tz_convert("America/Chicago")
                    .hour
                ),
            }
        )
    return pd.DataFrame(rows)


def write_diagnostic_suite(
    aligned_hourly: pd.DataFrame,
    out_dir: Path,
    *,
    meas_col: str = "kw_meas",
    mod_col: str = "kw_mod",
    aligned_15: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Write Phase-3 residual gallery under campaign diagnostics/."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = _ensure(Path(out_dir))
    plots = _ensure(out / "plots")
    manifest: dict[str, Any] = {"artifacts": [], "questions": {}}

    by_hour = residual_by_hour_of_day(aligned_hourly, meas_col=meas_col, mod_col=mod_col)
    by_month = residual_by_month(aligned_hourly, meas_col=meas_col, mod_col=mod_col)
    peaks = peak_day_errors(aligned_hourly, meas_col=meas_col, mod_col=mod_col)
    xcorr = cross_correlation_lags(
        aligned_hourly[meas_col].to_numpy(),
        aligned_hourly[mod_col].to_numpy(),
        max_lag=24,
    )
    hourly_block = resolution_block(
        aligned_hourly[meas_col], aligned_hourly[mod_col], resolution="hourly"
    )

    by_hour.to_csv(out / "residual_by_hour.csv", index=False)
    by_month.to_csv(out / "residual_by_month.csv", index=False)
    peaks.to_csv(out / "peak_day_errors.csv", index=False)
    (out / "xcorr_lags.json").write_text(json.dumps(xcorr, indent=2), encoding="utf-8")
    (out / "hourly_block.json").write_text(json.dumps(hourly_block, indent=2), encoding="utf-8")
    manifest["artifacts"].extend(
        [
            "residual_by_hour.csv",
            "residual_by_month.csv",
            "peak_day_errors.csv",
            "xcorr_lags.json",
            "hourly_block.json",
        ]
    )

    peak_hour_bias = float(by_hour.loc[by_hour["resid_mae"].idxmax(), "hour"]) if len(by_hour) else None
    manifest["questions"]["schedule_or_shape"] = {
        "worst_hour_local": peak_hour_bias,
        "morning_peak_resid_mae": float(
            by_hour.loc[by_hour["hour"].between(5, 9), "resid_mae"].mean()
        )
        if len(by_hour)
        else None,
        "note": "Large HE05-09 residuals suggest schedule/setpoint/preheat mismatch",
    }
    manifest["questions"]["peak_magnitude"] = {
        "mean_abs_peak_err_kw": float(peaks["peak_mag_err_kw"].abs().mean()) if len(peaks) else None,
        "median_peak_err_kw": float(peaks["peak_mag_err_kw"].median()) if len(peaks) else None,
    }
    manifest["questions"]["alignment"] = {
        "best_xcorr_lag_h": xcorr.get("best_lag"),
        "best_xcorr": xcorr.get("best_corr"),
        "lag_shifts_applied": False,
    }

    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.bar(by_hour["hour"], by_hour["resid_mean"], color="steelblue", alpha=0.85)
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xlabel("Local hour (America/Chicago)")
    ax.set_ylabel("Mean residual m−ŷ (kW)")
    ax.set_title("Hourly residual by hour-of-day")
    fig.tight_layout()
    fig.savefig(plots / "resid_by_hour.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(by_month["month"], by_month["cvrmse_pct"], marker="o")
    ax.axhline(30, color="r", ls="--", lw=0.8, label="hourly CVRMSE gate 30%")
    ax.set_xticks(range(len(by_month)))
    ax.set_xticklabels(list(by_month["month"]), rotation=45, ha="right")
    ax.set_ylabel("CVRMSE %")
    ax.set_title("Per-month hourly CVRMSE (partial-year aware)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(plots / "cvrmse_by_month.png", dpi=120)
    plt.close(fig)

    if len(aligned_hourly) >= 24 * 7:
        sample = aligned_hourly.iloc[: 24 * 7].copy()
        sample["ts"] = pd.to_datetime(sample["timestamp_utc"], utc=True)
        fig, ax = plt.subplots(figsize=(10, 3.5))
        ax.plot(sample["ts"], sample[meas_col], label="measured", lw=1)
        ax.plot(sample["ts"], sample[mod_col], label="modeled", lw=1, alpha=0.85)
        ax.legend()
        ax.set_title("Winter/first-week overlay (no lag shift)")
        fig.tight_layout()
        fig.savefig(plots / "week_overlay.png", dpi=120)
        plt.close(fig)

    if aligned_15 is not None and len(aligned_15):
        q15 = resolution_block(aligned_15[meas_col], aligned_15[mod_col], resolution="15min")
        (out / "q15_block.json").write_text(json.dumps(q15, indent=2), encoding="utf-8")
        manifest["artifacts"].append("q15_block.json")

    (out / "diagnostics_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return manifest
