#!/usr/bin/env python3
"""Tutorial charts: E+ end-use estimate vs actual demand (peak day + winter avg).

EnergyPlus meter file only reports InteriorLights/Equipment monthly, so HVAC /
lights / plugs are disaggregated with research-style diurnal fractions scaled
to those monthly totals, then overlaid on BAS observed demand.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from eplus_validation_contract import build_hourly_and_15min  # noqa: E402
from notebook_plots import apply_notebook_theme  # noqa: E402


def _save(path: Path, fig) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140, bbox_inches="tight")
    print("wrote", path, flush=True)
    return path

PEAK_DAY = "2026-01-26"


def _facility_hourly_j(sim: Path) -> pd.Series:
    mtr = pd.read_csv(sim / "eplusmtr.csv")
    col = "Electricity:Facility [J](Hourly)"
    if col not in mtr.columns:
        raise SystemExit(f"missing {col} in {sim / 'eplusmtr.csv'}")
    s = pd.to_numeric(mtr[col], errors="coerce")
    # Drop monthly-only trailing rows (NaN hourly)
    return s.dropna().reset_index(drop=True)


def _monthly_enduse_j(sim: Path) -> dict[str, float]:
    mtr = pd.read_csv(sim / "eplusmtr.csv")
    out: dict[str, float] = {}
    for key, col in (
        ("lights", "InteriorLights:Electricity [J](Monthly)"),
        ("equip", "InteriorEquipment:Electricity [J](Monthly)"),
        ("facility", "Electricity:Facility [J](Monthly)"),
    ):
        if col in mtr.columns:
            v = pd.to_numeric(mtr[col], errors="coerce").dropna()
            out[key] = float(v.sum()) if len(v) else 0.0
    return out


def _school_frac(hour: np.ndarray, kind: str) -> np.ndarray:
    """Simple school weekday fraction profiles (research-report style)."""
    h = hour % 24
    if kind == "lights":
        # low overnight, ramp 6–8, occupied 8–16, taper to 22
        f = np.where(h < 6, 0.08, 0.0)
        f = np.where((h >= 6) & (h < 8), 0.35 + 0.25 * (h - 6), f)
        f = np.where((h >= 8) & (h < 16), 0.85, f)
        f = np.where((h >= 16) & (h < 18), 0.55, f)
        f = np.where((h >= 18) & (h < 22), 0.25, f)
        f = np.where(h >= 22, 0.10, f)
        return f.astype(float)
    # plugs: ~5% overnight, 70% instruction
    f = np.where(h < 6, 0.05, 0.0)
    f = np.where((h >= 6) & (h < 8), 0.25 + 0.20 * (h - 6), f)
    f = np.where((h >= 8) & (h < 16), 0.70, f)
    f = np.where((h >= 16) & (h < 18), 0.35, f)
    f = np.where((h >= 18) & (h < 22), 0.15, f)
    f = np.where(h >= 22, 0.06, f)
    return f.astype(float)


def disaggregate_hourly_kw(sim: Path, n_hours: int) -> pd.DataFrame:
    fac_j = _facility_hourly_j(sim)
    if len(fac_j) < n_hours:
        raise SystemExit(f"facility hourly rows {len(fac_j)} < {n_hours}")
    fac_j = fac_j.iloc[:n_hours]
    monthly = _monthly_enduse_j(sim)
    hours = np.arange(n_hours)
    hod = hours % 24
    # Assume AMY starts Aug 1 — weekday mask approx Mon-Fri via day index
    day = hours // 24
    # 2025-08-01 was Friday → day%7: 0=Fri … use Mon-Fri as day%7 in {3,4,5,6,0}? 
    # Simpler: use same profile every day (school-year mean shape); scale to annual totals.
    li_frac = _school_frac(hod, "lights")
    eq_frac = _school_frac(hod, "equip")
    li_w = li_frac / li_frac.sum()
    eq_w = eq_frac / eq_frac.sum()
    lights_j = li_w * monthly.get("lights", 0.0)
    equip_j = eq_w * monthly.get("equip", 0.0)
    fac = fac_j.to_numpy(dtype=float)
    hvac_j = np.clip(fac - lights_j - equip_j, 0.0, None)
    j_to_kw = 1.0 / 3_600_000.0
    return pd.DataFrame(
        {
            "hour_index": hours,
            "facility_kw": fac * j_to_kw,
            "lights_kw": lights_j * j_to_kw,
            "equip_kw": equip_j * j_to_kw,
            "hvac_est_kw": hvac_j * j_to_kw,
        }
    )


def _q15_local(site: Path, sim: Path) -> pd.DataFrame:
    packed = build_hourly_and_15min(site, sim, heat_cop=3.5, cool_cop=4.5)
    f = packed["q15"].copy()
    f["interval_end_utc"] = pd.to_datetime(f["interval_end_utc"], utc=True)
    local = f["interval_end_utc"].dt.tz_convert("America/Chicago")
    f = f.assign(
        local=local,
        d=local.dt.strftime("%Y-%m-%d"),
        hod=local.dt.hour + local.dt.minute / 60.0,
        month=local.dt.month,
        dow=local.dt.dayofweek,
    )
    return f


def _hp_runtime_summary(site: Path) -> dict:
    p = site / "reports" / "zone_avg_fan_run_hours_monthly.csv"
    if not p.is_file():
        return {}
    zh = pd.read_csv(p)
    zh["month"] = zh["month"].astype(str)
    winter = zh[zh["month"].isin(["2026-01", "2026-02"])]
    return {
        "source": str(p),
        "jan_feb_avg_fan_run_hours_by_zone": winter.to_dict(orient="records"),
        "jan_building_avg_fan_run_hours": float(
            winter[winter["month"] == "2026-01"]["avg_fan_run_hours"].mean()
        )
        if len(winter) else None,
        "note": (
            "Fan run hours from clean BAS HP status analytics. "
            "Use as qualitative runtime check when cutting equip_w_area_mult "
            "after a peak≈285 / GL14-fail trial."
        ),
    }


def main() -> int:
    apply_notebook_theme()
    site = Path(os.environ.get("LAKESIDE_SITE_ROOT", r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"))
    fig_dir = site / "plots" / "analytics" / "eplus_gl14_vs_peak285"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # Prefer enhanced champion if summary says improved; else L22
    enh_camps = sorted((site / "eplus" / "campaigns").glob("w2a_l22_enhanced_*"))
    sim = site / "eplus/campaigns/w2a_lowbase_optstart_20260808T190216Z/trials/L22_cap145_cop124_sb46_opt35/sim"
    label = "L22"
    if enh_camps:
        summary_p = enh_camps[-1] / "summary.json"
        if summary_p.is_file():
            s = json.loads(summary_p.read_text(encoding="utf-8"))
            if s.get("improved_vs_l22") and s.get("best_dual"):
                tid = s["best_dual"]["trial_id"]
                cand = enh_camps[-1] / "trials" / tid / "sim"
                if (cand / "eplusmtr.csv").is_file():
                    sim = cand
                    label = tid

    q15 = _q15_local(site, sim)
    # Align disagg length to facility hourly count
    fac_n = len(_facility_hourly_j(sim))
    endu = disaggregate_hourly_kw(sim, fac_n)
    # Map AMY hour index → local timestamps via q15 hourly resample of first fac_n hours
    # Use q15 peak day + winter weekday means from observed/sim total; end-use from disagg.

    # Build hourly local frame from q15
    h = q15.copy()
    # Floor in UTC to avoid DST ambiguous/nonexistent local hours.
    h["hour_utc"] = h["interval_end_utc"].dt.floor("h")
    hourly = (
        h.groupby("hour_utc", as_index=False)
        .agg(observed_kw=("observed_kw", "mean"), simulated_kw=("simulated_kw", "mean"))
    )
    local_h = hourly["hour_utc"].dt.tz_convert("America/Chicago")
    hourly["hour"] = local_h
    hourly["d"] = local_h.dt.strftime("%Y-%m-%d")
    hourly["hod"] = local_h.dt.hour
    hourly["month"] = local_h.dt.month
    hourly["dow"] = local_h.dt.dayofweek

    # Attach end-use by matching chronological hour order
    n = min(len(hourly), len(endu))
    hourly = hourly.iloc[:n].copy()
    for c in ("lights_kw", "equip_kw", "hvac_est_kw", "facility_kw"):
        hourly[c] = endu[c].to_numpy()[:n]

    # --- Peak day stacked end-use + actual ---
    peak = hourly[hourly["d"] == PEAK_DAY].copy()
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    if len(peak):
        x = peak["hod"].to_numpy()
        ax.stackplot(
            x,
            peak["lights_kw"],
            peak["equip_kw"],
            peak["hvac_est_kw"],
            labels=["Lights (sched. est.)", "Plugs (sched. est.)", "HVAC residual est."],
            colors=["#e9c46a", "#f4a261", "#2a9d8f"],
            alpha=0.9,
        )
        ax.plot(x, peak["observed_kw"], color="#264653", lw=2.2, label="Actual BAS demand")
        ax.axhline(285, color="#5c6b73", ls="--", lw=1, label="Utility peak 285 kW")
        ax.set_title(f"{PEAK_DAY} — {label} end-use estimate vs actual")
        ax.set_xlabel("Hour (America/Chicago)")
        ax.set_ylabel("kW")
        ax.legend(loc="upper left", fontsize=8, frameon=False)
        ax.set_xlim(0, 23)
    _save(fig_dir / f"peak_day_enduse_stack_{label}.png", fig)
    plt.close(fig)

    # --- Winter weekday average profiles ---
    winter = hourly[(hourly["month"].isin([12, 1, 2])) & (hourly["dow"] < 5)]
    avg = winter.groupby("hod", as_index=False).mean(numeric_only=True)
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    if len(avg):
        x = avg["hod"].to_numpy()
        ax.stackplot(
            x,
            avg["lights_kw"],
            avg["equip_kw"],
            avg["hvac_est_kw"],
            labels=["Lights", "Plugs", "HVAC residual"],
            colors=["#e9c46a", "#f4a261", "#2a9d8f"],
            alpha=0.9,
        )
        ax.plot(x, avg["observed_kw"], color="#264653", lw=2.2, label="Actual (winter WD avg)")
        ax.plot(x, avg["simulated_kw"], color="#e76f51", lw=1.6, ls="--", label=f"{label} total sim")
        ax.set_title(f"Winter weekday average — {label} end-use vs actual")
        ax.set_xlabel("Hour")
        ax.set_ylabel("kW")
        ax.legend(loc="upper left", fontsize=8, frameon=False)
        ax.set_xlim(0, 23)
    _save(fig_dir / f"winter_wd_avg_enduse_{label}.png", fig)
    plt.close(fig)

    # --- Overnight summary vs observed ---
    ov = q15[(q15["month"].isin([12, 1, 2])) & (q15["hod"] < 4)]
    stats = {
        "model": label,
        "sim_dir": str(sim),
        "winter_overnight_0_4_obs_mean_kw": float(ov["observed_kw"].mean()) if len(ov) else None,
        "winter_overnight_0_4_sim_mean_kw": float(ov["simulated_kw"].mean()) if len(ov) else None,
        "winter_overnight_0_4_obs_p50_kw": float(ov["observed_kw"].median()) if len(ov) else None,
        "winter_overnight_0_4_obs_p90_kw": float(ov["observed_kw"].quantile(0.9)) if len(ov) else None,
        "peak_day": PEAK_DAY,
        "peak_day_obs_max_kw": float(q15.loc[q15["d"] == PEAK_DAY, "observed_kw"].max())
        if (q15["d"] == PEAK_DAY).any()
        else None,
        "peak_day_sim_max_kw": float(q15.loc[q15["d"] == PEAK_DAY, "simulated_kw"].max())
        if (q15["d"] == PEAK_DAY).any()
        else None,
        "monthly_enduse_j": _monthly_enduse_j(sim),
        "hp_fan_runtime": _hp_runtime_summary(site),
        "plots": [
            str(fig_dir / f"peak_day_enduse_stack_{label}.png"),
            str(fig_dir / f"winter_wd_avg_enduse_{label}.png"),
        ],
    }
    out_json = fig_dir / "enduse_profile_stats.json"
    out_json.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    mirror = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-l22-enduse-profile-stats.json"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: stats[k] for k in ("model", "winter_overnight_0_4_obs_mean_kw", "winter_overnight_0_4_sim_mean_kw", "peak_day_sim_max_kw", "plots")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
