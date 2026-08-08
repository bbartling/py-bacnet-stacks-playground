#!/usr/bin/env python3
"""Post-process schedule/plant campaigns to close plan deliverable gaps.

Publishes unmet-heating estimates, day-level peaks / HE05-09, zone stratified
metrics, and gallery plots under site reports (repo mirrors JSON only).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))

from eplus_native.align import parse_eplus_csv_timestamp  # noqa: E402
from eplus_native.extract import _c_to_f, _find_zone_mat_col  # noqa: E402
from eplus_native.idf_inspect import NINE_ZONES  # noqa: E402
from eplus_native.zone_agg import aggregate_zone_temp_frame, load_agg_contract  # noqa: E402
from eplus_validation_contract import (  # noqa: E402
    build_hourly_and_15min,
    day_level_peak_metrics,
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _site() -> Path:
    return Path(os.environ["LAKESIDE_SITE_ROOT"])


def load_nine_zone_temps(sim_dir: Path) -> pd.DataFrame:
    """Vectorized MAT extract (°F) — avoid iterrows on annual CSVs."""
    src = sim_dir / "eplusout.csv"
    if not src.is_file():
        src = sim_dir / "eplusmtr.csv"
    raw = pd.read_csv(src)
    cols = list(raw.columns)
    ts_col = cols[0]
    zone_cols: dict[str, str] = {}
    for z in NINE_ZONES:
        c = _find_zone_mat_col(cols, z)
        if c is None:
            return pd.DataFrame()
        zone_cols[z] = c
    stamp = raw[ts_col].astype(str).str.strip()
    keep = stamp.ne("") & ~stamp.str.lower().str.startswith("date")
    sub = raw.loc[keep].copy()
    if sub.empty:
        return pd.DataFrame()
    ts_vals = []
    ok_idx = []
    for i, s in enumerate(sub[ts_col].astype(str).str.strip().tolist()):
        try:
            ts_vals.append(parse_eplus_csv_timestamp(s))
            ok_idx.append(sub.index[i])
        except Exception:
            continue
    if not ok_idx:
        return pd.DataFrame()
    sub = sub.loc[ok_idx]
    out = pd.DataFrame({"interval_end_utc": ts_vals}, index=sub.index)
    for z, c in zone_cols.items():
        out[z] = pd.to_numeric(sub[c], errors="coerce") * 9.0 / 5.0 + 32.0
    out = out.dropna()
    return out.reset_index(drop=True)


def unmet_heating_hours(nine: pd.DataFrame, unocc_sp_f: float = 65.0, occ_sp_f: float = 70.0) -> dict[str, Any]:
    """Estimate unmet heating hours from MAT vs schedule SP (IdealLoads diagnostic)."""
    if nine.empty:
        return {"status": "empty"}
    ts = pd.to_datetime(nine["interval_end_utc"], utc=True).dt.tz_convert("America/Chicago")
    hod = ts.dt.hour + ts.dt.minute / 60.0
    dow = ts.dt.dayofweek
    # occupied approx 7.5–14.7 weekdays (Thu to 13.5)
    occ = np.zeros(len(nine), dtype=bool)
    for i in range(len(nine)):
        if dow.iloc[i] >= 5:
            continue
        end = 13.5 if dow.iloc[i] == 3 else 14.67
        if 7.5 <= hod.iloc[i] < end:
            occ[i] = True
    sp = np.where(occ, occ_sp_f, unocc_sp_f)
    # timestep hours from median delta
    dt_h = 0.25
    out: dict[str, Any] = {"timestep_h": dt_h, "zones": {}}
    total = 0.0
    for z in NINE_ZONES:
        unmet = nine[z].to_numpy(dtype=float) < (sp - 1.0)
        hours = float(unmet.sum() * dt_h)
        out["zones"][z] = {
            "unmet_heating_hours": hours,
            "frac": float(unmet.mean()),
            "min_temp_f": float(nine[z].min()),
            "mean_temp_f": float(nine[z].mean()),
        }
        total += hours
    out["sum_zone_unmet_heating_hours"] = total
    out["note"] = (
        "Estimated from zone MAT vs civil occupied/unoccupied SP (±1°F deadband); "
        "not EnergyPlus Facility Time Heating Setpoint Not Met meter (not in run outputs)."
    )
    return out


def stratified_zone_metrics(meas: pd.DataFrame, sim: pd.DataFrame, col: str) -> dict[str, Any]:
    left = meas.copy()
    right = sim.copy()
    left["interval_end_utc"] = pd.to_datetime(left["interval_end_utc"], utc=True)
    right["interval_end_utc"] = pd.to_datetime(right["interval_end_utc"], utc=True)
    m = left.merge(right, on="interval_end_utc", how="inner", suffixes=("_m", "_s"))
    if m.empty:
        return {}
    ts = pd.to_datetime(m["interval_end_utc"], utc=True).dt.tz_convert("America/Chicago")
    m = m.assign(
        hod=ts.dt.hour,
        dow=ts.dt.dayofweek,
        month=ts.dt.month,
        is_weekend=ts.dt.dayofweek >= 5,
    )
    y = pd.to_numeric(m[f"{col}_m"], errors="coerce")
    yhat = pd.to_numeric(m[f"{col}_s"], errors="coerce")
    mask = y.notna() & yhat.notna()
    m = m.loc[mask]
    y = y.loc[mask].to_numpy()
    yhat = yhat.loc[mask].to_numpy()

    def _blk(sel: pd.Series) -> dict[str, float]:
        yy = y[sel.to_numpy()]
        yh = yhat[sel.to_numpy()]
        if len(yy) == 0:
            return {}
        e = yh - yy
        return {
            "n": int(len(yy)),
            "mae": float(np.mean(np.abs(e))),
            "rmse": float(np.sqrt(np.mean(e**2))),
            "bias": float(np.mean(e)),
            "p95_abs": float(np.quantile(np.abs(e), 0.95)),
        }

    cold = m["month"].isin([12, 1, 2])
    return {
        "all": _blk(pd.Series(True, index=m.index)),
        "overnight": _blk(m["hod"].isin([0, 1, 2, 3, 4, 5])),
        "occupied_day": _blk(m["hod"].between(8, 15) & ~m["is_weekend"]),
        "weekday": _blk(~m["is_weekend"]),
        "weekend": _blk(m["is_weekend"]),
        "cold_months": _blk(cold),
    }


def plot_zone_gallery(nine: pd.DataFrame, agg: pd.DataFrame, out_dir: Path, meas: pd.DataFrame | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.to_datetime(nine["interval_end_utc"], utc=True).dt.tz_convert("America/Chicago")
    # pick a cold weekday
    winter = nine.assign(ts=ts, dow=ts.dt.dayofweek, month=ts.dt.month)
    days = winter[(winter["month"] == 1) & (winter["dow"] < 5)]["ts"].dt.date.unique()
    if len(days) == 0:
        return
    day = days[len(days) // 2]
    day_mask = winter["ts"].dt.date == day
    fig, axes = plt.subplots(3, 2, figsize=(11, 8), sharex=True)
    axes = axes.ravel()
    for i, col in enumerate(agg.columns):
        ax = axes[i]
        ax.plot(winter.loc[day_mask, "ts"].dt.hour + winter.loc[day_mask, "ts"].dt.minute / 60.0,
                agg.loc[day_mask, col], label="sim agg", lw=1.5)
        if meas is not None and col in meas.columns:
            mm = meas.copy()
            mm["interval_end_utc"] = pd.to_datetime(mm["interval_end_utc"], utc=True)
            ml = mm["interval_end_utc"].dt.tz_convert("America/Chicago")
            mday = mm[ml.dt.date == day]
            if len(mday):
                ax.plot(
                    ml[ml.dt.date == day].dt.hour + ml[ml.dt.date == day].dt.minute / 60.0,
                    mday[col],
                    label="BAS",
                    lw=1.2,
                    alpha=0.8,
                )
        ax.set_title(col.replace("zone_temp_", "").replace("_f", ""))
        ax.set_ylabel("°F")
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
    fig.suptitle(f"Six-zone temps — local day {day} (America/Chicago)")
    fig.tight_layout()
    fig.savefig(out_dir / "zone_gallery_cold_weekday.png", dpi=120)
    plt.close(fig)


def enrich_schedule_sanity(site: Path) -> dict[str, Any]:
    camp = site / "eplus" / "campaigns" / "schedule_sanity_20260808T150000Z"
    out: dict[str, Any] = {"campaign_id": camp.name, "created_utc": _utc(), "trials": {}}
    for trial_dir in sorted((camp / "trials").glob("*")):
        if not trial_dir.is_dir():
            continue
        sim = trial_dir / "sim"
        if not (sim / "eplusmtr.csv").is_file() and not (sim / "eplusout.csv").is_file():
            continue
        tid = trial_dir.name
        print(f"enrich schedule {tid}", flush=True)
        nine = load_nine_zone_temps(sim)
        unmet = unmet_heating_hours(nine)
        packed = build_hourly_and_15min(site, sim)
        peaks = day_level_peak_metrics(packed["hourly"])
        # strip heavy day list for summary
        peaks_slim = {k: v for k, v in peaks.items() if k != "days"}
        out["trials"][tid] = {
            "unmet_heating": unmet,
            "day_level_peaks": peaks_slim,
            "utility_nmbe_cvrmse": None,
        }
        # plot winter weekend overlay for facility
        h = packed["hourly"].copy()
        h["ts"] = pd.to_datetime(h["interval_end_utc"], utc=True).dt.tz_convert("America/Chicago")
        w = h[(h["ts"].dt.month.isin([12, 1, 2])) & (h["ts"].dt.dayofweek >= 5)].head(48)
        if len(w):
            plots = trial_dir / "plots"
            plots.mkdir(exist_ok=True)
            fig, ax = plt.subplots(figsize=(9, 3.5))
            ax.plot(range(len(w)), w["observed_kw"], label="meas")
            ax.plot(range(len(w)), w["simulated_kw"], label="sim")
            ax.set_title(f"{tid} winter-weekend sample")
            ax.set_ylabel("kW")
            ax.legend()
            fig.tight_layout()
            fig.savefig(plots / "winter_weekend_sample.png", dpi=110)
            plt.close(fig)
    path = camp / "schedule_sanity_enrichment.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def enrich_zone_validation(site: Path) -> dict[str, Any]:
    sim = site / "eplus" / "campaigns" / "schedule_sanity_20260808T150000Z" / "trials" / "S3_cap_mid_2p7" / "sim"
    out_dir = site / "reports" / "eplus" / "zone_validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    nine = load_nine_zone_temps(sim)
    cal = load_agg_contract()
    agg = aggregate_zone_temp_frame(nine, contract=cal, mode="hp_count")
    agg = agg.assign(interval_end_utc=nine["interval_end_utc"].values)
    meas = None
    for p in (
        site / "clean_data" / "LAKESIDE_ES" / "zone_temp_15min.parquet",
        site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet",
    ):
        if p.is_file():
            meas = pd.read_parquet(p)
            if "timestamp_utc" in meas.columns and "interval_end_utc" not in meas.columns:
                meas = meas.rename(columns={"timestamp_utc": "interval_end_utc"})
            meas["interval_end_utc"] = pd.to_datetime(meas["interval_end_utc"], utc=True)
            break
    stratified = {}
    if meas is not None:
        for col in [c for c in agg.columns if c.startswith("zone_temp_")]:
            if col in meas.columns:
                stratified[col] = stratified_zone_metrics(
                    meas[["interval_end_utc", col]],
                    agg[["interval_end_utc", col]],
                    col,
                )
    plot_zone_gallery(nine, agg.drop(columns=["interval_end_utc"]), out_dir / "plots", meas)
    summary = {
        "created_utc": _utc(),
        "contract": "eplus_nine_to_six_zone_agg_v1",
        "sim_trial_id": "S3_cap_mid_2p7",
        "stratified_zone_metrics": stratified,
        "unmet_heating": unmet_heating_hours(nine),
        "honesty": "SCREENING ONLY — IdealLoads repaired family",
    }
    (out_dir / "zone_validation_stratified.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    repo = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-zone-validation-summary.json"
    prev = json.loads(repo.read_text(encoding="utf-8")) if repo.is_file() else {}
    prev.update(
        {
            "stratified_available": bool(stratified),
            "unmet_heating_sum_zone_hours": summary["unmet_heating"].get("sum_zone_unmet_heating_hours"),
            "gallery_plot": "reports/eplus/zone_validation/plots/zone_gallery_cold_weekday.png",
            "updated_utc": _utc(),
        }
    )
    repo.write_text(json.dumps(prev, indent=2) + "\n", encoding="utf-8")
    return summary


def enrich_plant_proxy(site: Path) -> dict[str, Any]:
    camp = site / "eplus" / "campaigns" / "plant_proxy_calib_20260808T150000Z"
    out: dict[str, Any] = {"campaign_id": camp.name, "created_utc": _utc(), "trials": {}}
    for trial_dir in sorted((camp / "trials").glob("P*")):
        sim = trial_dir / "sim"
        if not sim.is_dir():
            continue
        tid = trial_dir.name
        print(f"enrich plant {tid}", flush=True)
        try:
            packed = build_hourly_and_15min(site, sim)
            peaks = day_level_peak_metrics(packed["hourly"])
            peaks_slim = {k: v for k, v in peaks.items() if k != "days"}
            nine = load_nine_zone_temps(sim)
            unmet = unmet_heating_hours(nine)
            tr = json.loads((trial_dir / "trial_result.json").read_text(encoding="utf-8"))
            util = (tr.get("metrics") or {}).get("utility_monthly") or {}
            out["trials"][tid] = {
                "knobs": tr.get("knobs"),
                "composite_score": tr.get("composite_score"),
                "gates": tr.get("gates"),
                "day_level_peaks": peaks_slim,
                "he05_09_mae_median": (peaks_slim.get("morning_he05_09_mae_kw") or {}).get("median"),
                "unmet_heating_sum_zone_hours": unmet.get("sum_zone_unmet_heating_hours"),
                "utility_nmbe_pct": util.get("nmbe_pct"),
                "utility_cvrmse_pct": util.get("cvrmse_pct"),
            }
        except Exception as e:
            out["trials"][tid] = {"status": "enrich_failed", "error": f"{type(e).__name__}: {e}"}
    # leaderboard by composite if present else utility cv
    ok = [t for t, v in out["trials"].items() if "composite_score" in v]
    ok.sort(key=lambda t: out["trials"][t].get("composite_score") or 1e9)
    out["leaderboard_top5"] = ok[:5]
    out["raw_eplus_gates_any_pass"] = any(
        (out["trials"][t].get("gates") or {}).get("raw_eplus_gates_pass") for t in ok
    )
    path = camp / "plant_proxy_enrichment.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    repo = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-plant-proxy-calib-summary.json"
    prev = json.loads(repo.read_text(encoding="utf-8"))
    prev["enrichment"] = {
        "day_level_peaks_and_he05_09": True,
        "unmet_heating_hours": True,
        "raw_eplus_gates_any_pass": out["raw_eplus_gates_any_pass"],
        "leaderboard_top5": out["leaderboard_top5"],
        "updated_utc": _utc(),
    }
    # attach best trial enriched metrics
    if ok:
        prev["best_enriched"] = out["trials"][ok[0]]
    repo.write_text(json.dumps(prev, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> int:
    site = _site()
    s = enrich_schedule_sanity(site)
    z = enrich_zone_validation(site)
    p = enrich_plant_proxy(site)
    print(json.dumps({
        "schedule_trials": len(s.get("trials") or {}),
        "zone_stratified_zones": len(z.get("stratified_zone_metrics") or {}),
        "plant_trials": len(p.get("trials") or {}),
        "plant_raw_gates": p.get("raw_eplus_gates_any_pass"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
