"""Jan 26 cold-day bridge study — same A04 physics, schedule-only arm differences.

Inspected diagnostic day (not pristine holdout). No RL training. No BACnet.

Each EnergyPlus arm runs in a fresh subprocess to avoid Windows API heap corruption
when chaining LakesideW2AEnv + ContinuityPlant in one interpreter.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

DAY = "2026-01-26"
PUBLIC = [
    "RESEARCH POLICY SCREENING ONLY",
    "NO VERIFIED 285 kW DEMAND REDUCTION CLAIM",
    "NO OPERATIONAL DSM AUTHORITY",
    "JAN26_IS_INSPECTED_DIAGNOSTIC_NOT_HOLDOUT",
]


def _rolling_max(x: list[float], window: int) -> float:
    if len(x) < window:
        return float(max(x)) if x else 0.0
    best = 0.0
    for i in range(len(x) - window + 1):
        best = max(best, float(np.mean(x[i : i + window])))
    return best


def _worker(payload: dict[str, Any]) -> dict[str, Any]:
    """Run a single arm inside this process (invoked via --worker-json)."""
    from eplus_gym.a04_identity import A04_IDF_NAME
    from eplus_gym.control_v2 import continuous_params, deep_setback_params, observed_bas_incumbent_params
    from eplus_gym.rl.campaign_bundle import forecasts_from_epw
    from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant
    from eplus_gym.rl.multiday_env import schedule_fingerprint
    from eplus_gym.rl.research_poc import refuse_fake_plant
    from eplus_gym.rl.research_spaces import decode_discrete_research_v3, research_build_six_schedules_f
    from eplus_gym.site_env import require_site_root
    from eplus_gym.site_pins import resolve_site_epw, sha256_file
    from scripts.a04v2_compare_incumbent_schedules import SchHtgSpReplay, run_arm as run_native_arm

    site = require_site_root(Path(payload["site_root"]) if payload.get("site_root") else None)
    day = str(payload["day"])[:10]
    lookback = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    arm = str(payload["arm"])
    out_root = Path(payload["out_root"])
    out_root.mkdir(parents=True, exist_ok=True)
    idf = _APP / "models" / "eplus" / A04_IDF_NAME
    epw = resolve_site_epw(site)
    oat = forecasts_from_epw(epw, [day])[day]

    if arm == "a04_native_sch_htgsp":
        native = run_native_arm(
            site=site,
            epw=epw,
            idf=idf,
            out=out_root / arm,
            begin=lookback,
            end=day,
            controller=SchHtgSpReplay(
                scored_weekday=date.fromisoformat(day).weekday(),
                lookback_weekday=date.fromisoformat(lookback).weekday(),
            ),
            six_zone=False,
        )
        import pandas as pd
        from eplus_gym.objective import _facility_series

        df = pd.read_parquet(out_root / arm / "trajectory.parquet")
        fac_all = _facility_series(df).tolist()
        fac = [float(x) for x in fac_all[-96:]]
        return {
            "label": "A04_NATIVE_CALIBRATION_REFERENCE",
            "facility_kw": fac,
            "peak_kw": float(max(fac)),
            "daily_kwh": float(sum(fac) * 0.25),
            "peak_30min_mean_kw": _rolling_max(fac, 2),
            "peak_60min_mean_kw": _rolling_max(fac, 4),
            "n_intervals": 96,
            "n_process_starts": 1,
            "schedule_fingerprint": "SCH_HtgSP_native_replay",
            "baseline_contract_name": "A04_NATIVE_CALIBRATION_REFERENCE",
            "six_zone": False,
            "native_report": native,
            "idf_sha256": sha256_file(idf),
            "epw_sha256": sha256_file(epw),
            "epw_path": str(epw),
        }

    def run_six(name: str, params, contract: str, extra: dict | None = None) -> dict[str, Any]:
        sched = research_build_six_schedules_f(params, day)
        plant = EnergyPlusContinuityPlant(
            site_root=site, epw=epw, idf=idf, output=out_root / name, days=[day], queue_timeout_s=600.0
        )
        refuse_fake_plant(plant)
        t0 = time.perf_counter()
        plant.start_episode()
        payload_day = plant.simulate_day(sched, oat_c=list(oat))
        quality = plant.finish_quality()
        fac = [float(x) for x in payload_day["facility_kw"]]
        out = {
            "label": name,
            "facility_kw": fac,
            "peak_kw": float(max(fac)),
            "daily_kwh": float(payload_day["daily_kwh"]),
            "peak_30min_mean_kw": _rolling_max(fac, 2),
            "peak_60min_mean_kw": _rolling_max(fac, 4),
            "zone_temps_series_f": payload_day.get("zone_temps_series_f"),
            "n_intervals": 96,
            "n_process_starts": int(plant.n_process_starts),
            "elapsed_s": time.perf_counter() - t0,
            "quality": quality,
            "schedule_fingerprint": schedule_fingerprint(sched),
            "schedules_f": sched,
            "start_zone_temps_f": payload_day.get("start_zone_temps_f"),
            "baseline_contract_name": contract,
            "params": {
                "occupied_heating_f": params.occupied_heating_f,
                "unoccupied_heating_f": params.unoccupied_heating_f,
                "recovery_lead_minutes": params.recovery_lead_minutes,
                "continuous_conditioning": params.continuous_conditioning,
                "post_occupancy_extension_minutes": getattr(params, "post_occupancy_extension_minutes", 0),
            },
            "idf_sha256": sha256_file(idf),
            "epw_sha256": sha256_file(epw),
            "epw_path": str(epw),
        }
        if extra:
            out.update(extra)
        return out

    if arm == "observed_bas_incumbent_v2":
        return run_six(arm, observed_bas_incumbent_params(), "OBSERVED_BAS_INCUMBENT_V2_HISTORICAL")
    if arm == "continuous_68_heat_sensitivity":
        return run_six(arm, continuous_params(68.0), "CONTINUOUS_DUALSP_68_74_SENSITIVITY_UNVERIFIED")
    if arm == "grid_flat_discrete_42":
        return run_six(arm, decode_discrete_research_v3(42, day=day), "POLICY_CANDIDATE_GRID_FLAT")
    if arm == "grid_tou_discrete_43":
        return run_six(arm, decode_discrete_research_v3(43, day=day), "POLICY_CANDIDATE_GRID_TOU")
    if arm == "fixed_rule_deep_setback":
        return run_six(arm, deep_setback_params(), "POLICY_CANDIDATE_FIXED_RULE_DEEP_SETBACK")

    if arm in ("frozen_ppo_flat_seed0", "frozen_dqn_tou_seed1"):
        from eplus_gym.rl.research_eval import load_sb3_model
        from eplus_gym.rl.research_spaces import decode_continuous_research_v3

        zpath = Path(payload["policy_zip"])
        algo = str(payload["algo"])
        if not zpath.is_file():
            return {"status": "NOT_RUN_MISSING_POLICY_ZIP", "path": str(zpath)}
        model = load_sb3_model(zpath, algo=algo)
        obs_dim = int(getattr(model.observation_space, "shape", [1])[0])
        obs = np.zeros((obs_dim,), dtype=np.float32)
        action, _ = model.predict(obs, deterministic=True)
        if algo.upper() == "DQN":
            params = decode_discrete_research_v3(int(action), day=day)
        else:
            params = decode_continuous_research_v3(np.asarray(action, dtype=np.float32), day=day)
        return run_six(
            arm,
            params,
            f"POLICY_CANDIDATE_{arm.upper()}",
            extra={
                "policy_zip": str(zpath),
                "policy_bundle_sha256": sha256_file(zpath),
                "action_decode_note": (
                    "DIAGNOSTIC: action from zeroed observation vector — not a full MultiDayDailyEnv "
                    "state replay. Treat as schedule-menu probe of frozen weights, not operational claim."
                ),
            },
        )

    raise ValueError(f"unknown arm {arm}")


def _run_arm_subprocess(*, site: Path, out_root: Path, day: str, arm: str, extra: dict | None = None) -> dict[str, Any]:
    payload = {"site_root": str(site), "out_root": str(out_root), "day": day, "arm": arm}
    if extra:
        payload.update(extra)
    tmp = out_root / f"_worker_{arm}.json"
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    result_path = out_root / f"_result_{arm}.json"
    cmd = [sys.executable, "-u", str(Path(__file__).resolve()), "--worker-json", str(tmp), "--result-json", str(result_path)]
    print(f"arm: {arm}", flush=True)
    proc = subprocess.run(cmd, cwd=str(_APP), capture_output=True, text=True)
    if proc.returncode != 0:
        return {
            "status": "FAILED",
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-4000:],
            "stderr": (proc.stderr or "")[-4000:],
        }
    return json.loads(result_path.read_text(encoding="utf-8"))


def _plots(out_root: Path, results: dict[str, Any], table: list[dict], native_peak: float, bas_peak: float) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    compact = {
        k: {"facility_kw": v.get("facility_kw"), "peak_kw": v.get("peak_kw")}
        for k, v in results.items()
        if "facility_kw" in v
    }
    (out_root / "bridge_trajectories_compact.json").write_text(json.dumps(compact), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(11, 5))
    for name, v in compact.items():
        ax.plot(v["facility_kw"], label=f"{name} ({v['peak_kw']:.1f} kW)", linewidth=1.5)
    ax.set_xlabel("15-min step")
    ax.set_ylabel("Facility kW")
    ax.set_title("Cold-day bridge facility kW @ 2026-01-26 (diagnostic)")
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.savefig(out_root / "fig1_facility_kw_trajectories.png", dpi=140, bbox_inches="tight")
    fig.savefig(out_root / "fig1_facility_kw_trajectories.svg", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    for row in table:
        if "peak_kw" in row:
            ax.scatter(row["daily_kwh"], row["peak_kw"], s=80)
            ax.annotate(row["arm"], (row["daily_kwh"], row["peak_kw"]), fontsize=7)
    ax.set_xlabel("Daily kWh")
    ax.set_ylabel("Peak kW")
    ax.set_title("Peak vs daily kWh (Jan 26 bridge)")
    ax.grid(True, alpha=0.3)
    fig.savefig(out_root / "fig2_peak_vs_kwh.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # Cost proxy: daily_kwh * flat rate + peak * demand rate (illustrative only)
    fig, ax = plt.subplots(figsize=(7, 5))
    for row in table:
        if "peak_kw" not in row:
            continue
        cost = float(row["daily_kwh"]) * 0.11 + float(row["peak_kw"]) * 12.0
        ready = 1.0 if "continuous" not in row["arm"] else 0.5
        ax.scatter(cost, ready, s=80)
        ax.annotate(row["arm"], (cost, ready), fontsize=7)
    ax.set_xlabel("Illustrative cost proxy ($)")
    ax.set_ylabel("Readiness proxy (diagnostic)")
    ax.set_title("Cost vs readiness proxy (not operational)")
    ax.grid(True, alpha=0.3)
    fig.savefig(out_root / "fig3_cost_vs_readiness_proxy.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # Zone temps for observed_bas and lowest-peak candidate among six-zone arms
    bas = results.get("observed_bas_incumbent_v2") or {}
    candidates = [
        (k, v)
        for k, v in results.items()
        if k != "observed_bas_incumbent_v2" and isinstance(v, dict) and v.get("zone_temps_series_f")
    ]
    best = min(candidates, key=lambda kv: float(kv[1].get("peak_kw") or 1e9), default=None)
    if bas.get("zone_temps_series_f") and best:
        fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
        for ax, (name, blob) in zip(axes, (("observed_bas_incumbent_v2", bas), best)):
            z = blob["zone_temps_series_f"]
            for zk, series in z.items():
                ax.plot(series, label=zk, linewidth=1.0)
            ax.set_ylabel("Zone °F")
            ax.set_title(f"{name} zones (peak {blob.get('peak_kw'):.1f} kW)")
            ax.legend(fontsize=6, ncol=3)
            ax.grid(True, alpha=0.3)
        axes[-1].set_xlabel("15-min step")
        fig.savefig(out_root / "fig4_six_zone_temps.png", dpi=140, bbox_inches="tight")
        plt.close(fig)

    # Setpoint schedules
    fig, ax = plt.subplots(figsize=(10, 5))
    for name, v in results.items():
        sched = v.get("schedules_f") if isinstance(v, dict) else None
        if not sched:
            continue
        # plot mean across zones
        arr = np.mean([np.asarray(s, dtype=float) for s in sched.values()], axis=0)
        ax.plot(arr, label=name, linewidth=1.5)
    ax.set_ylabel("Heating setpoint °F (zone mean)")
    ax.set_xlabel("15-min step")
    ax.set_title("Setpoint schedules by arm")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)
    fig.savefig(out_root / "fig5_setpoint_schedules.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    labels = [
        "Utility Jan\nbilled",
        "A04 native\nJan26",
        "Gym 70/65\nJan26 (hist)",
        "Obs BAS v2\nJan26",
        "Dec RL incumb\n(max)",
        "Dec DQN\n(max)",
    ]
    vals = [284.82, native_peak, 239.77, bas_peak, 201.88, 211.51]
    ax.bar(labels, vals, color=["#555555", "#1f4e79", "#888888", "#0b6e4f", "#c45c26", "#c45c26"])
    ax.set_ylabel("Peak kW")
    ax.set_title("Why ~285, ~240, and ~202 kW were different (not interchangeable)")
    ax.grid(True, axis="y", alpha=0.3)
    fig.savefig(out_root / "fig7_why_peaks_differ.png", dpi=140, bbox_inches="tight")
    fig.savefig(out_root / "fig7_why_peaks_differ.svg", bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site-root", type=Path, default=None)
    p.add_argument("--day", default=DAY)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=_APP / "docs" / "audits" / "figures" / "vibe22_cold_day_bridge",
    )
    p.add_argument("--worker-json", type=Path, default=None)
    p.add_argument("--result-json", type=Path, default=None)
    args = p.parse_args()

    if args.worker_json is not None:
        payload = json.loads(Path(args.worker_json).read_text(encoding="utf-8"))
        result = _worker(payload)
        out = Path(args.result_json) if args.result_json else Path(args.worker_json).with_name("_result.json")
        out.write_text(json.dumps(result), encoding="utf-8")
        return 0

    from eplus_gym.site_env import require_site_root
    from eplus_gym.site_pins import resolve_site_epw, sha256_file
    from eplus_gym.a04_identity import A04_IDF_NAME

    site = require_site_root(args.site_root)
    day = str(args.day)[:10]
    lookback = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    idf = _APP / "models" / "eplus" / A04_IDF_NAME
    epw = resolve_site_epw(site)
    idf_sha = sha256_file(idf)
    epw_sha = sha256_file(epw)

    ppo_zip = (
        site
        / "reports/eplus_gym/rl/research_long_flat_plus_demand_20260820T132506Z/ppo_seed0/models/ppo_final.zip"
    )
    dqn_zip = (
        site
        / "reports/eplus_gym/rl/research_long_illustrative_tou_plus_demand_20260820T210304Z/dqn_seed1/models/dqn_final.zip"
    )

    arm_specs: list[tuple[str, dict | None]] = [
        ("a04_native_sch_htgsp", None),
        ("observed_bas_incumbent_v2", None),
        ("continuous_68_heat_sensitivity", None),
        ("grid_flat_discrete_42", None),
        ("grid_tou_discrete_43", None),
        ("fixed_rule_deep_setback", None),
        ("frozen_ppo_flat_seed0", {"policy_zip": str(ppo_zip), "algo": "PPO"}),
        ("frozen_dqn_tou_seed1", {"policy_zip": str(dqn_zip), "algo": "DQN"}),
    ]

    results: dict[str, Any] = {}
    launches = 0
    for arm, extra in arm_specs:
        r = _run_arm_subprocess(site=site, out_root=out_root, day=day, arm=arm, extra=extra)
        results[arm] = r
        launches += int(r.get("n_process_starts") or 0)

    native_peak = float(results["a04_native_sch_htgsp"].get("peak_kw") or 0)
    bas_peak = float(results["observed_bas_incumbent_v2"].get("peak_kw") or 0)
    table = []
    for name, r in results.items():
        if "peak_kw" not in r:
            table.append({"arm": name, **{k: r.get(k) for k in ("status", "error", "returncode", "stderr")}})
            continue
        table.append(
            {
                "arm": name,
                "peak_kw": round(float(r["peak_kw"]), 4),
                "daily_kwh": round(float(r["daily_kwh"]), 4),
                "peak_30min_mean_kw": round(float(r.get("peak_30min_mean_kw") or 0), 4),
                "peak_60min_mean_kw": round(float(r.get("peak_60min_mean_kw") or 0), 4),
                "delta_vs_a04_native_kw": round(float(r["peak_kw"]) - native_peak, 4),
                "delta_vs_observed_bas_v2_kw": round(float(r["peak_kw"]) - bas_peak, 4),
                "delta_vs_native_label": "DIAGNOSTIC_NOT_OPERATIONAL_COUNTERFACTUAL",
                "schedule_fingerprint": r.get("schedule_fingerprint"),
                "baseline_contract_name": r.get("baseline_contract_name"),
                "n_process_starts": r.get("n_process_starts"),
                "severe_count": (r.get("quality") or {}).get("severe_count"),
                "fatal_count": (r.get("quality") or {}).get("fatal_count"),
                "action_decode_note": r.get("action_decode_note"),
            }
        )

    summary = {
        "schema": "vibe22.cold_day_bridge.v1",
        "public_verdict": PUBLIC,
        "target_date": day,
        "lookback_dates": [lookback],
        "idf_sha256": idf_sha,
        "epw_sha256": epw_sha,
        "epw_path": str(epw),
        "energyplus_version": "26.1.0",
        "n_process_starts_total": launches,
        "VERIFIED_BAS_INCUMBENT": "UNRESOLVED",
        "arms_table": table,
        "why_peaks_differ": {
            "utility_jan2026_billed_kw": 284.82,
            "a04_native_jan26_kw": native_peak,
            "observed_bas_v2_jan26_kw": bas_peak,
            "note": (
                "285-class peaks are Jan utility / A04 native calibration weather+schedule. "
                "December RL/grid ~200–234 kW peaks used different dates and observed_bas_v2."
            ),
        },
        "bacnet_commands": 0,
        "SIMULATION_TRAINING_READY": False,
        "RESEARCH_POLICY_SCREENING_READY": True,
        "OPERATIONAL_DSM_READY": False,
        "BACNET_COMMAND_AUTHORITY": 0,
    }
    (out_root / "bridge_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _plots(out_root, results, table, native_peak, bas_peak)
    print(json.dumps({"out": str(out_root), "launches": launches, "table": table}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
