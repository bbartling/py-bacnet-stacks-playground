"""BAS transient statistics on train_dev only. CapMult remains diagnostic."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from a04v2_phase2_zone_dataset import ZONE_COLS, contiguous_abs_delta
from eplus_gym.site_env import require_site_root

GATE = {"2026-01-25", "2026-01-26", "2026-03-16"}


def stats_for(df: pd.DataFrame) -> dict:
    t = pd.to_datetime(df["timestamp_local"])
    work = df.sort_values("timestamp_local").copy()
    work["timestamp_local"] = pd.to_datetime(work["timestamp_local"])
    for c in ZONE_COLS:
        work[f"dT_{c}"] = contiguous_abs_delta(work[c], work["timestamp_local"])
    occupied = work["occupied"].astype(float) > 0.5
    occ_chg = occupied.astype(int).diff().fillna(0)
    evening = occ_chg == -1
    morning = occ_chg == 1
    deltas = work[[f"dT_{c}" for c in ZONE_COLS]].to_numpy().reshape(-1)
    deltas = deltas[np.isfinite(deltas)]
    cooldown = []
    recovery = []
    time_to_68 = []
    for _, g in work.groupby(work["timestamp_local"].dt.date.astype(str)):
        g = g.sort_values("timestamp_local")
        dT = g[[f"dT_{c}" for c in ZONE_COLS]].mean(axis=1)
        occ = g["occupied"].astype(float) > 0.5
        chg = occ.astype(int).diff().fillna(0)
        mean_z = g[ZONE_COLS].mean(axis=1)
        if (chg == -1).any():
            i = int(np.argmax(chg.eq(-1).to_numpy()))
            cooldown.append(float(dT.iloc[i : i + 4].mean()) if i + 1 < len(dT) else float(dT.iloc[i]))
        if (chg == 1).any():
            i = int(np.argmax(chg.eq(1).to_numpy()))
            recovery.append(float(dT.iloc[max(0, i - 4) : i + 1].mean()))
            after = mean_z.iloc[i:]
            hit = after[after >= 68.0]
            if len(hit):
                time_to_68.append(float((hit.index[0] - after.index[0]) * 15.0) if False else 15.0 * int(np.argmax(after.to_numpy() >= 68.0)))
    return {
        "n_intervals": int(len(work)),
        "abs_dT_p50": float(np.quantile(deltas, 0.5)) if len(deltas) else None,
        "abs_dT_p99": float(np.quantile(deltas, 0.99)) if len(deltas) else None,
        "abs_dT_p99_9": float(np.quantile(deltas, 0.999)) if len(deltas) else None,
        "evening_cooldown_mean_abs_dT_f": float(np.mean(cooldown)) if cooldown else None,
        "morning_recovery_mean_abs_dT_f": float(np.mean(recovery)) if recovery else None,
        "time_to_68_min_mean": float(np.mean(time_to_68)) if time_to_68 else None,
        "n_evening_events": int(len(cooldown)),
        "n_morning_events": int(len(recovery)),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", default=None)
    args = p.parse_args()
    site = require_site_root(args.site_root)
    df = pd.read_parquet(site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet")
    ledger = pd.read_csv(_APP / "docs" / "audits" / "figures" / "a04v2" / "phase2" / "day_event_ledger.csv")
    t = pd.to_datetime(df["timestamp_local"])
    df = df.copy()
    df["date"] = t.dt.date.astype(str)
    df = df.merge(ledger[["date", "fold"]], on="date", how="left")
    oat = pd.to_numeric(df.get("oat_f"), errors="coerce")
    df["very_cold"] = oat < 10.0
    df["mild"] = oat > 45.0
    train = df[df["fold"].eq("train_dev") & ~df["date"].isin(GATE)]
    cold = train[train["very_cold"].astype(bool)]
    mild = train[train["mild"].astype(bool)]
    body = {
        "schema": "vibe22.a04v2.bas_transient_stats.v1",
        "split": "train_dev only; model_selection_val and heldout_transient preserved",
        "all_train_dev": stats_for(train),
        "cold_days": stats_for(cold) if len(cold) else None,
        "mild_days": stats_for(mild) if len(mild) else None,
        "capmult_note": (
            "Do not promote CapMult≈28 unless related to measured effective capacitance. "
            "Stage B CapMult bound is [1, 20]."
        ),
    }
    out_dir = _APP / "docs" / "audits" / "figures" / "a04v2" / "phase3"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bas_transient_stats.json").write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    cooldown = body["all_train_dev"]["evening_cooldown_mean_abs_dT_f"] or 1.0
    # Rough C_eff multiplier vs 5°F DualSP step: measured cooldown / 5.
    cap_est = min(20.0, max(1.0, 5.0 / max(cooldown, 0.2)))
    manifest = {
        "schema": "vibe22.a04v2.parameter_manifest.v1",
        "parameters": [
            {
                "name": "ZoneCapacitanceMultiplier.Temperature",
                "baseline": 1.0,
                "lo": 1.0,
                "hi": 20.0,
                "units": "dimensionless",
                "justification": f"BAS evening mean |dT|≈{cooldown:.3f}°F/15min; 5°F DualSP / measured slope ≈ {cap_est:.2f}. Diagnostic, not a ramp-threshold tuner.",
                "affects": ["temperature_dynamics", "peak"],
            },
            {
                "name": "InternalMass.Surface_Area_m2_per_zone",
                "baseline": 0.0,
                "lo": 0.0,
                "hi": 3000.0,
                "units": "m2",
                "justification": "Furniture/contents mass; Stage A showed InternalMass alone does not fix DualSP tracking.",
                "affects": ["temperature_dynamics"],
            },
            {
                "name": "W2A_heating_capacity_airflow",
                "baseline": "149430 W heating + autosize airflow on all 9 units",
                "lo": "autosize both",
                "hi": "3-ton/HP × 67 split",
                "units": "W and m3/s",
                "justification": "Identical 149430 W with autosized airflow causes W2A <25% rated flow warnings.",
                "affects": ["warnings", "peak", "temperature_dynamics"],
            },
        ],
    }
    (out_dir / "parameter_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(body["all_train_dev"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
