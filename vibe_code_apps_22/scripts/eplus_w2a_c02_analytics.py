#!/usr/bin/env python3
"""C02 residual / peak analytics from site measured meter + sim (no client PII)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from eplus_validation_contract import (  # noqa: E402
    build_hourly_and_15min,
    day_level_peak_metrics,
    reserved_final_winter_audit_mask,
    rolling_origin_selection_mask,
    ROLLING_ORIGIN_SELECTION_FOLDS,
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _profile(df: pd.DataFrame, *, label: str) -> dict[str, Any]:
    if df.empty:
        return {"label": label, "n": 0}
    resid = df["simulated_kw"].to_numpy(dtype=float) - df["observed_kw"].to_numpy(dtype=float)
    local = pd.to_datetime(df["interval_end_utc"], utc=True).dt.tz_convert("America/Chicago")
    hod = local.dt.hour
    by_hod = {
        str(h): {
            "mean_resid_kw": float(resid[hod == h].mean()) if (hod == h).any() else None,
            "mae_kw": float(np.abs(resid[hod == h]).mean()) if (hod == h).any() else None,
            "n": int((hod == h).sum()),
        }
        for h in range(24)
    }
    dow = local.dt.dayofweek
    by_dow = {
        str(d): {
            "mean_resid_kw": float(resid[dow == d].mean()) if (dow == d).any() else None,
            "mae_kw": float(np.abs(resid[dow == d]).mean()) if (dow == d).any() else None,
            "n": int((dow == d).sum()),
        }
        for d in range(7)
    }
    morning = (local.dt.hour >= 5) & (local.dt.hour < 9)
    return {
        "label": label,
        "n": int(len(df)),
        "mean_resid_kw": float(resid.mean()),
        "mae_kw": float(np.abs(resid).mean()),
        "rmse_kw": float(np.sqrt(np.mean(resid**2))),
        "he05_09_mae_kw": float(np.abs(resid[morning]).mean()) if morning.any() else None,
        "by_hod": by_hod,
        "by_dow": by_dow,
    }


def main() -> int:
    site = Path(os.environ["LAKESIDE_SITE_ROOT"])
    sim = (
        site
        / "eplus"
        / "campaigns"
        / "w2a_creative_push_20260808T165522Z"
        / "trials"
        / "C02_setback58_cap45"
        / "sim"
    )
    if not (sim / "eplusmtr.csv").is_file():
        raise SystemExit(f"missing C02 sim: {sim}")

    packed = build_hourly_and_15min(site, sim, heat_cop=3.5, cool_cop=4.5)
    hourly = packed["hourly"].copy()
    hourly["interval_end_utc"] = pd.to_datetime(hourly["interval_end_utc"], utc=True)

    sel_mask = pd.Series(False, index=hourly.index)
    for fold in ROLLING_ORIGIN_SELECTION_FOLDS:
        sel_mask |= rolling_origin_selection_mask(
            hourly,
            origin_local=str(fold["origin_local"]),
            horizon_days=int(fold.get("horizon_days", 10)),
        )
    feb_mask = reserved_final_winter_audit_mask(hourly)
    winter = hourly["interval_end_utc"].dt.tz_convert("America/Chicago").dt.month.isin([12, 1, 2])
    weekend = hourly["interval_end_utc"].dt.tz_convert("America/Chicago").dt.dayofweek >= 5

    peaks_feb = day_level_peak_metrics(hourly.loc[feb_mask])
    peaks_sel = day_level_peak_metrics(hourly.loc[sel_mask])

    analytics = {
        "created_utc": _utc(),
        "anchor_trial_id": "C02_setback58_cap45",
        "anchor_campaign": "w2a_creative_push_20260808T165522Z",
        "honesty": (
            "Facility kW residuals vs site meter; Lakeside alias only. "
            "Guides C02-neighborhood dial; monthly GL14-style is hard rank constraint."
        ),
        "structural_slice": {
            "winter_weekend_kw_mod_mean": float(
                hourly.loc[winter & weekend, "simulated_kw"].mean()
            ),
            "winter_weekend_kw_meas_mean": float(
                hourly.loc[winter & weekend, "observed_kw"].mean()
            ),
            "winter_weekend_abs_err": float(
                abs(
                    hourly.loc[winter & weekend, "simulated_kw"].mean()
                    - hourly.loc[winter & weekend, "observed_kw"].mean()
                )
            ),
        },
        "selection_nov_dec": _profile(hourly.loc[sel_mask], label="rolling_origin_selection"),
        "reserved_feb": _profile(hourly.loc[feb_mask], label="reserved_final_winter_audit"),
        "peaks_selection": {
            k: peaks_sel.get(k)
            for k in (
                "n_complete_days",
                "status",
                "abs_peak_magnitude_error_kw",
                "circular_abs_peak_timing_error_h",
                "morning_he05_09_mae_kw",
            )
        },
        "peaks_feb": {
            k: peaks_feb.get(k)
            for k in (
                "n_complete_days",
                "status",
                "abs_peak_magnitude_error_kw",
                "circular_abs_peak_timing_error_h",
                "morning_he05_09_mae_kw",
            )
        },
        "dial_hypotheses": [
            "Feb HE05-09 and peak mag still high — try mild optimum_start only if monthly holds",
            "Weekend still ~13 kW high — fine setback 58-62F and capacity 0.40-0.50",
            "Ban fan_avail_use_sch_hvac (collapse)",
            "Prefer COP mult >= 1.0",
        ],
    }

    # Top residual hours in Feb for report
    feb = hourly.loc[feb_mask].copy()
    if not feb.empty:
        local = feb["interval_end_utc"].dt.tz_convert("America/Chicago")
        feb = feb.assign(hod=local.dt.hour, resid=feb["simulated_kw"] - feb["observed_kw"])
        by = feb.groupby("hod")["resid"].agg(["mean", "count"])
        worst = by.reindex(range(24)).assign(abs_mean=lambda x: x["mean"].abs()).sort_values(
            "abs_mean", ascending=False
        )
        analytics["feb_worst_hod_by_abs_mean_resid"] = [
            {"hod": int(i), "mean_resid_kw": float(r["mean"]), "n": int(r["count"])}
            for i, r in worst.head(6).iterrows()
            if pd.notna(r["mean"])
        ]

    out_site = (
        site
        / "eplus"
        / "campaigns"
        / "w2a_monthly_hold_hourly_dial_analytics"
    )
    out_site.mkdir(parents=True, exist_ok=True)
    (out_site / "analytics.json").write_text(json.dumps(analytics, indent=2) + "\n", encoding="utf-8")
    mirror = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-w2a-monthly-hold-hourly-dial-analytics.json"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text(json.dumps(analytics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "mirror": str(mirror),
        "feb_mae": analytics["reserved_feb"].get("mae_kw"),
        "feb_he0509": analytics["reserved_feb"].get("he05_09_mae_kw"),
        "weekend_abs_err": analytics["structural_slice"]["winter_weekend_abs_err"],
        "worst_hod": analytics.get("feb_worst_hod_by_abs_mean_resid"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
