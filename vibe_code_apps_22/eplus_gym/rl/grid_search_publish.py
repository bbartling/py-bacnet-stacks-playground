"""Publish docs/results/grid_search pack from a finished LIVE screen run."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np

from eplus_gym.rl.day_ahead_tariff import load_day_ahead_tariff
from eplus_gym.rl.grid_search_menu import candidate_params_for_index
from eplus_gym.rl.grid_search_runner import DEC_FLOOR_DISCLOSURE, HONESTY
from eplus_gym.rl.grid_search_select import compare_grid_vs_rl

RL_FLAT = {
    "incumbent_total": 7623.65,
    "incumbent_peak": 201.88,
    "ppo_total": 7628.91,
    "ppo_peak": 233.77,
    "dqn_seed0_note": "not PRIMARY leader",
    "leader": "trained_ppo_seed0",
    "leader_ready": True,
    "elapsed_s": 27322.99,
}
RL_TOU = {
    "incumbent_total": 7082.56,
    "incumbent_peak": 201.88,
    "dqn_total": 7019.33,
    "dqn_peak": 211.51,
    "leader": "trained_dqn_seed1",
    "leader_ready": True,
    "elapsed_s": 19035.52,
}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def _save(fig: plt.Figure, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".png"), dpi=140, bbox_inches="tight")
    fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def publish_grid_pack(
    *,
    app_root: Path,
    screen_root: Path,
    pilot_root: Path | None = None,
    micro_root: Path | None = None,
    docs_out: Path | None = None,
) -> dict[str, Any]:
    screen_root = Path(screen_root)
    docs_out = Path(docs_out or (Path(app_root) / "docs" / "results" / "grid_search"))
    figs = docs_out / "figures"
    prov = docs_out / "provenance"
    docs_out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)
    prov.mkdir(parents=True, exist_ok=True)

    screen = json.loads((screen_root / "screen.json").read_text(encoding="utf-8"))
    scorecard = json.loads((screen_root / "scorecard.json").read_text(encoding="utf-8"))
    menu = json.loads((screen_root / "candidate_menu.json").read_text(encoding="utf-8"))
    traj = json.loads((screen_root / "trajectories_compact.json").read_text(encoding="utf-8"))

    # Scorecard CSV
    flat_rows = [c for c in scorecard if c["tariff_mode"] == "FLAT_PLUS_DEMAND"]
    ledger_rows = []
    for c in scorecard:
        p = candidate_params_for_index(int(c["action_index"]))
        ledger_rows.append(
            {
                "tariff_mode": c["tariff_mode"],
                "candidate_id": c["candidate_id"],
                "action_index": c["action_index"],
                "total_cost": round(c["total_cost"], 6),
                "energy_cost": round(c["energy_cost"], 6),
                "incremental_demand_cost": round(c["incremental_demand_cost"], 6),
                "peak_kw_max": round(c["peak_kw_max"], 6),
                "daily_kwh_sum": round(c["daily_kwh_sum"], 6),
                "eligible": c["eligible"],
                "ready_checked_school_days": c["readiness"]["ready_checked_school_days"],
                "checked_school_days": c["readiness"]["checked_school_days"],
                "unoccupied_heating_f": p.unoccupied_heating_f,
                "recovery_lead_minutes": p.recovery_lead_minutes,
                "post_occupancy_extension_minutes": p.post_occupancy_extension_minutes,
                "setback_offset_f": p.setback_offset_f,
                "continuous_conditioning": p.continuous_conditioning,
            }
        )
    _write_csv(docs_out / "grid_search_scorecard.csv", ledger_rows)
    _write_csv(docs_out / "grid_search_candidate_ledger.csv", ledger_rows)

    # Tariff sensitivity
    sens = []
    by_idx_tariff = {(c["action_index"], c["tariff_mode"]): c for c in scorecard}
    for idx in sorted({c["action_index"] for c in scorecard}):
        row = {"action_index": idx}
        for t in ("FLAT_PLUS_DEMAND", "ILLUSTRATIVE_TOU_PLUS_DEMAND", "ILLUSTRATIVE_DYNAMIC_HOURLY"):
            c = by_idx_tariff.get((idx, t))
            if c:
                row[f"{t}_total_cost"] = round(c["total_cost"], 4)
                row[f"{t}_peak_kw"] = round(c["peak_kw_max"], 4)
                row[f"{t}_eligible"] = c["eligible"]
        sens.append(row)
    _write_csv(docs_out / "grid_search_tariff_sensitivity.csv", sens)

    leaders = screen["leaders"]
    flat_leader = leaders["FLAT_PLUS_DEMAND"]
    tou_leader = leaders["ILLUSTRATIVE_TOU_PLUS_DEMAND"]
    dyn_leader = leaders["ILLUSTRATIVE_DYNAMIC_HOURLY"]
    flat_grid = next(c for c in scorecard if c["candidate_id"] == flat_leader["grid_validation_leader"] and c["tariff_mode"] == "FLAT_PLUS_DEMAND")
    tou_grid = next(c for c in scorecard if c["candidate_id"] == tou_leader["grid_validation_leader"] and c["tariff_mode"] == "ILLUSTRATIVE_TOU_PLUS_DEMAND")

    flat_verdict = compare_grid_vs_rl(
        grid=flat_grid,
        rl_total=RL_FLAT["ppo_total"],
        rl_peak=RL_FLAT["ppo_peak"],
        rl_ready=True,
        screen_exhaustive=screen["status"] == "EXHAUSTIVE_FIXED_POLICY",
    )
    tou_verdict = compare_grid_vs_rl(
        grid=tou_grid,
        rl_total=RL_TOU["dqn_total"],
        rl_peak=RL_TOU["dqn_peak"],
        rl_ready=True,
        screen_exhaustive=screen["status"] == "EXHAUSTIVE_FIXED_POLICY",
    )
    if screen["status"] != "EXHAUSTIVE_FIXED_POLICY":
        flat_verdict = "SCREEN_NOT_EXHAUSTIVE"
        tou_verdict = "SCREEN_NOT_EXHAUSTIVE"

    tariff_changed_strategy = flat_leader["action_index"] != tou_leader["action_index"]

    verdict = {
        "schema": "vibe22.grid_search_verdict.v1",
        "honesty_labels": HONESTY,
        "screen_status": screen["status"],
        "DAILY_ADAPTIVE_GRID_STATUS": screen.get("DAILY_ADAPTIVE_GRID_STATUS"),
        "december_billing_floor_disclosure": DEC_FLOOR_DISCLOSURE,
        "FLAT_PLUS_DEMAND": {
            "verdict": flat_verdict,
            "grid_validation_leader": flat_leader.get("grid_validation_leader"),
            "grid_total_cost": flat_leader.get("total_cost"),
            "grid_peak_kw": flat_leader.get("peak_kw_max"),
            "rl_validation_leader": RL_FLAT["leader"],
            "rl_total_cost": RL_FLAT["ppo_total"],
            "rl_peak_kw": RL_FLAT["ppo_peak"],
            "delta_cost_grid_minus_rl": float(flat_leader["total_cost"]) - RL_FLAT["ppo_total"],
            "delta_peak_grid_minus_rl": float(flat_leader["peak_kw_max"]) - RL_FLAT["ppo_peak"],
            "params": candidate_params_for_index(int(flat_leader["action_index"])).__dict__,
        },
        "ILLUSTRATIVE_TOU_PLUS_DEMAND": {
            "verdict": tou_verdict,
            "grid_validation_leader": tou_leader.get("grid_validation_leader"),
            "grid_total_cost": tou_leader.get("total_cost"),
            "grid_peak_kw": tou_leader.get("peak_kw_max"),
            "rl_validation_leader": RL_TOU["leader"],
            "rl_total_cost": RL_TOU["dqn_total"],
            "rl_peak_kw": RL_TOU["dqn_peak"],
            "delta_cost_grid_minus_rl": float(tou_leader["total_cost"]) - RL_TOU["dqn_total"],
            "delta_peak_grid_minus_rl": float(tou_leader["peak_kw_max"]) - RL_TOU["dqn_peak"],
            "params": candidate_params_for_index(int(tou_leader["action_index"])).__dict__,
        },
        "tariff_changed_selected_grid_strategy": tariff_changed_strategy,
        "never_compare_absolute_dollars_across_tariffs": True,
    }
    (docs_out / "grid_search_verdict.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    compute = {
        "schema": "vibe22.grid_search_compute_comparison.v1",
        "honesty_labels": HONESTY,
        "grid": {
            "declared_actions": screen["declared_action_count"],
            "unique_fixed_policies": screen["n_unique_fixed_policies"],
            "n_process_starts": screen["n_process_starts"],
            "candidate_days": screen["candidate_days"],
            "valid_trajectory_days": screen["valid_trajectory_days"],
            "failed_policies": screen["failed_policies"],
            "wall_clock_s": screen["elapsed_s"],
            "tariff_rescore_note": "three tariffs scored from identical stored trajectories (no extra E+)",
        },
        "finished_rl": {
            "models_per_campaign": 4,
            "transitions_per_model": 8192,
            "transitions_per_campaign": 32768,
            "PRIMARY_elapsed_s": RL_FLAT["elapsed_s"],
            "SECONDARY_elapsed_s": RL_TOU["elapsed_s"],
            "actual_energyplus_process_launches": None,
            "note": "not recorded in historical campaign_manifest; do not invent",
            "policy_inference_ms_estimate": "<10 ms typical SB3 predict (not re-benchmarked here)",
        },
        "views": {
            "one_time_research": {
                "rl_PRIMARY_s": RL_FLAT["elapsed_s"],
                "rl_SECONDARY_s": RL_TOU["elapsed_s"],
                "grid_exhaustive_s": screen["elapsed_s"],
            },
            "new_tariff": {
                "rl": "may require re-eval or retrain depending on generalization",
                "grid": "cheap re-score of stored facility/zone trajectories",
            },
            "daily_deployment": {
                "rl": "fast policy inference",
                "grid": "requires candidate E+ sims unless reusable lookup/cache applies",
                "daily_adaptive_branching": screen.get("DAILY_ADAPTIVE_GRID_STATUS"),
            },
        },
        "site_run_roots": {
            "screen": str(screen_root),
            "pilot": str(pilot_root) if pilot_root else None,
            "micro": str(micro_root) if micro_root else None,
        },
        "bacnet_commands": 0,
    }
    (docs_out / "grid_search_compute_comparison.json").write_text(
        json.dumps(compute, indent=2), encoding="utf-8"
    )

    summary = {
        "schema": "vibe22.grid_search_summary.v1",
        "honesty_labels": HONESTY,
        "screen_status": screen["status"],
        "declared_action_count": screen["declared_action_count"],
        "n_unique_fixed_policies": screen["n_unique_fixed_policies"],
        "candidate_menu_sha256": screen["candidate_menu_sha256"],
        "candidate_days": screen["candidate_days"],
        "n_process_starts": screen["n_process_starts"],
        "valid_trajectory_days": screen["valid_trajectory_days"],
        "failed_policies": screen["failed_policies"],
        "elapsed_s": screen["elapsed_s"],
        "idf_sha256": screen["idf_sha256"],
        "epw_sha256": screen["epw_sha256"],
        "leaders": leaders,
        "verdict_flat": flat_verdict,
        "verdict_tou": tou_verdict,
        "tariff_changed_selected_grid_strategy": tariff_changed_strategy,
        "DAILY_ADAPTIVE_GRID_STATUS": screen.get("DAILY_ADAPTIVE_GRID_STATUS"),
        "december_billing_floor_disclosure": DEC_FLOOR_DISCLOSURE,
        "bacnet_commands": 0,
    }
    (docs_out / "grid_search_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Provenance pointers (no raw eplus_out)
    (prov / "screen_pointer.json").write_text(
        json.dumps(
            {
                "screen_root": str(screen_root),
                "idf_sha256": screen["idf_sha256"],
                "epw_sha256": screen["epw_sha256"],
                "candidate_menu_sha256": screen["candidate_menu_sha256"],
                "do_not_commit_raw_eplus_out": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Figures
    _fig_landscape(figs, flat_rows, flat_leader, RL_FLAT)
    _fig_decomp(figs, scorecard, flat_leader, tou_leader, RL_FLAT, RL_TOU)
    _fig_tariff_load(figs, app_root, traj, flat_leader)
    _fig_heatmap(figs, flat_rows)
    _fig_compute(figs, screen, RL_FLAT, RL_TOU)
    _fig_table(figs, flat_rows, tou_grid if False else flat_rows, flat_leader, tou_leader, RL_FLAT, RL_TOU)

    readme = f"""# Vibe22 discrete grid-search comparator

