"""Publish docs/results/nightly_grid_compute pack + feasibility verdict."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np

from eplus_gym.rl.nightly_grid_anytime import anytime_curve, recommend_budget
from eplus_gym.rl.nightly_grid_freeze import PUBLIC_LABELS
from eplus_gym.rl.nightly_grid_instrument import aggregate_timing

SELECTION_WORDING = (
    "Grid search and RL share the same EnergyPlus trajectories, tariff accounting, "
    "and readiness criteria. RL trains on a shaped numerical reward, while grid search "
    "selects the lowest-cost fully-ready candidate."
)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _save(fig, out: Path, stem: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{stem}.png", dpi=140, bbox_inches="tight")
    fig.savefig(out / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def feasibility_verdict(
    *,
    invalid: bool,
    exhaustive_wall_s: float | None,
    target_s: float = 900.0,
    hard_s: float = 1800.0,
) -> str:
    if invalid:
        return "BENCHMARK_INVALID"
    if exhaustive_wall_s is None:
        return "NIGHTLY_GRID_NOT_FEASIBLE_ON_TEST_HARDWARE"
    if exhaustive_wall_s <= target_s:
        return "NIGHTLY_GRID_FEASIBLE_WITHIN_15_MIN"
    if exhaustive_wall_s <= hard_s:
        return "NIGHTLY_GRID_FEASIBLE_WITHIN_30_MIN"
    return "NIGHTLY_GRID_NOT_FEASIBLE_ON_TEST_HARDWARE"


def generate_figures(
    *,
    out_dir: Path,
    curve: Mapping[str, Any],
    timing_rows: Sequence[Mapping[str, Any]],
    parallel: Mapping[str, Any],
    ledger: Sequence[Mapping[str, Any]],
    rl_facts: Mapping[str, Any],
    inference: Mapping[str, Any],
    baseline_sched: Sequence[float] | None,
    winner_sched: Sequence[float] | None,
) -> list[str]:
    fig_dir = out_dir / "figures"
    written: list[str] = []
    pts = list(curve.get("points") or [])
    ns = [p["n"] for p in pts]
    costs = [p.get("best_fully_ready_cost") for p in pts]
    regrets = [p.get("regret") for p in pts]

    # 1 best cost vs n
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(ns, costs, marker="o")
    ax.set_xlabel("Candidates evaluated")
    ax.set_ylabel("Best fully-ready cost ($)")
    ax.set_title("Best feasible cost vs candidates")
    ax.grid(True, alpha=0.3)
    _save(fig, fig_dir, "fig01_best_cost_vs_n")
    written.append("fig01_best_cost_vs_n")

    # 2 best cost vs wall (cumulative)
    cum = []
    total = 0.0
    for r in timing_rows:
        total += float(r.get("wall_s") or 0)
        cum.append(total)
    ready_costs = []
    best = None
    for r in ledger:
        sc = r.get("score") or {}
        if r.get("status") == "OK" and sc.get("fully_ready_eligible"):
            c = float(sc["total_modeled_objective"])
            best = c if best is None else min(best, c)
        ready_costs.append(best)
    fig, ax = plt.subplots(figsize=(7, 4))
    if cum and ready_costs:
        ax.plot(cum[: len(ready_costs)], ready_costs, marker="o", markersize=3)
    ax.set_xlabel("Elapsed wall time (s)")
    ax.set_ylabel("Best fully-ready cost ($)")
    ax.set_title("Best feasible cost vs wall time")
    ax.grid(True, alpha=0.3)
    _save(fig, fig_dir, "fig02_best_cost_vs_wall")
    written.append("fig02_best_cost_vs_wall")

    # 3 regret
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(ns, regrets, marker="o")
    ax.set_xlabel("Candidates evaluated")
    ax.set_ylabel("Regret ($)")
    ax.set_title("Regret vs candidate budget")
    ax.grid(True, alpha=0.3)
    _save(fig, fig_dir, "fig03_regret_vs_n")
    written.append("fig03_regret_vs_n")

    # 4 latency hist
    walls = [float(r["wall_s"]) for r in timing_rows if r.get("wall_s") is not None]
    fig, ax = plt.subplots(figsize=(7, 4))
    if walls:
        ax.hist(walls, bins=min(20, max(5, len(walls) // 3)))
    ax.set_xlabel("Candidate wall time (s)")
    ax.set_ylabel("Count")
    ax.set_title("Candidate latency distribution")
    ax.grid(True, alpha=0.3)
    _save(fig, fig_dir, "fig04_latency_hist")
    written.append("fig04_latency_hist")

    # 5 wall by workers
    fig, ax = plt.subplots(figsize=(6, 4))
    labels, vals = [], []
    for k in ("1", "2", "4"):
        run = (parallel.get("runs") or {}).get(k) or {}
        if run.get("skipped"):
            continue
        labels.append(f"{k} workers")
        vals.append(float(run.get("wall_s") or 0))
    ax.bar(labels, vals)
    ax.set_ylabel("Wall time (s)")
    ax.set_title("Pilot pilot wall time by worker count")
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, fig_dir, "fig05_wall_by_workers")
    written.append("fig05_wall_by_workers")

    # 6 speedup / efficiency
    fig, ax = plt.subplots(figsize=(6, 4))
    xs, sp, ef = [], [], []
    for k in ("1", "2", "4"):
        run = (parallel.get("runs") or {}).get(k) or {}
        if run.get("skipped") or "speedup" not in run:
            continue
        xs.append(int(k))
        sp.append(float(run["speedup"]))
        ef.append(float(run["parallel_efficiency"]))
    if xs:
        ax.plot(xs, sp, marker="o", label="speedup")
        ax.plot(xs, ef, marker="s", label="efficiency")
    ax.set_xlabel("Workers")
    ax.legend()
    ax.set_title("Speedup and parallel efficiency")
    ax.grid(True, alpha=0.3)
    _save(fig, fig_dir, "fig06_speedup_efficiency")
    written.append("fig06_speedup_efficiency")

    # 7 peak vs kWh colored by cost
    fig, ax = plt.subplots(figsize=(7, 5))
    for r in ledger:
        sc = r.get("score") or {}
        if not sc:
            continue
        ax.scatter(sc.get("daily_kwh"), sc.get("peak_kw"), c=[sc.get("total_modeled_objective")], cmap="viridis", s=40)
        ax.annotate(str(r.get("short_label") or r.get("candidate_id"))[:18], (sc.get("daily_kwh"), sc.get("peak_kw")), fontsize=6)
    ax.set_xlabel("Daily kWh")
    ax.set_ylabel("Peak kW")
    ax.set_title("Peak kW vs kWh (color=modeled cost)")
    ax.grid(True, alpha=0.3)
    _save(fig, fig_dir, "fig07_peak_vs_kwh")
    written.append("fig07_peak_vs_kwh")

    # 8 winning schedule vs baseline
    fig, ax = plt.subplots(figsize=(8, 4))
    if baseline_sched is not None:
        ax.plot(baseline_sched, label="baseline mean DualSP", linewidth=1.5)
    if winner_sched is not None:
        ax.plot(winner_sched, label="winner mean DualSP", linewidth=1.5)
    ax.set_xlabel("15-min step")
    ax.set_ylabel("Heating setpoint °F")
    ax.set_title("Winning schedule vs paired baseline")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    _save(fig, fig_dir, "fig08_winner_vs_baseline")
    written.append("fig08_winner_vs_baseline")

    # 9 compute categories log axis
    fig, ax = plt.subplots(figsize=(8, 4))
    cats = ["RL train PRIMARY", "RL train SECONDARY", "Hist grid 17d", "Nightly grid", "PPO infer×1k", "DQN infer×1k"]
    vals = [
        float(rl_facts["PRIMARY"]["elapsed_s"]),
        float(rl_facts["SECONDARY"]["elapsed_s"]),
        float(rl_facts["historical_grid_screen"]["wall_clock_s"]),
        float(sum(float(r.get("wall_s") or 0) for r in timing_rows) or 1.0),
        float((inference.get("ppo") or {}).get("p50_ms") or 1) * 1000 / 1000.0,  # keep ms visible via small floor
        float((inference.get("dqn") or {}).get("p50_ms") or 1) * 1000 / 1000.0,
    ]
    # Use seconds for RL/grid; convert inference p50_ms to seconds for fair log plot
    vals[4] = max(1e-4, float((inference.get("ppo") or {}).get("p50_ms") or 0) / 1000.0)
    vals[5] = max(1e-4, float((inference.get("dqn") or {}).get("p50_ms") or 0) / 1000.0)
    ax.bar(cats, vals)
    ax.set_yscale("log")
    ax.set_ylabel("Seconds (log)")
    ax.set_title("One-time RL train vs nightly grid vs RL inference")
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=25, ha="right")
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, fig_dir, "fig09_compute_categories_log")
    written.append("fig09_compute_categories_log")
    return written


def publish_pack(
    *,
    app_root: Path,
    site_run_dir: Path,
    env: Mapping[str, Any],
    provenance: Mapping[str, Any],
    ledger: list[dict[str, Any]],
    timing_rows: list[dict[str, Any]],
    identical_state_proof: Mapping[str, Any],
    tariff_rescore: Mapping[str, Any],
    determinism: Mapping[str, Any],
    parallel: Mapping[str, Any],
    rl_facts: Mapping[str, Any],
    inference: Mapping[str, Any],
    ordered_results: list[dict[str, Any]],
    contract: Mapping[str, Any],
    quality_rows: list[dict[str, Any]],
    baseline_sched: list[float] | None = None,
    winner_sched: list[float] | None = None,
    eplus_launches: int = 0,
) -> Path:
    out = Path(app_root) / "docs" / "results" / "nightly_grid_compute"
    out.mkdir(parents=True, exist_ok=True)
    curve = anytime_curve(ordered_results, markers=tuple(contract.get("budget_markers") or [10, 25, 50, 100]))
    agg = aggregate_timing(timing_rows)
    wall_by_n: dict[int, float] = {}
    cum = 0.0
    for i, r in enumerate(timing_rows, start=1):
        cum += float(r.get("wall_s") or 0)
        if i in set(contract.get("budget_markers") or []) or i == len(timing_rows):
            wall_by_n[i] = cum
    if timing_rows:
        wall_by_n[len(timing_rows)] = cum
    budget_rec = recommend_budget(
        curve, wall_by_n=wall_by_n, hard_s=float(contract.get("deadline_hard_s") or 1800)
    )
    exhaustive_wall = wall_by_n.get(len(timing_rows))
    invalid = not bool(identical_state_proof.get("ok", True))
    verdict = feasibility_verdict(
        invalid=invalid,
        exhaustive_wall_s=exhaustive_wall,
        target_s=float(contract.get("deadline_target_s") or 900),
        hard_s=float(contract.get("deadline_hard_s") or 1800),
    )

    flat_ledger = []
    for r in ledger:
        sc = r.get("score") or {}
        flat_ledger.append(
            {
                "candidate_id": r.get("candidate_id"),
                "short_label": r.get("short_label") or r.get("candidate_id"),
                "action_index": r.get("action_index"),
                "schedule_fingerprint": r.get("schedule_fingerprint"),
                "rank_eligible": r.get("rank_eligible", True),
                "status": r.get("status"),
                "daily_kwh": sc.get("daily_kwh"),
                "peak_kw": sc.get("peak_kw"),
                "energy_charge_usd": sc.get("energy_charge_usd"),
                "incremental_demand_charge_usd": sc.get("incremental_demand_charge_usd"),
                "total_modeled_objective": sc.get("total_modeled_objective"),
                "readiness_ok": sc.get("readiness_ok"),
                "trajectory_sha256": r.get("trajectory_sha256"),
            }
        )
    _write_csv(out / "candidate_ledger.csv", flat_ledger)
    _write_csv(out / "candidate_timing.csv", timing_rows)
    _write_csv(out / "quality_ledger.csv", quality_rows)

    compute_cmp = [
        {
            "category": "one_time_offline_rl_training_PRIMARY",
            "wall_s": rl_facts["PRIMARY"]["elapsed_s"],
            "note": "4 models × 8192 transitions",
        },
        {
            "category": "one_time_offline_rl_training_SECONDARY",
            "wall_s": rl_facts["SECONDARY"]["elapsed_s"],
            "note": "4 models × 8192 transitions",
        },
        {
            "category": "historical_grid_17day_screen",
            "wall_s": rl_facts["historical_grid_screen"]["wall_clock_s"],
            "note": "130 policies × 17 days",
        },
        {
            "category": "nightly_identical_state_grid",
            "wall_s": agg.get("total_wall_s"),
            "note": f"{len(ledger)} candidate-days on {contract.get('primary_benchmark_day')}",
        },
        {
            "category": "once_per_day_rl_inference_ppo_p50",
            "wall_s": ((inference.get("ppo") or {}).get("p50_ms") or 0) / 1000.0,
            "note": "p50 single predict",
        },
        {
            "category": "once_per_day_rl_inference_dqn_p50",
            "wall_s": ((inference.get("dqn") or {}).get("p50_ms") or 0) / 1000.0,
            "note": "p50 single predict",
        },
    ]
    _write_csv(out / "compute_comparison.csv", compute_cmp)

    (out / "environment_manifest.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    (out / "identical_state_proof.json").write_text(json.dumps(identical_state_proof, indent=2), encoding="utf-8")
    (out / "tariff_rescore.json").write_text(json.dumps(tariff_rescore, indent=2), encoding="utf-8")
    (out / "determinism_check.json").write_text(json.dumps(determinism, indent=2), encoding="utf-8")
    (out / "aggregate_compute.json").write_text(
        json.dumps({**agg, "parallel": parallel, "eplus_launches": eplus_launches}, indent=2),
        encoding="utf-8",
    )

    winners = {}
    for mode, blob in (tariff_rescore.get("by_tariff") or {}).items():
        winners[mode] = blob.get("winner")

    manifest = {
        "schema": "vibe22.nightly_grid_run_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site_run_dir": str(site_run_dir),
        "public_labels": PUBLIC_LABELS,
        "selection_wording": SELECTION_WORDING,
        "feasibility_verdict": verdict,
        "recommended_nightly_budget": budget_rec,
        "anytime": curve,
        "tariff_winners": winners,
        "target_15min_pass": bool(exhaustive_wall is not None and exhaustive_wall <= float(contract.get("deadline_target_s") or 900)),
        "hard_30min_pass": bool(exhaustive_wall is not None and exhaustive_wall <= float(contract.get("deadline_hard_s") or 1800)),
        "exhaustive_wall_s": exhaustive_wall,
        "n_unique_evaluated": len(ordered_results),
        "eplus_launches": eplus_launches,
        "bacnet_commands": 0,
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    generate_figures(
        out_dir=out,
        curve=curve,
        timing_rows=timing_rows,
        parallel=parallel,
        ledger=ledger,
        rl_facts=rl_facts,
        inference=inference,
        baseline_sched=baseline_sched,
        winner_sched=winner_sched,
    )

    labels = "\n".join(f"- `{x}`" for x in PUBLIC_LABELS)
    readme = f"""# Nightly A04 grid-search compute benchmark

> {SELECTION_WORDING}

## Public labels

{labels}

## Verdict

**`{verdict}`** — recommended nightly budget: **`{budget_rec}`**

Primary day: `{contract.get("primary_benchmark_day")}` (lookback `{contract.get("lookback_day")}`).  
Weather: `RETROSPECTIVE_WEATHER_BENCHMARK`. BACnet commands: **0**.

## Key numbers

- Unique candidates evaluated: {len(ordered_results)}
- EnergyPlus launches: {eplus_launches}
- Exhaustive wall (s): {exhaustive_wall}
- Candidates within 1% of exhaustive best: {curve.get("candidates_within_1pct")}
- Candidates within $10: {curve.get("candidates_within_10_usd")}
- 15-min target pass: {manifest["target_15min_pass"]}
- 30-min hard pass: {manifest["hard_30min_pass"]}

## Artifacts

See CSVs/JSON in this directory and `figures/` (9 PNG+SVG plots).
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    return out
