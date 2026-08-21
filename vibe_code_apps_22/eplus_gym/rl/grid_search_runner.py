"""LIVE EnergyPlus fixed-policy discrete grid-search runner (no RL training)."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.control_v2 import observed_bas_incumbent_params
from eplus_gym.rl.campaign_bundle import forecasts_from_epw
from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant
from eplus_gym.rl.day_ahead_tariff import rate_vector_from_mode_or_fixture
from eplus_gym.rl.grid_search_menu import (
    build_candidate_menu,
    checked_school_days,
    select_indices_for_screen,
    validation_days,
)
from eplus_gym.rl.grid_search_select import aggregate_candidate, select_grid_validation_leader
from eplus_gym.rl.multiday_env import schedule_fingerprint, trajectory_hash
from eplus_gym.rl.research_model import verify_research_model
from eplus_gym.rl.research_poc import refuse_fake_plant, reject_candidate_as_baseline
from eplus_gym.rl.research_spaces import (
    decode_discrete_research_v3,
    research_build_six_schedules_f,
    research_continuous_70,
)
from eplus_gym.rl.reward_v2 import IntegrityFailure, score_day_v2
from eplus_gym.site_pins import resolve_site_epw, sha256_file

HONESTY = [
    "SIMULATION-ONLY RL RESEARCH",
    "NOT VALIDATED FOR OPERATIONAL DSM",
    "NO PRISTINE LOCKED TEST",
    "A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION",
    "TOU TARIFF IS ILLUSTRATIVE",
    "CURRENT CAMPAIGNS USED OBSERVED_BAS_INCUMBENT_V2",
    "NO BACNET COMMAND AUTHORITY",
]

DEC_FLOOR_DISCLOSURE = (
    "Validation demand-cost accounting initialized the December billing floor at "
    "zero and may overstate incremental candidate demand charges."
)


def load_experiment_contract(app_root: Path) -> dict[str, Any]:
    path = Path(app_root) / "contracts" / "grid_search_experiment_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_paths(app_root: Path, site_root: Path) -> dict[str, Any]:
    manifest = verify_research_model(app_root)
    idf = Path(app_root) / str(manifest.get("idf_path") or f"models/eplus/{A04_IDF_NAME}")
    epw = resolve_site_epw(Path(site_root))
    return {
        "idf": idf,
        "epw": epw,
        "idf_sha256": sha256_file(idf),
        "epw_sha256": sha256_file(epw),
        "manifest": manifest,
    }


def _compact_traj(payload: dict[str, Any]) -> dict[str, Any]:
    zones = payload["zone_temps_series_f"]
    fac = [float(x) for x in payload["facility_kw"]]
    zc = {k: [float(x) for x in zones[k]] for k in zones}
    return {
        "facility_kw": fac,
        "zone_temps_series_f": zc,
        "peak_kw": float(payload["peak_kw"]),
        "daily_kwh": float(payload["daily_kwh"]),
        "trajectory_sha256": trajectory_hash(payload),
        "n_intervals": 96,
    }


def _score_day(
    *,
    day: str,
    cand: dict[str, Any],
    base: dict[str, Any],
    schedules: Mapping[str, Sequence[float]],
    prev_schedules: Mapping[str, Sequence[float]] | None,
    mtd: float,
    base_mtd: float,
    rate_kwh: Sequence[float],
    demand_rate: float,
) -> dict[str, Any]:
    reject_candidate_as_baseline(
        {"sha": cand["trajectory_sha256"] + "-cand"},
        {"sha": base["trajectory_sha256"]},
    )
    res = score_day_v2(
        day=day,
        candidate_facility_kw=cand["facility_kw"],
        candidate_zone_temps_f=cand["zone_temps_series_f"],
        baseline_facility_kw=base["facility_kw"],
        baseline_zone_temps_f=base["zone_temps_series_f"],
        candidate_schedules=schedules,
        previous_schedules=prev_schedules,
        mtd_peak_kw=mtd,
        baseline_mtd_peak_kw=base_mtd,
        rate_kwh=rate_kwh,
        demand_rate=demand_rate,
    )
    return {
        "day": day,
        "valid": True,
        "energy_cost": float(res.candidate["energy_cost"]),
        "incremental_demand_cost": float(res.candidate["demand_increment"]),
        "peak_kw": float(res.candidate["day_peak_kw"]),
        "daily_kwh": float(cand["daily_kwh"]),
        "readiness_ok": bool(res.readiness.get("readiness_ok")),
        "readiness_checked": bool(res.readiness.get("checked")),
        "occupied_dh": float(res.extras.get("occupied_zone_DH") or 0.0),
        "movement": float(res.extras.get("within_day_schedule_movement") or 0.0),
        "opening_mtd_kw": float(mtd),
        "new_mtd_kw": float(res.candidate.get("new_floor_kw") or max(mtd, res.candidate["day_peak_kw"])),
        "trajectory_sha256": cand["trajectory_sha256"],
        "baseline_trajectory_sha256": base["trajectory_sha256"],
    }


def run_baseline_cache(
    *,
    site: Path,
    epw: Path,
    idf: Path,
    output: Path,
    days: Sequence[str],
    oat: Mapping[str, Sequence[float]],
) -> dict[str, Any]:
    plant = EnergyPlusContinuityPlant(
        site_root=site, epw=epw, idf=idf, output=output, days=list(days), queue_timeout_s=600.0
    )
    refuse_fake_plant(plant)
    t0 = time.perf_counter()
    plant.start_episode()
    incumbent = observed_bas_incumbent_params()
    out: dict[str, Any] = {}
    for day in days:
        sched = research_build_six_schedules_f(incumbent, day)
        payload = plant.simulate_day(sched, oat_c=list(oat[day]))
        out[day] = _compact_traj(payload)
    quality = plant.finish_quality()
    return {
        "payloads": out,
        "quality": quality,
        "n_process_starts": int(plant.n_process_starts),
        "elapsed_s": time.perf_counter() - t0,
        "baseline_schedule_fingerprint": schedule_fingerprint(
            research_build_six_schedules_f(incumbent, days[0])
        ),
    }


def run_fixed_policy_episode(
    *,
    site: Path,
    epw: Path,
    idf: Path,
    output: Path,
    days: Sequence[str],
    oat: Mapping[str, Sequence[float]],
    action_index: int,
) -> dict[str, Any]:
    plant = EnergyPlusContinuityPlant(
        site_root=site, epw=epw, idf=idf, output=output, days=list(days), queue_timeout_s=600.0
    )
    refuse_fake_plant(plant)
    t0 = time.perf_counter()
    plant.start_episode()
    traj: dict[str, Any] = {}
    schedules_by_day: dict[str, Any] = {}
    try:
        for day in days:
            params = decode_discrete_research_v3(int(action_index), day=day)
            sched = research_build_six_schedules_f(params, day)
            schedules_by_day[day] = {k: list(v) for k, v in sched.items()}
            payload = plant.simulate_day(sched, oat_c=list(oat[day]))
            traj[day] = _compact_traj(payload)
        failed = False
        fail_reason = None
    except IntegrityFailure as exc:
        failed = True
        fail_reason = str(exc)
    quality = plant.finish_quality()
    return {
        "action_index": int(action_index),
        "trajectories": traj,
        "schedules_by_day": schedules_by_day,
        "quality": quality,
        "n_process_starts": int(plant.n_process_starts),
        "elapsed_s": time.perf_counter() - t0,
        "failed": failed,
        "fail_reason": fail_reason,
        "lookback_fp": schedule_fingerprint(
            research_build_six_schedules_f(research_continuous_70(), days[0])
        ),
    }


def score_episode_trajectories(
    *,
    days: Sequence[str],
    traj: Mapping[str, Mapping[str, Any]],
    baseline: Mapping[str, Mapping[str, Any]],
    schedules_by_day: Mapping[str, Mapping[str, Sequence[float]]],
    tariff_mode: str,
    fixtures_dir: Path | None = None,
) -> list[dict[str, Any]]:
    rates, demand, _label = rate_vector_from_mode_or_fixture(tariff_mode, fixtures_dir=fixtures_dir)
    mtd = 0.0
    base_mtd = 0.0
    prev = None
    rows: list[dict[str, Any]] = []
    for day in days:
        if day not in traj or day not in baseline:
            raise IntegrityFailure(f"missing trajectory for {day}")
        row = _score_day(
            day=day,
            cand=traj[day],
            base=baseline[day],
            schedules=schedules_by_day[day],
            prev_schedules=prev,
            mtd=mtd,
            base_mtd=base_mtd,
            rate_kwh=list(rates),
            demand_rate=float(demand),
        )
        mtd = float(row["new_mtd_kw"])
        base_mtd = max(base_mtd, float(baseline[day]["peak_kw"]))
        prev = schedules_by_day[day]
        rows.append(row)
    return rows


def run_micro_gate(*, app_root: Path, site_root: Path, out_root: Path | None = None) -> dict[str, Any]:
    contract = load_experiment_contract(app_root)
    paths = resolve_paths(app_root, site_root)
    day = checked_school_days()[0]
    days = [day]
    oat = forecasts_from_epw(paths["epw"], days)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(out_root) if out_root else Path(site_root) / "reports" / "eplus_gym" / "rl" / f"grid_search_micro_{stamp}"
    root.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    base = run_baseline_cache(
        site=Path(site_root),
        epw=paths["epw"],
        idf=paths["idf"],
        output=root / "baseline",
        days=days,
        oat=oat,
    )
    launches = int(base["n_process_starts"])
    arms = {
        "incumbent": None,  # special: use baseline traj as candidate for arm record
        "continuous_68": 0,
        "setback_recovery": 2,
    }
    results: dict[str, Any] = {}
    fps: dict[str, str] = {}
    # incumbent arm: re-simulate as candidate with separate outdir
    for name, idx in arms.items():
        if name == "incumbent":
            plant_out = root / "arm_incumbent"
            # Fixed incumbent schedules via decode of continuous? Use observed params through index path:
            # simulate using observed_bas schedules directly
            plant = EnergyPlusContinuityPlant(
                site_root=Path(site_root),
                epw=paths["epw"],
                idf=paths["idf"],
                output=plant_out,
                days=days,
                queue_timeout_s=600.0,
            )
            refuse_fake_plant(plant)
            plant.start_episode()
            sched = research_build_six_schedules_f(observed_bas_incumbent_params(), day)
            payload = plant.simulate_day(sched, oat_c=list(oat[day]))
            quality = plant.finish_quality()
            launches += int(plant.n_process_starts)
            traj = {day: _compact_traj(payload)}
            schedules = {day: {k: list(v) for k, v in sched.items()}}
            fps[name] = schedule_fingerprint(sched)
            ep = {
                "action_index": "incumbent",
                "trajectories": traj,
                "schedules_by_day": schedules,
                "quality": quality,
                "failed": False,
                "n_process_starts": plant.n_process_starts,
            }
        else:
            ep = run_fixed_policy_episode(
                site=Path(site_root),
                epw=paths["epw"],
                idf=paths["idf"],
                output=root / f"arm_{name}",
                days=days,
                oat=oat,
                action_index=int(idx),
            )
            launches += int(ep["n_process_starts"])
            fps[name] = schedule_fingerprint(
                research_build_six_schedules_f(decode_discrete_research_v3(int(idx), day=day), day)
            )
        if ep.get("failed"):
            audit = {
                "status": "MICRO_GATE_FAILED",
                "reason": ep.get("fail_reason"),
                "honesty_labels": HONESTY,
                "run_root": str(root),
            }
            (root / "micro_gate_failure.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
            return audit
        rows = score_episode_trajectories(
            days=days,
            traj=ep["trajectories"],
            baseline=base["payloads"],
            schedules_by_day=ep["schedules_by_day"],
            tariff_mode="FLAT_PLUS_DEMAND",
            fixtures_dir=Path(app_root) / "contracts" / "fixtures" / "tariffs",
        )
        severe = int((ep.get("quality") or {}).get("severe_count") or 0)
        fatal = int((ep.get("quality") or {}).get("fatal_count") or 0)
        results[name] = {
            "rows": rows,
            "severe": severe,
            "fatal": fatal,
            "fingerprint": fps[name],
            "n_process_starts": ep["n_process_starts"],
        }

    ok = (
        len(results) == 3
        and all(r["rows"] and r["rows"][0]["valid"] for r in results.values())
        and all(r["severe"] == 0 and r["fatal"] == 0 for r in results.values())
        and len(set(fps.values())) >= 2
    )
    body = {
        "status": "MICRO_GATE_PASSED" if ok else "MICRO_GATE_FAILED",
        "day": day,
        "honesty_labels": HONESTY,
        "idf_sha256": paths["idf_sha256"],
        "epw_sha256": paths["epw_sha256"],
        "n_process_starts": launches,
        "elapsed_s": time.perf_counter() - t0,
        "schedule_fingerprints": fps,
        "baseline_provenance": {
            "baseline_schedule_fingerprint": base["baseline_schedule_fingerprint"],
            "paired_baseline": "observed_bas_incumbent_v2",
        },
        "december_billing_floor_disclosure": DEC_FLOOR_DISCLOSURE,
        "arms": {k: {kk: vv for kk, vv in v.items() if kk != "rows"} | {"row0": v["rows"][0]} for k, v in results.items()},
        "contract_version": contract.get("version"),
        "run_root": str(root),
        "bacnet_commands": 0,
        "DAILY_ADAPTIVE_GRID_STATUS": contract.get("daily_adaptive_grid_status"),
    }
    (root / "micro_gate.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
    if not ok:
        (root / "micro_gate_failure.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
    return body


def run_pilot(*, app_root: Path, site_root: Path, out_root: Path | None = None) -> dict[str, Any]:
    contract = load_experiment_contract(app_root)
    paths = resolve_paths(app_root, site_root)
    days = checked_school_days()
    oat = forecasts_from_epw(paths["epw"], days)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(out_root) if out_root else Path(site_root) / "reports" / "eplus_gym" / "rl" / f"grid_search_pilot_{stamp}"
    root.mkdir(parents=True, exist_ok=True)
    menu = build_candidate_menu(days=days)
    (root / "candidate_menu.json").write_text(json.dumps(menu, indent=2), encoding="utf-8")
    indices = [int(i) for i in contract["pilot_diversity_indices"]]
    groups = select_indices_for_screen(menu, indices=indices)
    t0 = time.perf_counter()
    base = run_baseline_cache(
        site=Path(site_root),
        epw=paths["epw"],
        idf=paths["idf"],
        output=root / "baseline",
        days=days,
        oat=oat,
    )
    launches = int(base["n_process_starts"])
    fixtures = Path(app_root) / "contracts" / "fixtures" / "tariffs"
    candidates_out: list[dict[str, Any]] = []
    traj_store: dict[str, Any] = {}
    for g in groups:
        idx = int(g["representative_index"])
        ep = run_fixed_policy_episode(
            site=Path(site_root),
            epw=paths["epw"],
            idf=paths["idf"],
            output=root / f"policy_{idx}",
            days=days,
            oat=oat,
            action_index=idx,
        )
        launches += int(ep["n_process_starts"])
        if ep.get("failed"):
            return {
                "status": "PILOT_FAILED",
                "reason": ep.get("fail_reason"),
                "run_root": str(root),
                "honesty_labels": HONESTY,
            }
        traj_store[str(idx)] = {
            "trajectories": ep["trajectories"],
            "schedules_by_day": ep["schedules_by_day"],
            "quality": ep["quality"],
        }
        for tariff in ("FLAT_PLUS_DEMAND", "ILLUSTRATIVE_TOU_PLUS_DEMAND"):
            rows = score_episode_trajectories(
                days=days,
                traj=ep["trajectories"],
                baseline=base["payloads"],
                schedules_by_day=ep["schedules_by_day"],
                tariff_mode=tariff,
                fixtures_dir=fixtures,
            )
            severe = int((ep.get("quality") or {}).get("severe_count") or 0)
            fatal = int((ep.get("quality") or {}).get("fatal_count") or 0)
            agg = aggregate_candidate(
                candidate_id=f"discrete_{idx}",
                action_index=idx,
                day_rows=rows,
                checked_school_days=days,
                severe=severe,
                fatal=fatal,
            )
            agg["tariff_mode"] = tariff
            candidates_out.append(agg)

    elapsed = time.perf_counter() - t0
    n_unique_full = int(build_candidate_menu(days=validation_days())["n_unique_fixed_policies"])
    # Estimate: pilot ran len(groups) policies over 5 days; scale to n_unique_full × 17
    per_policy_s = elapsed / max(1, len(groups))
    projected_full_s = per_policy_s * (17.0 / 5.0) * float(n_unique_full)
    wall_cap_s = float(contract["wall_time_limit_hours"]) * 3600.0
    proceed_exhaustive = projected_full_s <= wall_cap_s
    body = {
        "status": "PILOT_PASSED",
        "honesty_labels": HONESTY,
        "run_root": str(root),
        "days": days,
        "n_policies": len(groups),
        "candidate_days": len(groups) * len(days),
        "n_process_starts": launches,
        "elapsed_s": elapsed,
        "declared_action_count": menu["declared_action_count"],
        "n_unique_schedules_school_day0": menu["unique_by_day"][days[0]],
        "n_unique_fixed_policies_full_validation": n_unique_full,
        "projected_exhaustive_wall_s": projected_full_s,
        "wall_time_limit_s": wall_cap_s,
        "proceed_exhaustive": proceed_exhaustive,
        "screen_recommendation": (
            "EXHAUSTIVE_FIXED_POLICY" if proceed_exhaustive else "BOUNDED_GRID_SCREEN_NOT_EXHAUSTIVE"
        ),
        "bacnet_commands": 0,
        "candidates": [{k: v for k, v in c.items() if k != "day_rows"} for c in candidates_out],
        "idf_sha256": paths["idf_sha256"],
        "epw_sha256": paths["epw_sha256"],
        "december_billing_floor_disclosure": DEC_FLOOR_DISCLOSURE,
        "DAILY_ADAPTIVE_GRID_STATUS": contract.get("daily_adaptive_grid_status"),
    }
    (root / "pilot.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
    (root / "trajectories_compact.json").write_text(
        json.dumps({"baseline": base["payloads"], "policies": traj_store}, indent=2),
        encoding="utf-8",
    )
    return body


def run_fixed_policy_screen(
    *,
    app_root: Path,
    site_root: Path,
    out_root: Path | None = None,
    force_bounded: bool | None = None,
    pilot_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = load_experiment_contract(app_root)
    paths = resolve_paths(app_root, site_root)
    days = validation_days()
    oat = forecasts_from_epw(paths["epw"], days)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(out_root) if out_root else Path(site_root) / "reports" / "eplus_gym" / "rl" / f"grid_search_screen_{stamp}"
    root.mkdir(parents=True, exist_ok=True)
    menu = build_candidate_menu(days=days)
    (root / "candidate_menu.json").write_text(json.dumps(menu, indent=2), encoding="utf-8")

    use_bounded = bool(force_bounded)
    if force_bounded is None:
        if pilot_result is not None:
            use_bounded = not bool(pilot_result.get("proceed_exhaustive"))
        else:
            use_bounded = True  # fail closed without pilot estimate

    if use_bounded:
        indices = [int(i) for i in contract["preregistered_bounded_subset_indices"]]
        screen_label = "BOUNDED_GRID_SCREEN_NOT_EXHAUSTIVE"
    else:
        indices = None
        screen_label = "EXHAUSTIVE_FIXED_POLICY"

    groups = select_indices_for_screen(menu, indices=indices)
    t0 = time.perf_counter()
    base = run_baseline_cache(
        site=Path(site_root),
        epw=paths["epw"],
        idf=paths["idf"],
        output=root / "baseline",
        days=days,
        oat=oat,
    )
    launches = int(base["n_process_starts"])
    fixtures = Path(app_root) / "contracts" / "fixtures" / "tariffs"
    traj_store: dict[str, Any] = {"baseline": base["payloads"], "policies": {}}
    scored: dict[str, list[dict[str, Any]]] = {
        "FLAT_PLUS_DEMAND": [],
        "ILLUSTRATIVE_TOU_PLUS_DEMAND": [],
        "ILLUSTRATIVE_DYNAMIC_HOURLY": [],
    }
    failed_traj = 0
    valid_traj = 0

    for g in groups:
        idx = int(g["representative_index"])
        ep = run_fixed_policy_episode(
            site=Path(site_root),
            epw=paths["epw"],
            idf=paths["idf"],
            output=root / f"policy_{idx}",
            days=days,
            oat=oat,
            action_index=idx,
        )
        launches += int(ep["n_process_starts"])
        if ep.get("failed"):
            failed_traj += 1
            continue
        valid_traj += len(days)
        traj_store["policies"][str(idx)] = {
            "trajectories": ep["trajectories"],
            "schedules_by_day": ep["schedules_by_day"],
            "quality": ep["quality"],
            "action_indices": g["action_indices"],
            "sequence_fingerprint": g["sequence_fingerprint"],
        }
        severe = int((ep.get("quality") or {}).get("severe_count") or 0)
        fatal = int((ep.get("quality") or {}).get("fatal_count") or 0)
        for tariff in scored:
            rows = score_episode_trajectories(
                days=days,
                traj=ep["trajectories"],
                baseline=base["payloads"],
                schedules_by_day=ep["schedules_by_day"],
                tariff_mode=tariff,
                fixtures_dir=fixtures,
            )
            agg = aggregate_candidate(
                candidate_id=f"discrete_{idx}",
                action_index=idx,
                day_rows=rows,
                checked_school_days=checked_school_days(),
                severe=severe,
                fatal=fatal,
            )
            agg["tariff_mode"] = tariff
            scored[tariff].append(agg)

    elapsed = time.perf_counter() - t0
    leaders = {}
    for tariff, cands in scored.items():
        leaders[tariff] = select_grid_validation_leader(cands)

    body = {
        "status": screen_label,
        "honesty_labels": HONESTY,
        "run_root": str(root),
        "days": days,
        "n_policies_simulated": len(groups),
        "declared_action_count": menu["declared_action_count"],
        "n_unique_fixed_policies": menu["n_unique_fixed_policies"],
        "candidate_menu_sha256": menu["candidate_menu_sha256"],
        "candidate_days": len(groups) * len(days),
        "n_process_starts": launches,
        "valid_trajectory_days": valid_traj,
        "failed_policies": failed_traj,
        "elapsed_s": elapsed,
        "leaders": {
            t: {k: v for k, v in L.items() if k != "leader"} for t, L in leaders.items()
        },
        "bacnet_commands": 0,
        "idf_sha256": paths["idf_sha256"],
        "epw_sha256": paths["epw_sha256"],
        "december_billing_floor_disclosure": DEC_FLOOR_DISCLOSURE,
        "DAILY_ADAPTIVE_GRID_STATUS": contract.get("daily_adaptive_grid_status"),
        "indices": [int(g["representative_index"]) for g in groups],
    }
    (root / "screen.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
    # Compact scorecard without full day rows
    scorecard = []
    for tariff, cands in scored.items():
        for c in cands:
            scorecard.append({k: v for k, v in c.items() if k != "day_rows"})
    (root / "scorecard.json").write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    (root / "trajectories_compact.json").write_text(json.dumps(traj_store), encoding="utf-8")
    body["scorecard"] = scorecard
    body["leaders_full"] = leaders
    return body
