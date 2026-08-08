#!/usr/bin/env python3
"""Bounded IdealLoads schedule/calendar/OA/capacity sanity campaign (3–6 real E+ runs).

Not an equip/infil multiplier sweep. DSM remains NO-GO.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_native.runner import energyplus_version, run_energyplus  # noqa: E402
from eplus_native.schedule_calendar_repair import (  # noqa: E402
    load_calendar_contract,
    repair_idf_file,
)
from eplus_validation_contract import (  # noqa: E402
    build_hourly_and_15min,
    score_aligned,
    utility_monthly_from_trial_sim,
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _site_root() -> Path:
    env = os.environ.get("LAKESIDE_SITE_ROOT")
    if not env:
        raise SystemExit("LAKESIDE_SITE_ROOT required")
    return Path(env)


def _champion_idf(site: Path) -> Path:
    freeze = sorted((site / "eplus" / "campaigns").glob("freeze_pre_schedule_plant_*/champion_B_equip_mult_mid_model.idf"))
    if freeze:
        return freeze[-1]
    p = site / "eplus" / "campaigns" / "bounded_exec_20260807" / "trials" / "B_equip_mult_mid" / "model.idf"
    if p.is_file():
        return p
    raise FileNotFoundError("champion IDF not found")


def _epw(site: Path) -> Path:
    p = site / "eplus" / "weather" / "madison_amy_202508_202607.epw"
    if not p.is_file():
        raise FileNotFoundError(p)
    return p


def structural_metrics(aligned_h: pd.DataFrame) -> dict[str, Any]:
    """Local-civil overnight/weekend structure (honesty gate after P1)."""
    df = aligned_h.copy()
    ts = pd.to_datetime(df["timestamp_utc"], utc=True).dt.tz_convert("America/Chicago")
    df = df.assign(ts=ts, hod=ts.dt.hour, dow=ts.dt.dayofweek, month=ts.dt.month)
    winter = df[df["month"].isin([12, 1, 2])]
    wknd = winter[winter["dow"] >= 5]
    night = winter[winter["hod"].isin([0, 1, 2, 3, 4, 5])]
    wkdy = winter[winter["dow"] < 5]

    def _m(series: pd.Series) -> float | None:
        return float(series.mean()) if len(series) else None

    return {
        "winter_weekend_kw_mod_mean": _m(wknd["kw_mod"]),
        "winter_weekend_kw_meas_mean": _m(wknd["kw_meas"]),
        "winter_overnight_kw_mod_mean": _m(night["kw_mod"]),
        "winter_overnight_kw_meas_mean": _m(night["kw_meas"]),
        "winter_weekday_kw_mod_mean": _m(wkdy["kw_mod"]),
        "winter_weekday_kw_meas_mean": _m(wkdy["kw_meas"]),
        "weekend_collapse_ratio_mod_over_meas": (
            (_m(wknd["kw_mod"]) / _m(wknd["kw_meas"]))
            if _m(wknd["kw_meas"]) not in (None, 0.0)
            else None
        ),
    }


def _score_trial(site: Path, sim_dir: Path, *, heat_cop: float, cool_cop: float) -> dict[str, Any]:
    packed = build_hourly_and_15min(site, sim_dir, heat_cop=heat_cop, cool_cop=cool_cop)
    hourly = packed["hourly"].copy()
    # expected columns: interval_end_utc, observed_kw, simulated_kw
    hourly = hourly.rename(
        columns={
            "observed_kw": "kw_meas",
            "simulated_kw": "kw_mod",
            "interval_end_utc": "timestamp_utc",
        }
    )
    sc_h = score_aligned(
        packed["hourly"],
        resolution="hourly",
    )
    util = utility_monthly_from_trial_sim(site, sim_dir, heat_cop=heat_cop, cool_cop=cool_cop)
    return {
        "hourly_score": sc_h,
        "utility_monthly": util,
        "structural": structural_metrics(hourly),
    }


def run_one(
    *,
    camp: Path,
    trial_id: str,
    idf_path: Path,
    epw: Path,
    site: Path,
    heat_cop: float = 3.5,
    cool_cop: float = 4.5,
    copy_sim_from: Path | None = None,
) -> dict[str, Any]:
    trial_dir = camp / "trials" / trial_id
    sim_dir = trial_dir / "sim"
    trial_dir.mkdir(parents=True, exist_ok=True)
    staged = trial_dir / "trial.idf"
    if Path(idf_path).resolve() != staged.resolve():
        shutil.copy2(idf_path, staged)

    result: dict[str, Any] = {
        "trial_id": trial_id,
        "started_utc": _utc(),
        "trial_idf": str(staged.resolve()),
        "trial_idf_sha256": sha256_file(staged),
        "epw_sha256": sha256_file(epw),
        "status": "running",
    }
    if copy_sim_from and (copy_sim_from / "eplusmtr.csv").is_file():
        if sim_dir.exists():
            shutil.rmtree(sim_dir, ignore_errors=True)
        shutil.copytree(copy_sim_from, sim_dir)
        result["energyplus"] = {
            "version": energyplus_version(),
            "exit_code": 0,
            "accepted": True,
            "runtime_sec": 0.0,
            "reused_sim_from": str(copy_sim_from.resolve()),
        }
    else:
        man = run_energyplus(
            run_id=f"{camp.name}_{trial_id}",
            scenario_id=trial_id,
            idf_path=staged,
            epw_path=epw,
            output_dir=sim_dir,
            heat_cop=heat_cop,
            cool_cop=cool_cop,
            require_zero_severe=False,
            allow_staged_idf=True,
        )
        result["energyplus"] = {
            "version": energyplus_version(),
            "exit_code": man.exit_code,
            "accepted": man.accepted,
            "severe_count": man.severe_count,
            "fatal_count": man.fatal_count,
            "reject_reasons": list(man.reject_reasons or []),
            "runtime_sec": man.runtime_sec,
        }
        if man.exit_code != 0 or not (sim_dir / "eplusmtr.csv").is_file():
            result["status"] = "failed"
            result["ended_utc"] = _utc()
            (trial_dir / "trial_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return result

    out_hashes = {}
    for name in ("eplusout.err", "eplusmtr.csv", "eplusout.csv"):
        p = sim_dir / name
        if p.is_file():
            out_hashes[name] = sha256_file(p)
    result["output_sha256"] = out_hashes
    try:
        result["metrics"] = _score_trial(site, sim_dir, heat_cop=heat_cop, cool_cop=cool_cop)
        result["status"] = "succeeded"
    except Exception as e:
        result["status"] = "failed"
        result["score_error"] = f"{type(e).__name__}: {e}"
    result["ended_utc"] = _utc()
    (trial_dir / "trial_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def gate_structural(baseline: dict[str, Any], repaired: dict[str, Any]) -> dict[str, Any]:
    b = (baseline.get("metrics") or {}).get("structural") or {}
    r = (repaired.get("metrics") or {}).get("structural") or {}
    b_wk = b.get("winter_weekend_kw_mod_mean")
    r_wk = r.get("winter_weekend_kw_mod_mean")
    b_nt = b.get("winter_overnight_kw_mod_mean")
    r_nt = r.get("winter_overnight_kw_mod_mean")
    improved = False
    reasons = []
    if b_wk is not None and r_wk is not None:
        # material improvement: leave ~12.4 kW floor
        if r_wk >= max(b_wk * 1.5, 25.0):
            improved = True
            reasons.append(f"weekend_kw_mod {b_wk:.2f} → {r_wk:.2f}")
        else:
            reasons.append(f"weekend_kw_mod insufficient {b_wk:.2f} → {r_wk:.2f}")
    if b_nt is not None and r_nt is not None and r_nt >= max(b_nt * 1.5, 25.0):
        improved = True
        reasons.append(f"overnight_kw_mod {b_nt:.2f} → {r_nt:.2f}")
    return {
        "hourly_structure_improved": improved,
        "reasons": reasons,
        "baseline_structural": b,
        "repaired_structural": r,
        "next": "continue_P2_P3_P4" if improved else "NO-GO_skip_large_P3_P4_may_finish_P2_diagnostics",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign-id", default=None)
    ap.add_argument("--reuse-frozen-sim", action="store_true", default=True)
    ap.add_argument("--no-reuse-frozen-sim", action="store_true")
    args = ap.parse_args(argv)

    site = _site_root()
    cal = load_calendar_contract()
    cid = args.campaign_id or f"schedule_sanity_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    camp = site / "eplus" / "campaigns" / cid
    camp.mkdir(parents=True, exist_ok=True)
    idf0 = _champion_idf(site)
    epw = _epw(site)
    staged_dir = camp / "staged_idfs"
    staged_dir.mkdir(exist_ok=True)

    variants = [
        ("S0_frozen_original", None, None, True),
        ("S1_schedule_calendar_oa", None, None, False),
        ("S2_cap_low_2p3", 2.3, None, False),
        ("S3_cap_mid_2p7", 2.7, None, False),
        ("S4_cap_high_3p2", 3.2, None, False),
        ("S5_opt_start_sens", 2.7, 1.0, False),
    ]

    results = []
    for tid, cap, lead, is_frozen in variants:
        if is_frozen:
            idf_path = idf0
            reuse = None
            if not args.no_reuse_frozen_sim:
                reuse = (
                    site
                    / "eplus"
                    / "campaigns"
                    / "bounded_exec_20260807"
                    / "trials"
                    / "B_equip_mult_mid"
                    / "sim"
                )
        else:
            dst = staged_dir / f"{tid}.idf"
            repair_idf_file(
                idf0,
                dst,
                heating_capacity_mmbtu_h=cap,
                optimum_start_hours=lead,
            )
            idf_path = dst
            reuse = None
        print(f"RUN {tid} …", flush=True)
        results.append(
            run_one(
                camp=camp,
                trial_id=tid,
                idf_path=idf_path,
                epw=epw,
                site=site,
                copy_sim_from=reuse if is_frozen else None,
            )
        )

    by_id = {r["trial_id"]: r for r in results}
    gate = gate_structural(by_id["S0_frozen_original"], by_id["S1_schedule_calendar_oa"])
    summary = {
        "campaign_id": cid,
        "created_utc": _utc(),
        "calendar_contract": "eplus_school_calendar_v1",
        "energyplus_version": energyplus_version(),
        "champion_parent_sha256": sha256_file(idf0),
        "planned_trials": len(variants),
        "succeeded": sum(1 for r in results if r.get("status") == "succeeded"),
        "failed": sum(1 for r in results if r.get("status") != "succeeded"),
        "trials": results,
        "p1_gate": gate,
        "dsm_status": "NO-GO",
        "honesty": "IdealLoads schedule/calendar sanity only; not GSHP plant; not DSM-eligible",
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (camp / "p1_gate.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    # repo mirror (no client identity)
    repo_mirror = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-schedule-sanity-summary.json"
    slim = {
        "campaign_id": cid,
        "succeeded": summary["succeeded"],
        "failed": summary["failed"],
        "p1_gate": gate,
        "dsm_status": "NO-GO",
        "trial_ids": [r["trial_id"] for r in results],
        "trial_status": {r["trial_id"]: r.get("status") for r in results},
    }
    repo_mirror.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(slim, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
