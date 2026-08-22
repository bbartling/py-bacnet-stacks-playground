"""Figures for weather-triggered continuous-conditioning pack."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np

from eplus_gym.rl.weather_trigger_metrics import COLD_TRIGGER_IDS, STRATEGY_LABELS, WEATHER_POLICY_IDS

BANNERS = (
    "SIMULATION-ONLY RESEARCH",
    "A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION",
    "ILLUSTRATIVE COSTS",
    "NO BACNET COMMAND AUTHORITY",
)


def _banner(ax) -> None:
    ax.text(
        0.01,
        1.02,
        " | ".join(BANNERS),
        transform=ax.transAxes,
        fontsize=7,
        color="#444",
        va="bottom",
    )


def _save(fig, out: Path, stem: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{stem}.png", dpi=140, bbox_inches="tight")
    fig.savefig(out / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def _threshold_tag(strategy: str) -> float | None:
    mapping = {
        "COLD_TRIGGER_10F": 10.0,
        "COLD_TRIGGER_20F": 20.0,
        "COLD_TRIGGER_30F": 30.0,
        "COLD_TRIGGER_20F_4H": 20.4,
        "COLD_TRIGGER_20F_8H": 20.8,
        "ALWAYS_GRID_114": 0.0,
        "ALWAYS_CONTINUOUS_68_74": -1.0,
    }
    return mapping.get(strategy)


def generate_weather_figures(
    *,
    out_dir: Path,
    summaries: Sequence[Mapping[str, Any]],
    results: Mapping[str, Mapping[str, Any]],
    daily_triggers: Sequence[Mapping[str, Any]],
    compute_rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    fig_dir = out_dir / "figures"
    written: list[str] = []
    by_s = {r["strategy"]: r for r in summaries}

    # 1 peak vs energy scatter
    fig, ax = plt.subplots(figsize=(8, 5))
    for s, r in by_s.items():
        ax.scatter(r["two_month_kwh"], r["two_month_peak_15min_kw"], label=STRATEGY_LABELS.get(s, s)[:22], s=40)
    ax.set_xlabel("Two-month kWh")
    ax.set_ylabel("Two-month peak kW")
    ax.set_title("Two-month peak vs energy")
    ax.legend(fontsize=6, loc="best")
    ax.grid(True, alpha=0.3)
    _banner(ax)
    _save(fig, fig_dir, "fig01_peak_vs_energy")
    written.append("fig01_peak_vs_energy")

    # 2–4 threshold vs peak / kWh / cost
    thr_strats = [s for s in ("ALWAYS_GRID_114", "COLD_TRIGGER_10F", "COLD_TRIGGER_20F", "COLD_TRIGGER_30F", "ALWAYS_CONTINUOUS_68_74") if s in by_s]
    xs = [_threshold_tag(s) for s in thr_strats]
    for ykey, ylabel, stem in (
        ("two_month_peak_15min_kw", "Peak kW", "fig02_threshold_vs_peak"),
        ("two_month_kwh", "Total kWh", "fig03_threshold_vs_kwh"),
        ("illustrative_total_cost_usd", "Modeled cost ($)", "fig04_threshold_vs_cost"),
    ):
        fig, ax = plt.subplots(figsize=(7, 4))
        ys = [by_s[s][ykey] for s in thr_strats]
        ax.plot(xs, ys, marker="o")
        for s, x, y in zip(thr_strats, xs, ys):
            ax.annotate(s.replace("COLD_TRIGGER_", "").replace("ALWAYS_", ""), (x, y), fontsize=7)
        ax.set_xlabel("Threshold °F (proxy; continuous=-1, grid114=0)")
        ax.set_ylabel(ylabel)
        ax.set_title(f"Threshold temperature vs {ylabel}")
        ax.grid(True, alpha=0.3)
        _banner(ax)
        _save(fig, fig_dir, stem)
        written.append(stem)

    # 5 daily strategy-selection calendar (use COLD_TRIGGER_20F if present)
    cal_id = "COLD_TRIGGER_20F" if "COLD_TRIGGER_20F" in results else next(iter(WEATHER_POLICY_IDS), None)
    fig, ax = plt.subplots(figsize=(10, 3))
    if cal_id and cal_id in results:
        days = [d["day"] for d in results[cal_id].get("daily") or []]
        modes = [1 if d.get("continuous_day") else 0 for d in results[cal_id].get("daily") or []]
        ax.bar(range(len(modes)), modes, width=1.0, color=["#1f77b4" if m else "#bbbbbb" for m in modes])
        ax.set_title(f"Daily selection calendar — {cal_id} (1=continuous 68/74)")
        ax.set_ylabel("Continuous day")
        ax.set_xlabel("Day index (Dec→Jan)")
    else:
        ax.text(0.5, 0.5, "no trigger calendar", ha="center")
    ax.grid(True, axis="y", alpha=0.3)
    _banner(ax)
    _save(fig, fig_dir, "fig05_daily_selection_calendar")
    written.append("fig05_daily_selection_calendar")

    # 6 coldest week profiles — find week with lowest min daily peak among continuous days or first cold week
    fig, ax = plt.subplots(figsize=(9, 4))
    plotted = False
    for sid in ("ALWAYS_GRID_114", "ALWAYS_CONTINUOUS_68_74", "COLD_TRIGGER_20F"):
        if sid not in results:
            continue
        fac = results[sid]["facility_kw"]
        # use Jan 12–18 as cold-week proxy (indices from Dec 1)
        from eplus_gym.rl.two_month_calendar import scored_days

        days = scored_days()
        try:
            i0 = days.index("2026-01-12") * 96
        except ValueError:
            i0 = 0
        chunk = fac[i0 : i0 + 7 * 96]
        if chunk:
            ax.plot(chunk, label=sid, alpha=0.85)
            plotted = True
    if plotted:
        ax.legend(fontsize=7)
    ax.set_title("Coldest-week facility-kW profiles (2026-01-12 week)")
    ax.set_ylabel("kW")
    ax.grid(True, alpha=0.3)
    _banner(ax)
    _save(fig, fig_dir, "fig06_coldest_week_kw")
    written.append("fig06_coldest_week_kw")

    # 7 Jan 26 profiles
    fig, ax = plt.subplots(figsize=(9, 4))
    from eplus_gym.rl.two_month_calendar import scored_days

    days = scored_days()
    try:
        j0 = days.index("2026-01-26") * 96
    except ValueError:
        j0 = None
    if j0 is not None:
        for sid in ("ALWAYS_GRID_114", "ALWAYS_CONTINUOUS_68_74", "COLD_TRIGGER_20F", "ALWAYS_GRID_42"):
            if sid not in results:
                continue
            ax.plot(results[sid]["facility_kw"][j0 : j0 + 96], label=sid, alpha=0.85)
        ax.legend(fontsize=7)
    ax.set_title("January 26 facility-kW profiles")
    ax.set_ylabel("kW")
    ax.grid(True, alpha=0.3)
    _banner(ax)
    _save(fig, fig_dir, "fig07_jan26_kw")
    written.append("fig07_jan26_kw")

    # 8 monthly energy + demand decomposition
    fig, ax = plt.subplots(figsize=(10, 5))
    wids = [s for s in WEATHER_POLICY_IDS if s in by_s]
    y = np.arange(len(wids))
    e = [by_s[s]["illustrative_energy_charge_usd"] for s in wids]
    d = [
        by_s[s]["illustrative_dec_demand_charge_usd"] + by_s[s]["illustrative_jan_demand_charge_usd"]
        for s in wids
    ]
    ax.barh(y, e, label="Energy")
    ax.barh(y, d, left=e, label="Demand (Dec+Jan)")
    ax.set_yticks(y)
    ax.set_yticklabels([STRATEGY_LABELS.get(s, s) for s in wids], fontsize=7)
    ax.set_xlabel("Illustrative $")
    ax.set_title("Monthly energy and demand-cost decomposition")
    ax.legend()
    ax.grid(True, axis="x", alpha=0.3)
    _banner(ax)
    _save(fig, fig_dir, "fig08_cost_decomposition")
    written.append("fig08_cost_decomposition")

    # 9 comfort/readiness
    fig, ax = plt.subplots(figsize=(9, 4))
    names = [STRATEGY_LABELS.get(s, s)[:20] for s in wids]
    ready = [by_s[s]["ready_checked_school_days"] for s in wids]
    checked = [by_s[s]["checked_school_days"] for s in wids]
    x = np.arange(len(wids))
    ax.bar(x - 0.2, checked, 0.4, label="Checked school days")
    ax.bar(x + 0.2, ready, 0.4, label="Ready checked days")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=25, ha="right", fontsize=7)
    ax.set_title("Comfort / readiness comparison")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    _banner(ax)
    _save(fig, fig_dir, "fig09_readiness")
    written.append("fig09_readiness")

    # 10 compute comparison
    fig, ax = plt.subplots(figsize=(8, 4))
    cats = [r.get("category") for r in compute_rows]
    vals = [max(1e-4, float(r.get("wall_s") or 0)) for r in compute_rows]
    ax.bar(cats, vals)
    ax.set_yscale("log")
    ax.set_ylabel("Seconds (log)")
    ax.set_title("Compute: weather replay vs nightly grid vs RL")
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=20, ha="right", fontsize=7)
    ax.grid(True, axis="y", alpha=0.3)
    _banner(ax)
    _save(fig, fig_dir, "fig10_compute_comparison")
    written.append("fig10_compute_comparison")
    return written
