"""Publication figures for two-month policy replay pack."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np

from eplus_gym.rl.two_month_metrics import STRATEGY_LABELS, compare_vs_continuous_68


def _save(fig, out: Path, stem: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{stem}.png", dpi=140, bbox_inches="tight")
    fig.savefig(out / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def generate_all_figures(
    *,
    out_dir: Path,
    monthly_physical: Sequence[Mapping[str, Any]],
    flat_cost: Sequence[Mapping[str, Any]],
    tou_cost: Sequence[Mapping[str, Any]],
    daily_metrics: Sequence[Mapping[str, Any]],
    decision_table: Sequence[Mapping[str, Any]],
    results: Mapping[str, Mapping[str, Any]],
    utility_evidence: Mapping[str, Any],
) -> list[str]:
    fig_dir = out_dir / "figures"
    written: list[str] = []

    # 1. Actual utility vs A04 monthly kWh
    a04 = next((r for r in monthly_physical if r["strategy"] == "a04_native_sch_htgsp"), None)
    fig, ax = plt.subplots(figsize=(7, 4))
    months = ["Dec 2025", "Jan 2026"]
    util_kwh = [utility_evidence["dec_2025"]["kwh"], utility_evidence["jan_2026"]["kwh"]]
    ax.bar(np.arange(2) - 0.2, util_kwh, 0.4, label="Actual utility")
    if a04:
        sim = [
            next(r for r in monthly_physical if r["strategy"] == "a04_native_sch_htgsp" and r["period"] == "2025-12")["total_kwh"],
            next(r for r in monthly_physical if r["strategy"] == "a04_native_sch_htgsp" and r["period"] == "2026-01")["total_kwh"],
        ]
        ax.bar(np.arange(2) + 0.2, sim, 0.4, label="A04 native E+")
    ax.set_xticks(range(2))
    ax.set_xticklabels(months)
    ax.set_ylabel("kWh")
    ax.set_title("Actual utility vs A04 native monthly kWh")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, fig_dir, "fig01_actual_vs_a04_kwh")
    written.append("fig01_actual_vs_a04_kwh")

    strategies = sorted({r["strategy"] for r in monthly_physical if r["strategy"] != "actual_utility_cs351075"})
    labels = [STRATEGY_LABELS.get(s, s)[:28] for s in strategies]

    # 2. Monthly kWh by strategy
    for period, tag in (("2025-12", "dec"), ("2026-01", "jan")):
        vals = [
            next(r for r in monthly_physical if r["strategy"] == s and r["period"] == period)["total_kwh"]
            for s in strategies
        ]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.barh(labels, vals)
        ax.set_xlabel("kWh")
        ax.set_title(f"Monthly kWh by strategy ({period})")
        ax.grid(True, axis="x", alpha=0.3)
        _save(fig, fig_dir, f"fig02_monthly_kwh_{tag}")
        written.append(f"fig02_monthly_kwh_{tag}")

    # 3. Monthly peak by strategy
    for period, tag in (("2025-12", "dec"), ("2026-01", "jan")):
        vals = [
            next(r for r in monthly_physical if r["strategy"] == s and r["period"] == period)["peak_15min_kw"]
            for s in strategies
        ]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.barh(labels, vals, color="#c45c26")
        ax.set_xlabel("Peak kW (15-min)")
        ax.set_title(f"Monthly peak by strategy ({period})")
        ax.grid(True, axis="x", alpha=0.3)
        _save(fig, fig_dir, f"fig03_monthly_peak_{tag}")
        written.append(f"fig03_monthly_peak_{tag}")

    # 4–5. Stacked energy+demand bars
    for table, stem, title in (
        (flat_cost, "fig04_flat_stacked", "Illustrative FLAT energy + demand"),
        (tou_cost, "fig05_tou_stacked", "Illustrative TOU energy + demand"),
    ):
        fig, ax = plt.subplots(figsize=(10, 5))
        rows = [r for r in table if r.get("ranking_eligible") and r["period"] == "two_month"]
        names = [STRATEGY_LABELS.get(r["strategy"], r["strategy"])[:24] for r in rows]
        e = [float(r["energy_charge_usd"]) for r in rows]
        d = [float(r["demand_charge_usd"]) for r in rows]
        y = np.arange(len(names))
        ax.barh(y, e, label="Energy")
        ax.barh(y, d, left=e, label="Demand")
        ax.set_yticks(y)
        ax.set_yticklabels(names, fontsize=8)
        ax.set_xlabel("USD (illustrative)")
        ax.set_title(title)
        ax.legend()
        ax.grid(True, axis="x", alpha=0.3)
        _save(fig, fig_dir, stem)
        written.append(stem)

    # 6. Pareto kWh vs peak
    fig, ax = plt.subplots(figsize=(7, 6))
    for row in decision_table:
        ax.scatter(row["two_month_kwh"], row["two_month_peak_kw"], s=70)
        ax.annotate(row["public_label"][:20], (row["two_month_kwh"], row["two_month_peak_kw"]), fontsize=7)
    ax.set_xlabel("Two-month kWh")
    ax.set_ylabel("Two-month peak kW")
    ax.set_title("Two-month kWh vs max peak (Pareto view)")
    ax.grid(True, alpha=0.3)
    _save(fig, fig_dir, "fig06_pareto_kwh_peak")
    written.append("fig06_pareto_kwh_peak")

    # 7–8. Daily trajectories
    for metric, stem, ylab in (
        ("peak_kw", "fig07_daily_peak", "Daily peak kW"),
        ("daily_kwh", "fig08_daily_kwh", "Daily kWh"),
    ):
        fig, ax = plt.subplots(figsize=(12, 5))
        for s in strategies:
            pts = sorted(
                [r for r in daily_metrics if r["strategy"] == s],
                key=lambda r: r["day"],
            )
            if not pts:
                continue
            ax.plot([p["day"] for p in pts], [p[metric] for p in pts], label=STRATEGY_LABELS.get(s, s)[:18], linewidth=1)
        ax.set_ylabel(ylab)
        ax.set_title(f"Daily {metric} trajectories")
        ax.legend(fontsize=6, ncol=2)
        ax.grid(True, alpha=0.3)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
        _save(fig, fig_dir, stem)
        written.append(stem)

    # 9. Days beating continuous-68
    cmp = compare_vs_continuous_68(results)
    fig, ax = plt.subplots(figsize=(8, 5))
    names = [STRATEGY_LABELS.get(c["strategy"], c["strategy"])[:24] for c in cmp["comparisons"]]
    both = [c["days_both"] for c in cmp["comparisons"]]
    ax.barh(names, both)
    ax.set_xlabel("Days beating continuous-68 on peak AND kWh")
    ax.set_title("vs continuous-68 sensitivity reference")
    ax.grid(True, axis="x", alpha=0.3)
    _save(fig, fig_dir, "fig09_beats_continuous68")
    written.append("fig09_beats_continuous68")

    # 10–11. Representative day schedules (peak day per strategy subset)
    for day, stem, title in (
        ("2026-01-26", "fig10_cold_school_day", "Representative cold school-day facility kW"),
        ("2025-12-15", "fig11_mild_day", "Representative mid-Dec facility kW"),
    ):
        fig, ax = plt.subplots(figsize=(10, 5))
        for s in ("observed_bas_incumbent_v2", "continuous_68_heat_sensitivity", "frozen_ppo_flat_seed0"):
            payload = results.get(s)
            if not payload:
                continue
            days_list = sorted({str(r["day"]) for r in payload.get("daily") or []})
            if day not in days_list:
                continue
            i0 = days_list.index(day) * 96
            fac = payload["facility_kw"][i0 : i0 + 96]
            ax.plot(fac, label=STRATEGY_LABELS.get(s, s)[:20])
        ax.set_xlabel("15-min step")
        ax.set_ylabel("Facility kW")
        ax.set_title(title)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        _save(fig, fig_dir, stem)
        written.append(stem)

    # 12. Evidence flow diagram (text schematic)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axis("off")
    lines = [
        "Evidence flow (two-month replay)",
        "",
        "ACTUAL UTILITY (CS 351075) ──► actual_utility_evidence.csv (total bill only)",
        "        │",
        "        └── NOT ranked against illustrative tariff totals",
        "",
        "A04 IDF + EPW + 62 scored days ──► LIVE EnergyPlus (7 strategies)",
        "        │",
        "        ├── trajectory hashes ──► offline flat/TOU re-score",
        "        └── physical metrics ──► decision table (kWh/peak only)",
    ]
    ax.text(0.02, 0.98, "\n".join(lines), va="top", fontsize=10, family="monospace")
    _save(fig, fig_dir, "fig12_evidence_flow")
    written.append("fig12_evidence_flow")

    return written