Honesty: {'; '.join(HONESTY)}

## Status

- Screen: **{screen['status']}**
- Declared actions: {screen['declared_action_count']}
- Unique fixed policies simulated: {screen['n_unique_fixed_policies']}
- Candidate-days: {screen['candidate_days']}
- EnergyPlus process launches: {screen['n_process_starts']}
- Wall-clock: {screen['elapsed_s']:.1f} s
- Daily adaptive: `{screen.get('DAILY_ADAPTIVE_GRID_STATUS')}`

## Grid validation leaders

| Tariff | Leader | Total $ | Peak kW | vs RL |
| --- | --- | ---: | ---: | --- |
| FLAT_PLUS_DEMAND | {flat_leader.get('grid_validation_leader')} | {flat_leader.get('total_cost'):.2f} | {flat_leader.get('peak_kw_max'):.2f} | {flat_verdict} (PPO {RL_FLAT['ppo_total']:.2f}) |
| ILLUSTRATIVE_TOU | {tou_leader.get('grid_validation_leader')} | {tou_leader.get('total_cost'):.2f} | {tou_leader.get('peak_kw_max'):.2f} | {tou_verdict} (DQN {RL_TOU['dqn_total']:.2f}) |

Tariff changed selected strategy: **{tariff_changed_strategy}**

