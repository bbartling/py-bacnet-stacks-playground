"""Independently reproduce the physics-ramp gate from LIVE EnergyPlus.

Does not raise ENGINEERING_MARGIN. Writes interval-level diagnostics.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.objective import BAS_ZONE_COLS
from eplus_gym.rl.live_day_worker import run_live_day_subprocess
from eplus_gym.rl.physics_ramp_gate import ENGINEERING_MARGIN, evaluate_ramp_gate
from eplus_gym.six_zone_daily_controller import SixZoneDailyParams, incumbent_lookback_params

SP_COLS = tuple("htg_sp_applied_" + c[len("zone_temp_") :] for c in BAS_ZONE_COLS)


def ep_clock_index(frame: pd.DataFrame, fallback_day: str) -> pd.DatetimeIndex:
    """Use gym local_step (true 15-min MDP), not EnergyPlus clock fields.

    ep_hour/ep_minute on A04 trajectories are not a unique 15-minute grid
    (duplicate 23:60, stray minutes). Those fields are diagnostic only.
    """
    df = frame.reset_index(drop=True)
    day0 = datetime.fromisoformat(str(fallback_day)[:10])
    stamps = []
    for _, row in df.iterrows():
        local = int(row["local_step"]) if "local_step" in df.columns else int(_)
        look = bool(row["lookback"]) if "lookback" in df.columns else False
        origin = day0 - timedelta(days=1) if look else day0
        stamps.append(origin + timedelta(minutes=15 * (local + 1)))
    return pd.DatetimeIndex(stamps)


def with_dt_index(frame: pd.DataFrame, day: str) -> pd.DataFrame:
    out = frame.copy()
    out.index = ep_clock_index(out, day)
    if not out.index.is_unique:
        out = out.groupby(level=0).last()
    return out.sort_index()


def locate_breaches(sim: pd.DataFrame, threshold: float) -> pd.DataFrame:
    rows = []
    temps = sim[list(BAS_ZONE_COLS)].astype(float)
    deltas = temps.diff().abs()
    for col in BAS_ZONE_COLS:
        series = deltas[col]
        for ts, val in series.items():
            if pd.isna(val) or float(val) <= threshold:
                continue
            prev = temps[col].shift(1).loc[ts]
            rec = {
                "timestamp": ts.isoformat(),
                "zone": col,
                "delta_f": float(val),
                "zone_temp_f": float(temps[col].loc[ts]),
                "prior_zone_temp_f": float(prev) if pd.notna(prev) else None,
                "local_step": int(sim.loc[ts]["local_step"]) if "local_step" in sim.columns else None,
                "lookback": bool(sim.loc[ts]["lookback"]) if "lookback" in sim.columns else False,
                "facility_kw": float(sim.loc[ts]["facility_kw"]) if "facility_kw" in sim.columns else None,
                "oat_c": float(sim.loc[ts]["oat_c"]) if "oat_c" in sim.columns else None,
            }
            sp = "htg_sp_applied_" + col[len("zone_temp_") :]
            if sp in sim.columns:
                rec["heating_setpoint_f"] = float(sim.loc[ts][sp])
            rows.append(rec)
    return pd.DataFrame(rows)


def plot_offenders(sim: pd.DataFrame, breaches: pd.DataFrame, threshold: float, dest: Path, title: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
    hours = np.arange(len(sim)) * 0.25
    for col in BAS_ZONE_COLS:
        axes[0].plot(hours, sim[col].astype(float).to_numpy(), lw=1, label=col.replace("zone_temp_", "").replace("_f", ""))
    axes[0].set_ylabel("Zone T (°F)")
    axes[0].legend(ncol=3, fontsize=7, loc="upper right")
    dmax = sim[list(BAS_ZONE_COLS)].astype(float).diff().abs().max(axis=1)
    axes[1].plot(hours, dmax.to_numpy(), color="#b22d3c")
    axes[1].axhline(threshold, color="#444", ls="--", label=f"threshold {threshold:.3f}°F")
    axes[1].set_ylabel("max |ΔT| °F/15min")
    axes[1].legend(fontsize=8)
    if "facility_kw" in sim.columns:
        axes[2].plot(hours, sim["facility_kw"].astype(float).to_numpy(), color="#127d8e")
    axes[2].set_ylabel("Facility kW")
    if "oat_c" in sim.columns:
        axes[3].plot(hours, sim["oat_c"].astype(float).to_numpy(), color="#2b6cb0")
        axes[3].set_ylabel("OAT °C")
    axes[3].set_xlabel("Hours from series start")
    fig.suptitle(title, fontsize=12)
    fig.text(0.5, 0.01, "EnergyPlus screening experiment; not an operational recommendation.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    fig.savefig(dest, dpi=140)
    plt.close(fig)
    if not breaches.empty:
        breaches.to_csv(dest.with_suffix(".csv"), index=False)


def bas_frame(path: Path) -> pd.DataFrame:
    raw = pd.read_parquet(path)
    if not isinstance(raw.index, pd.DatetimeIndex):
        for c in ("timestamp_local", "timestamp_utc", "timestamp", "time", "datetime"):
            if c in raw.columns:
                raw = raw.set_index(pd.to_datetime(raw[c]))
                break
        else:
            raise ValueError("BAS parquet needs a DatetimeIndex")
    missing = [c for c in BAS_ZONE_COLS if c not in raw.columns]
    if missing:
        raise ValueError(f"BAS missing {missing}")
    raw = raw.sort_index()
    # resample to 15 min for gate continuity
    sub = raw[list(BAS_ZONE_COLS)].astype(float)
    sub = sub[~sub.index.duplicated(keep="last")]
    return sub


def run_arm(site: Path, epw: Path, idf: Path, out: Path, day: str, params: SixZoneDailyParams, name: str) -> pd.DataFrame:
    ep_dir = out / name
    pq = ep_dir / "trajectory.parquet"
    if pq.is_file() and (ep_dir / "trajectory_all.parquet").is_file():
        scored = pd.read_parquet(pq)
        scored.attrs["all_path"] = str(ep_dir / "trajectory_all.parquet")
        return scored
    payload = run_live_day_subprocess(
        site_root=site,
        epw=epw,
        champion_idf=idf,
        day=day,
        params=params.to_dict(),
        ep_dir=ep_dir,
        lookback_days=1,
        reward_name="legacy_reward_v1",
    )
    if payload.get("failed"):
        raise RuntimeError(f"{name} failed: {payload}")
    q = payload.get("eplus_quality") or {}
    if int(q.get("severe_count") or 0) or int(q.get("fatal_count") or 0):
        raise RuntimeError(f"{name} Severe/Fatal: {q}")
    if int(payload.get("n_rows") or 0) != 96 or int(payload.get("n_all_rows") or 0) != 192:
        raise RuntimeError(f"{name} row counts {payload.get('n_rows')} {payload.get('n_all_rows')}")
    scored = pd.read_parquet(payload["trajectory"])
    all_rows = pd.read_parquet(payload["trajectory_all"])
    scored.attrs["payload"] = {k: payload[k] for k in ("n_rows", "n_all_rows", "peak_kw", "daily_kwh") if k in payload}
    scored.attrs["all_path"] = str(payload["trajectory_all"])
    (ep_dir / "arm_meta.json").write_text(json.dumps({"arm": name, "n_rows": payload["n_rows"], "n_all_rows": payload["n_all_rows"]}, indent=2) + "\n")
    all_rows.to_parquet(ep_dir / "trajectory_all.parquet", index=False)
    return scored


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", type=Path, default=Path(os.environ.get("SITE_ROOT") or ""))
    p.add_argument("--day", default="2026-01-26")
    p.add_argument("--out", type=Path, default=_APP / "docs" / "audits" / "figures" / "postfix" / "ramp_repro")
    args = p.parse_args()
    site = args.site_root
    if not site.is_dir():
        print("SITE_ROOT required", file=sys.stderr)
        return 2
    epw = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    idf = _APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    bas_path = site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet"
    args.out.mkdir(parents=True, exist_ok=True)

    real_idx = bas_frame(bas_path)

    arms = {
        "incumbent": incumbent_lookback_params(),
        "low_unocc": SixZoneDailyParams(occupied_heating_f=68.0, unoccupied_heating_f=58.0),
        "high_occ": SixZoneDailyParams(occupied_heating_f=72.0, unoccupied_heating_f=68.0, recovery_ramp_minutes=0),
    }
    reports: dict[str, Any] = {}
    for name, params in arms.items():
        scored = run_arm(site, epw, idf, args.out, args.day, params, name)
        sim = with_dt_index(scored, args.day)
        # Align BAS to 15-min for threshold only (full history)
        gate = evaluate_ramp_gate(simulated=sim[list(BAS_ZONE_COLS)], real_bas=real_idx[list(BAS_ZONE_COLS)])
        breaches = locate_breaches(sim, float(gate["threshold_f_per_15min"]))
        plot_offenders(
            sim,
            breaches,
            float(gate["threshold_f_per_15min"]),
            args.out / f"{name}_intervals.png",
            f"{name} Jan 26 LIVE A04 — scored 96 rows",
        )
        all_path = Path(scored.attrs["all_path"])
        all_df = with_dt_index(pd.read_parquet(all_path), args.day)
        splice = None
        if len(all_df) == 192:
            look = all_df[all_df["lookback"] == True] if "lookback" in all_df.columns else all_df.iloc[:96]
            tgt = all_df[all_df["lookback"] == False] if "lookback" in all_df.columns else all_df.iloc[96:]
            if len(look) and len(tgt):
                last = look[list(BAS_ZONE_COLS)].astype(float).iloc[-1]
                first = tgt[list(BAS_ZONE_COLS)].astype(float).iloc[0]
                splice = {c: float(abs(first[c] - last[c])) for c in BAS_ZONE_COLS}
        reports[name] = {
            "gate": gate,
            "n_breaches": int(len(breaches)),
            "breach_max": float(breaches["delta_f"].max()) if len(breaches) else 0.0,
            "lookback_target_splice_abs_f": splice,
            "n_rows": 96,
            "n_all_rows": 192,
        }

    # Combined artifact matching committed schema
    inc = reports["incumbent"]["gate"]
    low = reports["low_unocc"]["gate"]
    high = reports["high_occ"]["gate"]
    passed = bool(inc["passed"] and low["passed"] and high["passed"])
    artifact = {
        "schema": "vibe22.physics_ramp_gate.v1",
        "arm": "incumbent_low_high_jan26",
        "engineering_margin": ENGINEERING_MARGIN,
        "threshold_rule": "bas_p99_9 * engineering_margin",
        "threshold_f_per_15min": inc["threshold_f_per_15min"],
        "incumbent_simulated_max_f_per_15min": inc["simulated_max_f_per_15min"],
        "perturbed_simulated_max_f_per_15min": low["simulated_max_f_per_15min"],
        "high_occ_simulated_max_f_per_15min": high["simulated_max_f_per_15min"],
        "bas_quantiles_f_per_15min": inc["bas_quantiles_f_per_15min"],
        "passed": passed,
        "verdict": inc["verdict"] if passed else inc["verdict"],
        "per_arm": {k: {"passed": v["gate"]["passed"], "max": v["gate"]["simulated_max_f_per_15min"], "splice": v["lookback_target_splice_abs_f"], "n_breaches": v["n_breaches"]} for k, v in reports.items()},
        "notes": "Newly generated from LIVE EnergyPlus; threshold not retuned.",
    }
    if not passed:
        artifact["verdict"] = "NO_GO_LONG_RL_TRAINING_PHYSICS_RAMP_IMPLAUSIBLE"
    dest = _APP / "docs" / "audits" / "figures" / "postfix" / "ramp_gate.json"
    dest.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    (args.out / "ramp_repro.json").write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
