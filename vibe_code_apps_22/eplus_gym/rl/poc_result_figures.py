"""Publication figures for Vibe22 RL PoC results pack (no EnergyPlus)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np

from eplus_gym.rl.poc_results_publish import HONESTY_LABELS, REPRESENTATIVE_DAY

DISPLAY_ARMS = [
    "incumbent",
    "continuous_68",
    "continuous_70",
    "shallow_setback",
    "random",
    "trained_ppo_seed0",
    "trained_ppo_seed1",
    "trained_dqn_seed0",
    "trained_dqn_seed1",
]


def _save_fig(fig: plt.Figure, out_stem: Path) -> None:
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_stem.with_suffix(".png"), dpi=140, bbox_inches="tight")
    fig.savefig(out_stem.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


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


def _prov(path: Path, **payload: Any) -> None:
    body = {
        "honesty_labels": HONESTY_LABELS,
        **payload,
    }
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")


def _arm_ready_frac(block: dict[str, Any], arm: str) -> float:
    tot = (block.get("arm_totals") or {}).get(arm) or {}
    ready = tot.get("readiness") or {}
    rate = ready.get("readiness_rate_checked_school_days")
    return float(rate) if rate is not None else float("nan")


def figure_cost_decomposition(
    *,
    primary: dict[str, Any],
    secondary: dict[str, Any],
    out_dir: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)
    panels = [
        (axes[0], primary, "PRIMARY FLAT_PLUS_DEMAND"),
        (axes[1], secondary, "SECONDARY ILLUSTRATIVE_TOU"),
    ]
    csv_rows: list[dict[str, Any]] = []
    for ax, block, title in panels:
        arms = [a for a in DISPLAY_ARMS if a in (block.get("arm_totals") or {})]
        energy = [float(block["arm_totals"][a]["energy_cost"]) for a in arms]
        demand = [float(block["arm_totals"][a]["incremental_demand_cost"]) for a in arms]
        x = np.arange(len(arms))
        ax.bar(x, energy, label="energy_cost", color="#1f4e79")
        ax.bar(x, demand, bottom=energy, label="incremental_demand_cost", color="#c45c26")
        ax.set_xticks(x)
        ax.set_xticklabels(arms, rotation=55, ha="right", fontsize=8)
        ax.set_title(title)
        ax.set_ylabel("Modeled USD (illustrative tariff accounting)")
        ax.grid(True, axis="y", alpha=0.3)
        leader = block.get("validation_leader")
        for i, a in enumerate(arms):
            rate = _arm_ready_frac(block, a)
            ax.text(
                i,
                energy[i] + demand[i],
                f"{rate:.0%}" if rate == rate else "n/a",
                ha="center",
                va="bottom",
                fontsize=7,
            )
            if a == leader:
                ax.axvline(i, color="#0b6e4f", linestyle="--", alpha=0.5, linewidth=1)
            csv_rows.append(
                {
                    "experiment_id": block["experiment_id"],
                    "arm": a,
                    "energy_cost": energy[i],
                    "incremental_demand_cost": demand[i],
                    "total_cost": energy[i] + demand[i],
                    "checked_school_readiness_rate": rate,
                    "is_validation_leader": a == leader,
                }
            )
        ax.legend(loc="upper left", fontsize=8)
    fig.suptitle(
        "Cost decomposition by tariff (checked-school readiness % above bars)",
        fontsize=11,
    )
    fig.text(
        0.5,
        0.01,
        "SIMULATION-ONLY · TOU illustrative · never mix PRIMARY/SECONDARY dollars",
        ha="center",
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    stem = out_dir / "cost_decomposition_by_tariff"
    _save_fig(fig, stem)
    _write_csv(stem.with_name(stem.name + "_source.csv"), csv_rows)
    _prov(
        stem.with_name(stem.name + "_provenance.json"),
        figure="cost_decomposition_by_tariff",
        source="eval.json arm aggregates via poc_results_publish",
    )


def figure_peak_tradeoff(
    *,
    primary: dict[str, Any],
    secondary: dict[str, Any],
    out_dir: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    csv_rows: list[dict[str, Any]] = []
    for ax, block, title in (
        (axes[0], primary, "PRIMARY FLAT_PLUS_DEMAND"),
        (axes[1], secondary, "SECONDARY ILLUSTRATIVE_TOU"),
    ):
        leader = block.get("validation_leader")
        for arm, tot in (block.get("arm_totals") or {}).items():
            if arm not in DISPLAY_ARMS:
                continue
            rate = _arm_ready_frac(block, arm)
            peak = float(tot["peak_kw_max"])
            cost = float(tot["total_cost"])
            color = "#0b6e4f" if rate == 1.0 else ("#c45c26" if rate == rate and rate < 1.0 else "#888888")
            marker = "*" if arm == leader else ("s" if arm == "incumbent" else "o")
            size = 160 if arm in {leader, "incumbent"} else 60
            ax.scatter(peak, cost, c=color, marker=marker, s=size, zorder=3)
            ax.annotate(arm, (peak, cost), fontsize=6, xytext=(4, 4), textcoords="offset points")
            csv_rows.append(
                {
                    "experiment_id": block["experiment_id"],
                    "arm": arm,
                    "peak_kw_max": peak,
                    "total_cost": cost,
                    "checked_school_readiness_rate": rate,
                    "is_validation_leader": arm == leader,
                }
            )
        ax.set_xlabel("Facility peak kW (validation max)")
        ax.set_ylabel("Total modeled USD")
        ax.set_title(title + "\n(both leaders raised peak vs incumbent)")
        ax.grid(True, alpha=0.3)
    fig.text(
        0.5,
        0.01,
        "Green=100% checked-school ready; orange=<100%; star=validation leader; square=incumbent",
        ha="center",
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    stem = out_dir / "peak_and_readiness_tradeoff"
    _save_fig(fig, stem)
    _write_csv(stem.with_name(stem.name + "_source.csv"), csv_rows)
    _prov(
        stem.with_name(stem.name + "_provenance.json"),
        figure="peak_and_readiness_tradeoff",
        source="eval.json arm aggregates",
    )


def _row_for(block: dict[str, Any], arm: str, day: str) -> dict[str, Any] | None:
    for r in block.get("rows") or []:
        if str(r.get("arm")) == arm and str(r.get("day"))[:10] == day:
            return r
    return None


def _zone_mean_series(proof: dict[str, Any]) -> tuple[list[float], float]:
    htg = proof.get("heating_setpoints_f") or {}
    if not htg:
        return [float("nan")] * 96, 0.0
    mats = list(htg.values())
    arr = np.asarray(mats, dtype=float)
    mean = arr.mean(axis=0).tolist()
    spread = float(arr.max(axis=0).max() - arr.min(axis=0).min()) if arr.size else 0.0
    return mean, spread


def figure_control_plan(
    *,
    primary: dict[str, Any],
    secondary: dict[str, Any],
    out_dir: Path,
    day: str = REPRESENTATIVE_DAY,
) -> None:
    specs = [
        ("incumbent", primary, "incumbent (PRIMARY eval)"),
        (primary.get("validation_leader"), primary, "PRIMARY validation leader"),
        (secondary.get("validation_leader"), secondary, "SECONDARY validation leader"),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    csv_rows: list[dict[str, Any]] = []
    for ax, (arm, block, title) in zip(axes, specs):
        row = _row_for(block, str(arm), day)
        if row is None:
            ax.set_title(f"{title}: missing {arm} on {day}")
            continue
        proof = row.get("schedule_proof") or {}
        mean, spread = _zone_mean_series(proof)
        ax.plot(mean, color="#1f4e79", linewidth=2, label="mean heating DualSP °F")
        ax.fill_between(
            range(96),
            np.asarray(mean) - spread / 2.0,
            np.asarray(mean) + spread / 2.0,
            color="#1f4e79",
            alpha=0.15,
            label="six-zone range",
        )
        win = proof.get("school_occupancy_window") or {}
        start = int(win.get("start_step") or proof.get("fixed_occupied_start_step") or 0)
        end = int(win.get("end_step") or proof.get("fixed_occupied_end_step") or 0)
        if win.get("school_occupied"):
            ax.axvspan(start, end, color="#90c978", alpha=0.25, label="school occupancy")
        rec = proof.get("recovery_begin_step")
        if rec is not None:
            ax.axvline(int(rec), color="#c45c26", linestyle="--", label="recovery begin")
        ext = proof.get("post_occupancy_extension_minutes")
        ax.set_ylabel("°F")
        ax.set_title(
            f"{title}: {arm} @ {day} | extension_min={ext} | "
            f"continuous={proof.get('continuous_conditioning')}"
        )
        ax.set_ylim(58, 76)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", fontsize=7)
        for t, v in enumerate(mean):
            csv_rows.append(
                {
                    "day": day,
                    "panel": title,
                    "arm": arm,
                    "step": t,
                    "mean_heating_f": v,
                    "zone_spread_f": spread,
                    "school_start": start,
                    "school_end": end,
                    "recovery_begin_step": rec,
                    "post_occupancy_extension_minutes": ext,
                }
            )
    axes[-1].set_xlabel("15-min step (0–95)")
    fig.suptitle("Representative daily control plan (schedule_proof)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    stem = out_dir / "representative_daily_control_plan"
    _save_fig(fig, stem)
    _write_csv(stem.with_name(stem.name + "_source.csv"), csv_rows)
    _prov(
        stem.with_name(stem.name + "_provenance.json"),
        figure="representative_daily_control_plan",
        day=day,
        source="eval.json schedule_proof",
    )


def figure_day_outcomes(
    *,
    primary: dict[str, Any],
    secondary: dict[str, Any],
    out_dir: Path,
    day: str = REPRESENTATIVE_DAY,
) -> None:
    """Aggregate-only outcomes — timestep facility series were not retained."""
    fig, axes = plt.subplots(2, 1, figsize=(11, 7))
    arms = [
        ("incumbent", primary),
        (primary.get("validation_leader"), primary),
        (secondary.get("validation_leader"), secondary),
    ]
    labels = []
    peaks = []
    kwhs = []
    energy = []
    demand = []
    csv_rows: list[dict[str, Any]] = []
    for arm, block in arms:
        row = _row_for(block, str(arm), day)
        label = f"{block['experiment_id'][:12]}:{arm}"
        labels.append(label)
        if row is None:
            peaks.append(0.0)
            kwhs.append(0.0)
            energy.append(0.0)
            demand.append(0.0)
            continue
        peaks.append(float(row.get("peak_kw") or 0.0))
        kwhs.append(float(row.get("daily_kwh") or 0.0))
        energy.append(float(row.get("energy_cost") or 0.0))
        demand.append(float(row.get("incremental_demand_cost") or 0.0))
        proof = row.get("schedule_proof") or {}
        mean, _ = _zone_mean_series(proof)
        csv_rows.append(
            {
                "day": day,
                "experiment_id": block["experiment_id"],
                "arm": arm,
                "peak_kw": peaks[-1],
                "daily_kwh": kwhs[-1],
                "energy_cost": energy[-1],
                "incremental_demand_cost": demand[-1],
                "readiness_ok": row.get("readiness_ok"),
                "opening_mtd_kw": row.get("opening_mtd_kw"),
                "mean_htg_sp_f_at_step30": mean[30] if len(mean) > 30 else None,
                "mean_htg_sp_f_at_step31": mean[31] if len(mean) > 31 else None,
                "series_kind": "AGGREGATE_FROM_EVAL_JSON_NOT_TIMESTEP_REPLAY",
            }
        )
    x = np.arange(len(labels))
    axes[0].bar(x - 0.2, peaks, width=0.4, label="peak_kw", color="#1f4e79")
    axes[0].bar(x + 0.2, kwhs, width=0.4, label="daily_kwh", color="#0b6e4f")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=20, ha="right")
    axes[0].set_title(f"Representative day outcomes @ {day} (daily aggregates)")
    axes[0].legend()
    axes[0].grid(True, axis="y", alpha=0.3)
    axes[1].bar(x - 0.2, energy, width=0.4, label="energy_cost", color="#1f4e79")
    axes[1].bar(x + 0.2, demand, width=0.4, label="incremental_demand_cost", color="#c45c26")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=20, ha="right")
    axes[1].set_title("Same-day cost components + readiness DualSP at steps 30–31 (not zone MAT)")
    axes[1].legend()
    axes[1].grid(True, axis="y", alpha=0.3)
    fig.text(
        0.5,
        0.01,
        "AGGREGATE_FROM_EVAL_JSON_NOT_TIMESTEP_REPLAY — facility/zone MAT 15-min series not retained",
        ha="center",
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    stem = out_dir / "representative_day_outcomes"
    _save_fig(fig, stem)
    _write_csv(stem.with_name(stem.name + "_source.csv"), csv_rows)
    _prov(
        stem.with_name(stem.name + "_provenance.json"),
        figure="representative_day_outcomes",
        day=day,
        series_kind="AGGREGATE_FROM_EVAL_JSON_NOT_TIMESTEP_REPLAY",
        source="eval.json daily fields + schedule_proof setpoints",
    )


def write_all_figures(
    *,
    primary: dict[str, Any],
    secondary: dict[str, Any],
    out_dir: Path,
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    figure_cost_decomposition(primary=primary, secondary=secondary, out_dir=out_dir)
    figure_peak_tradeoff(primary=primary, secondary=secondary, out_dir=out_dir)
    figure_control_plan(primary=primary, secondary=secondary, out_dir=out_dir)
    figure_day_outcomes(primary=primary, secondary=secondary, out_dir=out_dir)