> {DEC_FLOOR_DISCLOSURE}

Never compare absolute dollars across tariffs. Simulation-only; not operational DSM.
"""
    (docs_out / "README.md").write_text(readme, encoding="utf-8")
    return {"docs_out": str(docs_out), "summary": summary, "verdict": verdict}


def _fig_landscape(figs: Path, flat_rows: list[dict], flat_leader: dict, rl: dict) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    rows = []
    for c in flat_rows:
        rate = c["readiness"]["readiness_rate_checked_school_days"] or 0
        color = "#0b6e4f" if c["eligible"] else "#c45c26"
        ax.scatter(c["peak_kw_max"], c["total_cost"], c=color, s=40, alpha=0.7)
        rows.append(
            {
                "action_index": c["action_index"],
                "peak_kw_max": c["peak_kw_max"],
                "total_cost": c["total_cost"],
                "eligible": c["eligible"],
            }
        )
    ax.scatter(flat_leader["peak_kw_max"], flat_leader["total_cost"], marker="*", s=220, c="#0b6e4f", label="grid leader")
    ax.scatter(rl["ppo_peak"], rl["ppo_total"], marker="D", s=100, c="#1f4e79", label="PPO leader")
    ax.scatter(rl["incumbent_peak"], rl["incumbent_total"], marker="s", s=100, c="#555555", label="incumbent (RL pack)")
    ax.set_xlabel("Validation max peak kW")
    ax.set_ylabel("Total modeled USD (FLAT)")
    ax.set_title("Grid candidate cost landscape (FLAT_PLUS_DEMAND)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    stem = figs / "grid_candidate_cost_landscape"
    _save(fig, stem)
    _write_csv(stem.with_name(stem.name + "_source.csv"), rows)
    (stem.with_name(stem.name + "_provenance.json")).write_text(
        json.dumps({"figure": "grid_candidate_cost_landscape", "honesty_labels": HONESTY}, indent=2),
        encoding="utf-8",
    )


def _fig_decomp(figs, scorecard, flat_leader, tou_leader, rl_flat, rl_tou) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, tariff, leader, rl_total, title in (
        (axes[0], "FLAT_PLUS_DEMAND", flat_leader, rl_flat["ppo_total"], "FLAT"),
        (axes[1], "ILLUSTRATIVE_TOU_PLUS_DEMAND", tou_leader, rl_tou["dqn_total"], "ILLUSTRATIVE TOU"),
    ):
        rows = [c for c in scorecard if c["tariff_mode"] == tariff]
        picks = []
        for idx in (0, 1, int(leader["action_index"])):
            hits = [c for c in rows if c["action_index"] == idx]
            if hits:
                picks.append(hits[0])
        labels = [f"idx{c['action_index']}" for c in picks] + ["RL leader"]
        energy = [c["energy_cost"] for c in picks] + [None]
        demand = [c["incremental_demand_cost"] for c in picks] + [None]
        # RL pack only has totals - show as single bar approximation unavailable; skip stack for RL
        x = np.arange(len(picks))
        ax.bar(x, [c["energy_cost"] for c in picks], label="energy", color="#1f4e79")
        ax.bar(
            x,
            [c["incremental_demand_cost"] for c in picks],
            bottom=[c["energy_cost"] for c in picks],
            label="demand",
            color="#c45c26",
        )
        ax.axhline(rl_total, color="#0b6e4f", linestyle="--", label="RL leader total")
        ax.set_xticks(x)
        ax.set_xticklabels([f"idx{c['action_index']}" for c in picks], rotation=20)
        ax.set_title(title)
        ax.legend(fontsize=8)
        ax.grid(True, axis="y", alpha=0.3)
    fig.suptitle("Cost decomposition (grid arms vs RL leader total)")
    stem = figs / "grid_cost_decomposition"
    _save(fig, stem)
    (stem.with_name(stem.name + "_provenance.json")).write_text(
        json.dumps({"figure": "grid_cost_decomposition", "honesty_labels": HONESTY}, indent=2),
        encoding="utf-8",
    )


def _fig_tariff_load(figs, app_root, traj, flat_leader) -> None:
    fixtures = Path(app_root) / "contracts" / "fixtures" / "tariffs"
    flat = load_day_ahead_tariff(fixtures / "flat_plus_demand.json")
    tou = load_day_ahead_tariff(fixtures / "illustrative_evening_tou.json")
    dyn = load_day_ahead_tariff(fixtures / "illustrative_dynamic_hourly.json")
    idx = str(flat_leader["action_index"])
    day = "2025-12-15"
    fac = traj["policies"][idx]["trajectories"][day]["facility_kw"]
    fig, ax1 = plt.subplots(figsize=(10, 5))
    hours = np.arange(24)
    ax1.step(hours, flat["energy_prices"], where="mid", label="flat $/kWh", color="#1f4e79")
    ax1.step(hours, tou["energy_prices"], where="mid", label="TOU $/kWh", color="#c45c26")
    ax1.step(hours, dyn["energy_prices"], where="mid", label="dynamic $/kWh", color="#0b6e4f")
    ax1.set_ylabel("Energy price USD/kWh")
    ax2 = ax1.twinx()
    # downsample facility to hourly mean
    fac_h = [float(np.mean(fac[i * 4 : (i + 1) * 4])) for i in range(24)]
    ax2.plot(hours, fac_h, color="#333333", linewidth=2, label="facility kW (hourly mean)")
    ax2.set_ylabel("Facility kW")
    ax1.set_xlabel("Hour")
    ax1.set_title(f"Tariff vectors + selected load (idx {idx} @ {day})")
    ax1.legend(loc="upper left", fontsize=8)
    ax2.legend(loc="upper right", fontsize=8)
    stem = figs / "tariff_vector_and_selected_load"
    _save(fig, stem)
    _write_csv(
        stem.with_name(stem.name + "_source.csv"),
        [
            {
                "hour": h,
                "flat": flat["energy_prices"][h],
                "tou": tou["energy_prices"][h],
                "dynamic": dyn["energy_prices"][h],
                "facility_kw_mean": fac_h[h],
            }
            for h in range(24)
        ],
    )
    (stem.with_name(stem.name + "_provenance.json")).write_text(
        json.dumps(
            {
                "figure": "tariff_vector_and_selected_load",
                "series_kind": "STORED_TRAJECTORY_REPLAY",
                "honesty_labels": HONESTY,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _fig_heatmap(figs, flat_rows) -> None:
    # Parameter scatter as heatmap proxy
    fig, ax = plt.subplots(figsize=(9, 6))
    xs, ys, cs, rows = [], [], [], []
    for c in flat_rows:
        p = candidate_params_for_index(int(c["action_index"]))
        xs.append(p.recovery_lead_minutes)
        ys.append(p.unoccupied_heating_f)
        cs.append(c["total_cost"])
        rows.append(
            {
                "action_index": c["action_index"],
                "recovery_lead_minutes": p.recovery_lead_minutes,
                "unoccupied_heating_f": p.unoccupied_heating_f,
                "extension": p.post_occupancy_extension_minutes,
                "total_cost": c["total_cost"],
                "eligible": c["eligible"],
            }
        )
    sc = ax.scatter(xs, ys, c=cs, cmap="viridis", s=50)
    fig.colorbar(sc, ax=ax, label="Total modeled USD")
    ax.set_xlabel("Recovery lead minutes")
    ax.set_ylabel("Unoccupied heating °F")
    ax.set_title("Grid schedule parameter map (FLAT costs)")
    ax.grid(True, alpha=0.3)
    stem = figs / "grid_schedule_heatmap"
    _save(fig, stem)
    _write_csv(stem.with_name(stem.name + "_source.csv"), rows)
    (stem.with_name(stem.name + "_provenance.json")).write_text(
        json.dumps({"figure": "grid_schedule_heatmap", "honesty_labels": HONESTY}, indent=2),
        encoding="utf-8",
    )


def _fig_compute(figs, screen, rl_flat, rl_tou) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = ["RL PRIMARY\ntrain+val", "RL SECONDARY\ntrain+val", "Grid exhaustive\nscreen", "Tariff\nre-score≈0"]
    vals = [rl_flat["elapsed_s"] / 3600.0, rl_tou["elapsed_s"] / 3600.0, screen["elapsed_s"] / 3600.0, 0.01]
    ax.bar(labels, vals, color=["#1f4e79", "#1f4e79", "#0b6e4f", "#888888"])
    ax.set_ylabel("Wall-clock hours")
    ax.set_title("Compute cost comparison (one-time research)")
    ax.grid(True, axis="y", alpha=0.3)
    stem = figs / "compute_cost_comparison"
    _save(fig, stem)
    _write_csv(
        stem.with_name(stem.name + "_source.csv"),
        [{"label": l, "hours": v} for l, v in zip(labels, vals)],
    )
    (stem.with_name(stem.name + "_provenance.json")).write_text(
        json.dumps({"figure": "compute_cost_comparison", "honesty_labels": HONESTY}, indent=2),
        encoding="utf-8",
    )


def _fig_table(figs, flat_rows, _tou_rows, flat_leader, tou_leader, rl_flat, rl_tou) -> None:
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.axis("off")
    by = {c["action_index"]: c for c in flat_rows}
    cells = [
        ["Strategy", "FLAT total $", "FLAT peak", "TOU total $", "Ready 5/5"],
        ["Incumbent (RL pack)", f"{rl_flat['incumbent_total']:.0f}", f"{rl_flat['incumbent_peak']:.0f}", f"{rl_tou['incumbent_total']:.0f}", "see pack"],
        ["Continuous 68", f"{by[0]['total_cost']:.0f}", f"{by[0]['peak_kw_max']:.0f}", "-", str(by[0]['eligible'])],
        ["Continuous 70", f"{by[1]['total_cost']:.0f}", f"{by[1]['peak_kw_max']:.0f}", "-", str(by[1]['eligible'])],
        ["Grid leader", f"{flat_leader['total_cost']:.0f}", f"{flat_leader['peak_kw_max']:.0f}", f"{tou_leader['total_cost']:.0f}", "True"],
        ["PPO / DQN leaders", f"{rl_flat['ppo_total']:.0f}", f"{rl_flat['ppo_peak']:.0f}", f"{rl_tou['dqn_total']:.0f}", "True"],
    ]
    table = ax.table(cellText=cells, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.4)
    ax.set_title("Strategy comparison (do not mix FLAT/TOU dollars as one ranking)")
    stem = figs / "strategy_comparison_table"
    _save(fig, stem)
    (stem.with_name(stem.name + "_provenance.json")).write_text(
        json.dumps({"figure": "strategy_comparison_table", "honesty_labels": HONESTY}, indent=2),
        encoding="utf-8",
    )
