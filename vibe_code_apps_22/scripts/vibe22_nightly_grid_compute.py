"""Nightly identical-state A04 grid-search compute benchmark CLI."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _worker(payload: dict[str, Any]) -> dict[str, Any]:
    from eplus_gym.control_v2 import observed_bas_incumbent_params
    from eplus_gym.rl.nightly_grid_branch import run_baseline_incumbent, run_identical_state_candidate
    from eplus_gym.rl.nightly_grid_menu import schedule_for_index
    from eplus_gym.rl.research_spaces import decode_discrete_research_v3, research_build_six_schedules_f
    from eplus_gym.site_env import require_site_root

    site = require_site_root(Path(payload["site_root"]) if payload.get("site_root") else None)
    app_root = Path(payload.get("app_root") or _APP)
    out_dir = Path(payload["out_dir"])
    day = str(payload["day"])
    lookback_day = str(payload["lookback_day"])
    mode = str(payload.get("tariff_mode") or "FLAT_PLUS_DEMAND")
    mtd = float(payload.get("opening_mtd_kw") or 0.0)

    if payload.get("role") == "baseline":
        return run_baseline_incumbent(
            site=site,
            app_root=app_root,
            out_dir=out_dir,
            day=day,
            lookback_day=lookback_day,
            opening_mtd_kw=mtd,
            tariff_mode=mode,
        )

    baseline = payload["baseline"]
    cid = str(payload["candidate_id"])
    if payload.get("kind") == "params_json":
        # Reconstruct from discrete index preferred
        idx = int(payload["action_index"])
        sched = schedule_for_index(idx, day)
    else:
        idx = int(payload["action_index"])
        sched = schedule_for_index(idx, day)
    return run_identical_state_candidate(
        site=site,
        app_root=app_root,
        out_dir=out_dir,
        day=day,
        lookback_day=lookback_day,
        candidate_id=cid,
        target_schedules=sched,
        baseline_payload=baseline,
        lookback_params=observed_bas_incumbent_params(),
        opening_mtd_kw=mtd,
        tariff_mode=mode,
    )


def _run_sub(payload: dict[str, Any], *, run_dir: Path) -> dict[str, Any]:
    from eplus_gym.rl.nightly_grid_instrument import instrument_subprocess

    tmp = run_dir / f"_worker_{payload.get('candidate_id') or payload.get('role')}.json"
    res_path = run_dir / f"_result_{payload.get('candidate_id') or payload.get('role')}.json"
    _save_json(tmp, payload)
    cmd = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "--worker-json",
        str(tmp),
        "--result-json",
        str(res_path),
    ]
    code, out, err, metrics = instrument_subprocess(cmd, cwd=str(_APP))
    if code != 0 or not res_path.is_file():
        return {
            "status": "FAILED",
            "exit_code": code,
            "stdout": (out or "")[-2000:],
            "stderr": (err or "")[-2000:],
            "wall_s": metrics.wall_s,
            "child_user_cpu_s": metrics.child_user_cpu_s,
            "child_system_cpu_s": metrics.child_system_cpu_s,
            "peak_rss_bytes": metrics.peak_rss_bytes,
            "pid": metrics.pid,
            "utc_start": metrics.utc_start,
            "utc_end": metrics.utc_end,
        }
    result = _load_json(res_path)
    result["wall_s"] = metrics.wall_s
    result["child_user_cpu_s"] = metrics.child_user_cpu_s
    result["child_system_cpu_s"] = metrics.child_system_cpu_s
    result["peak_rss_bytes"] = metrics.peak_rss_bytes
    result["pid"] = metrics.pid
    result["utc_start"] = metrics.utc_start
    result["utc_end"] = metrics.utc_end
    result["exit_code"] = code
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site-root", type=Path, default=None)
    p.add_argument("--site-run-dir", type=Path, default=None)
    p.add_argument("--stage", default="all", choices=["freeze", "micro", "pilot", "budgets", "publish", "all"])
    p.add_argument("--resume", action="store_true")
    p.add_argument("--worker-json", type=Path, default=None)
    p.add_argument("--result-json", type=Path, default=None)
    args = p.parse_args()

    if args.worker_json is not None:
        payload = _load_json(Path(args.worker_json))
        result = _worker(payload)
        out = Path(args.result_json) if args.result_json else Path(args.worker_json).with_name("_result.json")
        _save_json(out, result)
        return 0

    from eplus_gym.rl.day_ahead_tariff import rate_vector_from_mode_or_fixture
    from eplus_gym.rl.nightly_grid_branch import IdenticalStateFailure, prove_identical_midnight
    from eplus_gym.rl.nightly_grid_cost import score_candidate_day
    from eplus_gym.rl.nightly_grid_freeze import build_environment_manifest, build_provenance
    from eplus_gym.rl.nightly_grid_menu import (
        build_one_day_menu,
        load_nightly_contract,
        preregistered_anytime_order,
        schedule_for_index,
    )
    from eplus_gym.rl.nightly_grid_parallel import run_worker_sweep
    from eplus_gym.rl.nightly_grid_publish import publish_pack
    from eplus_gym.rl.nightly_grid_rl_compare import benchmark_inference, import_recorded_rl_facts
    from eplus_gym.rl.two_month_provenance import DQN_ZIP_REL, PPO_ZIP_REL
    from eplus_gym.site_env import require_site_root

    site = require_site_root(args.site_root)
    contract = load_nightly_contract(_APP)
    day = str(contract["primary_benchmark_day"])
    lookback_day = str(contract["lookback_day"])
    run_dir = args.site_run_dir or (site / "reports/eplus_gym/rl" / f"nightly_grid_compute_{_utc()}")
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "stage_state.json"
    state = _load_json(state_path) if args.resume else {}

    def persist() -> None:
        _save_json(state_path, state)

    # --- freeze ---
    if args.stage in ("freeze", "all"):
        print("stage: freeze", flush=True)
        env = build_environment_manifest(app_root=_APP, site=site)
        prov = build_provenance(app_root=_APP, site=site, env=env)
        _save_json(run_dir / "environment_manifest.json", env)
        _save_json(run_dir / "provenance.json", prov)
        state["env"] = env
        state["provenance"] = prov
        persist()

    env = state.get("env") or build_environment_manifest(app_root=_APP, site=site)
    prov = state.get("provenance") or build_provenance(app_root=_APP, site=site, env=env)
    menu = build_one_day_menu(day=day)
    order = preregistered_anytime_order(
        menu, seed_indices=list(contract.get("preregistered_anytime_seed_indices") or [])
    )
    _save_json(run_dir / "menu.json", {"n_unique": menu["n_unique_one_day"], "order": order})

    tariff = str(contract.get("primary_tariff_for_selection") or "FLAT_PLUS_DEMAND")
    mtd = float(contract.get("opening_mtd_kw") or 0.0)

    # Baseline once
    if "baseline" not in state:
        print("stage: baseline", flush=True)
        base = _run_sub(
            {
                "role": "baseline",
                "site_root": str(site),
                "app_root": str(_APP),
                "out_dir": str(run_dir / "baseline"),
                "day": day,
                "lookback_day": lookback_day,
                "tariff_mode": tariff,
                "opening_mtd_kw": mtd,
            },
            run_dir=run_dir,
        )
        if base.get("status") == "FAILED":
            print(json.dumps(base, indent=2), file=sys.stderr)
            return 1
        state["baseline"] = base
        state["eplus_launches"] = int(state.get("eplus_launches") or 0) + 1
        persist()
    baseline = state["baseline"]

    def eval_index(idx: int, *, tag: str) -> dict[str, Any]:
        cid = f"discrete_{idx}"
        cache = (state.get("results") or {}).get(cid)
        if args.resume and cache and cache.get("status") == "OK":
            print(f"resume skip {cid}", flush=True)
            return cache
        print(f"candidate: {cid} ({tag})", flush=True)
        r = _run_sub(
            {
                "site_root": str(site),
                "app_root": str(_APP),
                "out_dir": str(run_dir / "candidates" / cid),
                "day": day,
                "lookback_day": lookback_day,
                "candidate_id": cid,
                "action_index": int(idx),
                "kind": "params_json",
                "baseline": {
                    "facility_kw": baseline["facility_kw"],
                    "zone_temps_series_f": baseline["zone_temps_series_f"],
                },
                "tariff_mode": tariff,
                "opening_mtd_kw": mtd,
            },
            run_dir=run_dir,
        )
        r["action_index"] = int(idx)
        r["short_label"] = cid
        r["rank_eligible"] = True
        state.setdefault("results", {})[cid] = r
        state["eplus_launches"] = int(state.get("eplus_launches") or 0) + 1
        persist()
        return r

    # --- micro ---
    if args.stage in ("micro", "all"):
        print("stage: micro", flush=True)
        micro_idx = [int(i) for i in contract.get("micro_gate_indices") or [0, 1, 42]]
        micro_rows = [eval_index(i, tag="micro") for i in micro_idx]
        midnights = [r.get("midnight_zone_temps_f") for r in micro_rows if r.get("midnight_zone_temps_f")]
        try:
            proof = prove_identical_midnight(
                midnights, tol_f=float(contract.get("identical_state_temp_tol_f") or 0.05)
            )
            # also include baseline midnight
            if baseline.get("midnight_zone_temps_f"):
                prove_identical_midnight(
                    [baseline["midnight_zone_temps_f"], *midnights],
                    tol_f=float(contract.get("identical_state_temp_tol_f") or 0.05),
                )
        except IdenticalStateFailure as exc:
            proof = {"ok": False, "error": str(exc)}
            state["identical_state_proof"] = proof
            persist()
            print(f"BENCHMARK_INVALID: {exc}", file=sys.stderr)
            if args.stage == "micro":
                return 1
        else:
            state["identical_state_proof"] = proof
            persist()
        state["micro_done"] = True
        persist()

    # --- pilot timing (3 repeats on 10 candidates, then parallel sweep on cold results) ---
    if args.stage in ("pilot", "all"):
        print("stage: pilot", flush=True)
        pilot_idx = [int(i) for i in contract.get("pilot_diversity_indices") or order[:10]]
        # Map to unique order reps
        pilot_order = []
        for i in pilot_idx:
            if i in order and i not in pilot_order:
                pilot_order.append(i)
            elif i not in pilot_order:
                pilot_order.append(i)
        pilot_order = pilot_order[:10]
        repeats = []
        for rep in range(3):
            cache_mode = "cold" if rep == 0 else "warm"
            print(f"pilot repeat {rep} ({cache_mode})", flush=True)
            rows = []
            t0 = time.perf_counter()
            for i in pilot_order:
                # Always re-run for timing measurement (do not use resume cache)
                cid = f"discrete_{i}"
                print(f"candidate: {cid} (pilot{rep})", flush=True)
                r = _run_sub(
                    {
                        "site_root": str(site),
                        "app_root": str(_APP),
                        "out_dir": str(run_dir / "pilot" / f"rep{rep}" / cid),
                        "day": day,
                        "lookback_day": lookback_day,
                        "candidate_id": cid,
                        "action_index": int(i),
                        "kind": "params_json",
                        "baseline": {
                            "facility_kw": baseline["facility_kw"],
                            "zone_temps_series_f": baseline["zone_temps_series_f"],
                        },
                        "tariff_mode": tariff,
                        "opening_mtd_kw": mtd,
                    },
                    run_dir=run_dir,
                )
                r["action_index"] = int(i)
                r["short_label"] = cid
                r["rank_eligible"] = True
                if rep == 0 and r.get("status") == "OK":
                    state.setdefault("results", {})[cid] = r
                state["eplus_launches"] = int(state.get("eplus_launches") or 0) + 1
                rows.append(r)
            persist()
            repeats.append(
                {
                    "repeat": rep,
                    "cache_mode": cache_mode,
                    "wall_s": time.perf_counter() - t0,
                    "mean_candidate_s": sum(float(x.get("wall_s") or 0) for x in rows) / max(len(rows), 1),
                    "n": len(rows),
                }
            )
        mean_cand = float(sum(r["mean_candidate_s"] for r in repeats) / len(repeats))
        n_unique = int(menu["n_unique_one_day"])
        projected = mean_cand * n_unique
        state["pilot"] = {
            "repeats": repeats,
            "mean_candidate_wall_s": mean_cand,
            "projected_exhaustive_wall_s": projected,
            "proceed_exhaustive": projected < float(contract.get("deadline_hard_s") or 1800),
            "n_unique": n_unique,
        }
        # Parallel sweep: use already-simulated result fetch as light proxy is wrong —
        # measure wall of sequential vs parallel *subprocess launches* on 10 indices.
        def _parallel_task(task: dict[str, Any]) -> dict[str, Any]:
            # Re-run candidate for parallel timing (tagged)
            idx = int(task["action_index"])
            return _run_sub(
                {
                    "site_root": str(site),
                    "app_root": str(_APP),
                    "out_dir": str(run_dir / "parallel" / f"w{task['workers']}" / f"discrete_{idx}"),
                    "day": day,
                    "lookback_day": lookback_day,
                    "candidate_id": f"discrete_{idx}",
                    "action_index": idx,
                    "kind": "params_json",
                    "baseline": {
                        "facility_kw": baseline["facility_kw"],
                        "zone_temps_series_f": baseline["zone_temps_series_f"],
                    },
                    "tariff_mode": tariff,
                    "opening_mtd_kw": mtd,
                },
                run_dir=run_dir,
            )

        # Sequential timing for p=1 already in pilot; for parallel use ProcessPool on tasks
        # Simpler: record 1-worker pilot wall as T1; run 2 and optionally 4.
        peak_rss = max((int(state["results"][f"discrete_{i}"].get("peak_rss_bytes") or 0) for i in pilot_order), default=0)
        t1 = float(repeats[0]["wall_s"])
        parallel = {"runs": {"1": {"wall_s": t1, "n_tasks": 10, "skipped": False, "speedup": 1.0, "parallel_efficiency": 1.0}}}
        for workers in (2, 4):
            ram = env.get("installed_ram_bytes")
            if workers == 4 and ram and peak_rss and workers * peak_rss > float(contract.get("worker_memory_fraction_cap") or 0.7) * ram:
                parallel["runs"]["4"] = {"skipped": True, "reason": "projected peak RSS exceeds memory fraction cap"}
                continue
            tasks = [{"action_index": i, "workers": workers} for i in pilot_order]
            t0 = time.perf_counter()
            from concurrent.futures import ThreadPoolExecutor, as_completed

            # Thread pool launching subprocesses (E+ isolation); ProcessPool would pickle too much.
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(_parallel_task, t) for t in tasks]
                for f in as_completed(futs):
                    _ = f.result()
                    state["eplus_launches"] = int(state.get("eplus_launches") or 0) + 1
            tp = time.perf_counter() - t0
            parallel["runs"][str(workers)] = {
                "wall_s": tp,
                "n_tasks": 10,
                "skipped": False,
                "speedup": t1 / tp if tp else 0.0,
                "parallel_efficiency": t1 / (workers * tp) if tp else 0.0,
            }
            persist()
        parallel["recommended_workers"] = min(
            (
                int(k)
                for k, v in parallel["runs"].items()
                if not v.get("skipped")
            ),
            key=lambda k: float(parallel["runs"][str(k)]["wall_s"]),
            default=1,
        )
        parallel["scientific_reference_workers"] = 1
        state["parallel"] = parallel
        persist()

    # --- budgets / exhaustive ---
    if args.stage in ("budgets", "all"):
        print("stage: budgets", flush=True)
        projected = float((state.get("pilot") or {}).get("projected_exhaustive_wall_s") or 0)
        proceed = bool((state.get("pilot") or {}).get("proceed_exhaustive", projected < 1800))
        markers = [int(x) for x in contract.get("budget_markers") or [10, 25, 50, 100]]
        limit = len(order) if proceed else max(markers)
        if not proceed:
            limit = min(limit, max(markers))
            print(f"bounded screen: projected {projected:.1f}s >= hard deadline; limit={limit}", flush=True)
        ordered_results = []
        for n, idx in enumerate(order[:limit], start=1):
            r = eval_index(idx, tag="budget")
            ordered_results.append(r)
            if n in markers:
                state.setdefault("budget_snapshots", {})[str(n)] = {
                    "n": n,
                    "best": min(
                        (
                            float(x["score"]["total_modeled_objective"])
                            for x in ordered_results
                            if x.get("status") == "OK" and x.get("score", {}).get("fully_ready_eligible")
                        ),
                        default=None,
                    ),
                }
                persist()
        state["ordered_results_ids"] = [r.get("candidate_id") for r in ordered_results]
        state["budget_limit"] = limit
        persist()

        # Winner determinism ×3
        ready = [
            r
            for r in ordered_results
            if r.get("status") == "OK" and r.get("score", {}).get("fully_ready_eligible")
        ]
        winner = min(ready, key=lambda r: float(r["score"]["total_modeled_objective"])) if ready else None
        det = {"winner": None, "runs": [], "ok": False}
        if winner is not None:
            widx = int(winner["action_index"])
            hashes = []
            for i in range(3):
                rr = _run_sub(
                    {
                        "site_root": str(site),
                        "app_root": str(_APP),
                        "out_dir": str(run_dir / "determinism" / f"run{i}"),
                        "day": day,
                        "lookback_day": lookback_day,
                        "candidate_id": f"discrete_{widx}",
                        "action_index": widx,
                        "kind": "params_json",
                        "baseline": {
                            "facility_kw": baseline["facility_kw"],
                            "zone_temps_series_f": baseline["zone_temps_series_f"],
                        },
                        "tariff_mode": tariff,
                        "opening_mtd_kw": mtd,
                    },
                    run_dir=run_dir,
                )
                state["eplus_launches"] = int(state.get("eplus_launches") or 0) + 1
                hashes.append(rr.get("trajectory_sha256"))
                det["runs"].append(
                    {
                        "trajectory_sha256": rr.get("trajectory_sha256"),
                        "total_modeled_objective": (rr.get("score") or {}).get("total_modeled_objective"),
                        "peak_kw": (rr.get("score") or {}).get("peak_kw"),
                    }
                )
            det["winner"] = winner.get("candidate_id")
            det["ok"] = len(set(hashes)) == 1
        state["determinism"] = det
        persist()

        # Tariff re-score (zero extra E+)
        by_tariff: dict[str, Any] = {}
        for mode in contract.get("tariff_modes") or []:
            rescored = []
            for r in ordered_results:
                if r.get("status") != "OK":
                    continue
                sc = score_candidate_day(
                    day=day,
                    candidate_facility_kw=r["facility_kw"],
                    candidate_zone_temps_f=r["zone_temps_series_f"],
                    baseline_facility_kw=baseline["facility_kw"],
                    baseline_zone_temps_f=baseline["zone_temps_series_f"],
                    candidate_schedules=schedule_for_index(int(r["action_index"]), day),
                    previous_schedules=None,
                    mtd_peak_kw=mtd,
                    baseline_mtd_peak_kw=mtd,
                    tariff_mode=str(mode),
                )
                rescored.append({"candidate_id": r["candidate_id"], "score": sc})
            ready2 = [x for x in rescored if x["score"].get("fully_ready_eligible")]
            win = min(ready2, key=lambda x: float(x["score"]["total_modeled_objective"])) if ready2 else None
            by_tariff[str(mode)] = {
                "winner": None if win is None else win["candidate_id"],
                "winner_cost": None if win is None else win["score"]["total_modeled_objective"],
                "n_rescored": len(rescored),
                "additional_eplus_launches": 0,
            }
        state["tariff_rescore"] = {"by_tariff": by_tariff, "additional_eplus_launches": 0}
        persist()

    # --- publish ---
    if args.stage in ("publish", "all"):
        print("stage: publish", flush=True)
        results = state.get("results") or {}
        ids = state.get("ordered_results_ids") or []
        ordered_results = [results[i] for i in ids if i in results]
        if not ordered_results:
            # fall back to all OK results
            ordered_results = [v for v in results.values() if str(v.get("candidate_id", "")).startswith("discrete_")]
        timing_rows = []
        ledger = []
        quality_rows = []
        midnights = []
        for r in ordered_results:
            timing_rows.append(
                {
                    "candidate_id": r.get("candidate_id"),
                    "action_index": r.get("action_index"),
                    "wall_s": r.get("wall_s"),
                    "child_user_cpu_s": r.get("child_user_cpu_s"),
                    "child_system_cpu_s": r.get("child_system_cpu_s"),
                    "peak_rss_bytes": r.get("peak_rss_bytes"),
                    "pid": r.get("pid"),
                    "utc_start": r.get("utc_start"),
                    "utc_end": r.get("utc_end"),
                    "exit_code": r.get("exit_code"),
                    "status": r.get("status"),
                    "n_intervals": r.get("n_intervals"),
                }
            )
            ledger.append(r)
            q = r.get("quality") or {}
            quality_rows.append(
                {
                    "candidate_id": r.get("candidate_id"),
                    "severe_count": q.get("severe_count"),
                    "fatal_count": q.get("fatal_count"),
                    "warning_count": q.get("warning_count"),
                    "w2a_scored": (q.get("w2a_low_airflow_by_phase") or {}).get("scored_runtime"),
                    "w2a_warmup": (q.get("w2a_low_airflow_by_phase") or {}).get("warmup"),
                    "readiness_ok": (r.get("score") or {}).get("readiness_ok"),
                }
            )
            if r.get("midnight_zone_temps_f"):
                midnights.append(r["midnight_zone_temps_f"])
        proof = state.get("identical_state_proof")
        if not proof and midnights:
            try:
                proof = prove_identical_midnight(
                    midnights, tol_f=float(contract.get("identical_state_temp_tol_f") or 0.05)
                )
            except IdenticalStateFailure as exc:
                proof = {"ok": False, "error": str(exc)}
        proof = proof or {"ok": False, "error": "missing"}

        rl_facts = import_recorded_rl_facts(_APP)
        ppo_zip = site / PPO_ZIP_REL
        dqn_zip = site / DQN_ZIP_REL
        inference = {
            "ppo": benchmark_inference(zip_path=ppo_zip, algo="PPO"),
            "dqn": benchmark_inference(zip_path=dqn_zip, algo="DQN"),
        }
        _save_json(run_dir / "inference_bench.json", inference)

        # schedule means for figure 8
        import numpy as np

        def _mean_sched(idx: int) -> list[float]:
            sched = schedule_for_index(idx, day)
            arr = np.mean([np.asarray(v, dtype=float) for v in sched.values()], axis=0)
            return arr.tolist()

        baseline_sched = _mean_sched(0)  # continuous 68 as visual stand-in if needed
        # Prefer observed bas: action from params fingerprint not discrete — use discrete_0 as continuous-68 visual
        winner = None
        ready = [
            r
            for r in ordered_results
            if r.get("status") == "OK" and r.get("score", {}).get("fully_ready_eligible")
        ]
        if ready:
            winner = min(ready, key=lambda r: float(r["score"]["total_modeled_objective"]))
        winner_sched = _mean_sched(int(winner["action_index"])) if winner else None
        from eplus_gym.control_v2 import observed_bas_incumbent_params
        from eplus_gym.rl.research_spaces import research_build_six_schedules_f

        bas = research_build_six_schedules_f(observed_bas_incumbent_params(), day)
        baseline_sched = np.mean([np.asarray(v, dtype=float) for v in bas.values()], axis=0).tolist()

        pack = publish_pack(
            app_root=_APP,
            site_run_dir=run_dir,
            env=env,
            provenance=prov,
            ledger=ledger,
            timing_rows=timing_rows,
            identical_state_proof=proof,
            tariff_rescore=state.get("tariff_rescore") or {"by_tariff": {}, "additional_eplus_launches": 0},
            determinism=state.get("determinism") or {},
            parallel=state.get("parallel") or {},
            rl_facts=rl_facts,
            inference=inference,
            ordered_results=ordered_results,
            contract=contract,
            quality_rows=quality_rows,
            baseline_sched=baseline_sched,
            winner_sched=winner_sched,
            eplus_launches=int(state.get("eplus_launches") or 0),
        )
        # artifact index
        idx_path = _APP / "docs/results/artifact_index_v1.json"
        idx = _load_json(idx_path)
        items = idx.get("items") or []
        if not any(i.get("path") == "docs/results/nightly_grid_compute/" for i in items):
            items.append(
                {
                    "path": "docs/results/nightly_grid_compute/",
                    "status": "ACTIVE_COMPUTE_BENCHMARK",
                    "notes": "Identical-state nightly grid compute on 2026-01-26; not operational DSM",
                }
            )
            idx["items"] = items
            _save_json(idx_path, idx)
        print(json.dumps({"pack": str(pack), "launches": state.get("eplus_launches")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
