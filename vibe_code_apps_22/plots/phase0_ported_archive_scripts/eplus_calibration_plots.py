#!/usr/bin/env python
"""GL14 calibration progress plots (vibe20-style)."""
from __future__ import annotations


import sys
from pathlib import Path as _PathForLakeside

_APP = _PathForLakeside(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
from lakeside.paths import (  # noqa: E402
    BUILDING_LABEL,
    CAMPUS_ID,
    REGION_LABEL,
    app_root,
    clean_data_building_dir,
    eplus_dir,
    packages_dir,
    reports_dir,
    site_root,
    utilities_dir,
)
from lakeside.paths import BUILDING_ID as _LAKESIDE_BUILDING_ID  # noqa: E402
from lakeside.paths import SITE_REF as _LAKESIDE_SITE_REF  # noqa: E402
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = site_root()
LOG = ROOT / "eplus" / "scorecards" / "campaign_log.csv"
PLOTS = ROOT / "eplus" / "plots"
ANALYTICS = ROOT / "plots" / "analytics"
RUNS = ROOT / "eplus" / "runs"

BG, PANEL, INK, MUTED = "#0f1419", "#1a222c", "#e8eef4", "#8b9aab"
ACCENT, WEEKDAY, WEEKEND, GRID = "#5eb1ff", "#3ecf8e", "#f0a04b", "#2a3544"


def style(ax):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=MUTED)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.grid(True, color=GRID, alpha=0.6, lw=0.6)


def plot_gl14_progress(log: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(BG)
    style(ax)
    x = log["iter"].astype(int)
    ax.plot(x, log["nmbe_pct"].abs(), color=ACCENT, lw=2.2, marker="o", label="|NMBE| %")
    ax.plot(x, log["cvrmse_pct"], color=WEEKEND, lw=2.2, marker="s", label="CVRMSE %")
    ax.axhline(5, color=ACCENT, ls="--", lw=1.2, alpha=0.8, label="NMBE gate 5%")
    ax.axhline(15, color=WEEKEND, ls="--", lw=1.2, alpha=0.8, label="CVRMSE gate 15%")
    ax.set_xlabel("Iteration", color=MUTED)
    ax.set_ylabel("Percent", color=MUTED)
    ax.set_title("Lakeside GL14 progress by iteration", color=INK)
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=INK)
    fig.tight_layout()
    out = PLOTS / "gl14_progress_by_iteration.png"
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)
    return out


def _best_iter(log: pd.DataFrame) -> int:
    usable = log.dropna(subset=["gl14_distance"]) if "gl14_distance" in log.columns else log
    if usable.empty:
        return int(log["iter"].iloc[-1])
    if "gl14_distance" in usable.columns:
        return int(usable.loc[usable["gl14_distance"].idxmin(), "iter"])
    return int(usable.loc[usable["cvrmse_pct"].idxmin(), "iter"])


def _load_best_scorecard(log: pd.DataFrame) -> tuple[int, dict] | None:
    best_sc = ROOT / "eplus" / "scorecards" / "best_scorecard.json"
    if best_sc.is_file():
        sc = json.loads(best_sc.read_text(encoding="utf-8"))
        it = sc.get("iter") or ""
        try:
            n = int(str(it).replace("iter_", ""))
        except ValueError:
            n = _best_iter(log)
        return n, sc
    best = _best_iter(log)
    sc_path = RUNS / f"iter_{best:02d}" / "scorecard.json"
    if not sc_path.is_file():
        found = list(RUNS.glob("iter_*/scorecard.json"))
        if not found:
            return None
        sc_path = sorted(found)[-1]
        best = int(sc_path.parent.name.split("_")[1])
    return best, json.loads(sc_path.read_text(encoding="utf-8"))


def _gl14_banner(sc: dict) -> str:
    gl = sc.get("gl14") or {}
    status = str(sc.get("gl14_status") or "unknown").upper()
    nmbe = gl.get("nmbe_pct")
    cv = gl.get("cvrmse_pct")
    gate = "PASS" if status == "PASS" else "FAIL"
    parts = [f"GL14 {gate}"]
    if nmbe is not None:
        parts.append(f"NMBE {nmbe:.1f}% (gate |≤5|)")
    if cv is not None:
        parts.append(f"CVRMSE {cv:.1f}% (gate ≤15)")
    return " · ".join(parts)


def plot_monthly_kwh(log: pd.DataFrame) -> Path | None:
    loaded = _load_best_scorecard(log)
    if not loaded:
        return None
    best, sc = loaded
    months = [m["month"] for m in sc["monthly"]]
    obs = [m["kwh_obs"] for m in sc["monthly"]]
    sim = [m["kwh_sim"] for m in sc["monthly"]]
    fig, ax = plt.subplots(figsize=(11, 5))
    fig.patch.set_facecolor(BG)
    style(ax)
    x = np.arange(len(months))
    w = 0.38
    ax.bar(x - w / 2, obs, width=w, color=WEEKDAY, label="Observed (integrated kWh)")
    ax.bar(x + w / 2, sim, width=w, color=ACCENT, label="Model")
    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=45, ha="right", color=MUTED)
    ax.set_ylabel("kWh", color=MUTED)
    ax.set_title(
        f"Monthly electric fuel kWh — model vs observed (best iter {best})\n{_gl14_banner(sc)}",
        color=INK,
        fontsize=12,
    )
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=INK)
    fig.tight_layout()
    out = PLOTS / "monthly_kwh_model_vs_obs_best.png"
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)
    return out


def plot_monthly_fuel_pct_of_actual(log: pd.DataFrame) -> Path | None:
    """Model kWh as % of actual kWh per month (100% = perfect). GL14 status in title."""
    loaded = _load_best_scorecard(log)
    if not loaded:
        return None
    best, sc = loaded
    months = [m["month"] for m in sc["monthly"]]
    obs = np.array([m["kwh_obs"] for m in sc["monthly"]], dtype=float)
    sim = np.array([m["kwh_sim"] for m in sc["monthly"]], dtype=float)
    pct = np.where(obs > 0, 100.0 * sim / obs, np.nan)
    status = str(sc.get("gl14_status") or "").lower()
    bar_c = WEEKDAY if status == "pass" else WEEKEND

    fig, ax = plt.subplots(figsize=(11, 5.2))
    fig.patch.set_facecolor(BG)
    style(ax)
    x = np.arange(len(months))
    bars = ax.bar(x, pct, color=bar_c, edgecolor=GRID, width=0.72)
    ax.axhline(100, color=ACCENT, ls="--", lw=1.6, label="Perfect match (100%)")
    ax.axhspan(95, 105, color=ACCENT, alpha=0.12, label="±5% band (NMBE-ish)")
    for i, (b, p) in enumerate(zip(bars, pct)):
        if p == p:
            ax.text(
                b.get_x() + b.get_width() / 2,
                b.get_height() + 1.5,
                f"{p:.0f}%",
                ha="center",
                va="bottom",
                color=INK,
                fontsize=8,
            )
    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=45, ha="right", color=MUTED)
    ax.set_ylabel("Model ÷ Actual electric fuel (%)", color=MUTED)
    ax.set_ylim(0, max(120, float(np.nanmax(pct)) * 1.12))
    ax.set_title(
        f"Monthly fuel % — modeled vs actual (best iter {best})\n{_gl14_banner(sc)}",
        color=INK,
        fontsize=12,
    )
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=INK, loc="upper right")
    fig.tight_layout()
    out = PLOTS / "monthly_fuel_pct_model_vs_actual_best.png"
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)
    return out


def plot_monthly_fuel_share_pct(log: pd.DataFrame) -> Path | None:
    """Actual vs model each as % of their own annual total (shape / seasonality)."""
    loaded = _load_best_scorecard(log)
    if not loaded:
        return None
    best, sc = loaded
    months = [m["month"] for m in sc["monthly"]]
    obs = np.array([m["kwh_obs"] for m in sc["monthly"]], dtype=float)
    sim = np.array([m["kwh_sim"] for m in sc["monthly"]], dtype=float)
    obs_pct = 100.0 * obs / obs.sum()
    sim_pct = 100.0 * sim / sim.sum()

    fig, ax = plt.subplots(figsize=(11, 5.2))
    fig.patch.set_facecolor(BG)
    style(ax)
    x = np.arange(len(months))
    w = 0.38
    ax.bar(x - w / 2, obs_pct, width=w, color=WEEKDAY, label="Actual % of annual")
    ax.bar(x + w / 2, sim_pct, width=w, color=ACCENT, label="Model % of annual")
    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=45, ha="right", color=MUTED)
    ax.set_ylabel("% of annual electric fuel", color=MUTED)
    ax.set_title(
        f"Monthly fuel share (%) — actual vs model (best iter {best})\n{_gl14_banner(sc)}",
        color=INK,
        fontsize=12,
    )
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=INK)
    fig.tight_layout()
    out = PLOTS / "monthly_fuel_share_pct_best.png"
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)
    return out


def plot_gl14_status_strip(log: pd.DataFrame) -> Path | None:
    """Per-iteration GL14 pass/fail with NMBE/CVRMSE markers."""
    df = log.dropna(subset=["nmbe_pct", "cvrmse_pct"]).copy()
    if df.empty:
        return None
    df["iter"] = df["iter"].astype(int)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    fig.patch.set_facecolor(BG)
    style(ax)
    for _, row in df.iterrows():
        passed = str(row.get("gl14_status", "")).lower() == "pass"
        c = WEEKDAY if passed else WEEKEND
        ax.scatter(
            row["iter"],
            abs(float(row["nmbe_pct"])),
            c=c,
            s=70,
            marker="o",
            zorder=3,
            edgecolors=INK,
            linewidths=0.4,
        )
        ax.scatter(
            row["iter"],
            float(row["cvrmse_pct"]),
            c=c,
            s=70,
            marker="s",
            zorder=3,
            edgecolors=INK,
            linewidths=0.4,
        )
    ax.plot(df["iter"], df["nmbe_pct"].abs(), color=ACCENT, lw=1.2, alpha=0.7, label="|NMBE| %")
    ax.plot(df["iter"], df["cvrmse_pct"], color=MUTED, lw=1.2, alpha=0.7, label="CVRMSE %")
    ax.axhline(5, color=ACCENT, ls="--", lw=1.1, alpha=0.85)
    ax.axhline(15, color=WEEKEND, ls="--", lw=1.1, alpha=0.85)
    n_pass = int((df["gl14_status"].astype(str).str.lower() == "pass").sum())
    n_fail = len(df) - n_pass
    ax.set_xlabel("Iteration", color=MUTED)
    ax.set_ylabel("Percent", color=MUTED)
    ax.set_title(
        f"GL14 status by iteration — {n_pass} pass / {n_fail} fail "
        f"(green=pass, orange=fail markers)",
        color=INK,
    )
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=INK)
    fig.tight_layout()
    out = PLOTS / "gl14_status_by_iteration.png"
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)
    return out


def plot_monthly_peak(log: pd.DataFrame) -> Path | None:
    loaded = _load_best_scorecard(log)
    if not loaded:
        return None
    best, sc = loaded
    months = [m["month"] for m in sc["monthly"] if m.get("peak_kw_obs") is not None]
    obs = [m["peak_kw_obs"] for m in sc["monthly"] if m.get("peak_kw_obs") is not None]
    if not months:
        return None
    fig, ax = plt.subplots(figsize=(11, 5))
    fig.patch.set_facecolor(BG)
    style(ax)
    ax.bar(months, obs, color=WEEKEND, label="Observed peak kW")
    ax.set_ylabel("kW", color=MUTED)
    ax.set_title(
        f"Monthly peak demand (observed) — iter {best} reference\n{_gl14_banner(sc)}",
        color=INK,
        fontsize=12,
    )
    ax.tick_params(axis="x", rotation=45)
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=INK)
    fig.tight_layout()
    out = PLOTS / "monthly_peak_kw_model_vs_obs_best.png"
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)
    return out


def plot_error_heatmap(log: pd.DataFrame) -> Path | None:
    rows = []
    for sc_path in sorted(RUNS.glob("iter_*/scorecard.json")):
        sc = json.loads(sc_path.read_text(encoding="utf-8"))
        it = int(sc_path.parent.name.split("_")[1])
        for m in sc.get("monthly") or []:
            rows.append({"iter": it, "month": m["month"], "pct_error": m.get("pct_error")})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    pivot = df.pivot(index="iter", columns="month", values="pct_error")
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor(BG)
    style(ax)
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdBu_r", vmin=-50, vmax=50)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, color=MUTED)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right", color=MUTED)
    ax.set_title("Monthly kWh % error heatmap (sim − obs) / obs", color=INK)
    cb = fig.colorbar(im, ax=ax)
    cb.set_label("% error", color=MUTED)
    cb.ax.yaxis.set_tick_params(color=MUTED)
    plt.setp(plt.getp(cb.ax.axes, "yticklabels"), color=MUTED)
    fig.tight_layout()
    out = PLOTS / "monthly_error_heatmap.png"
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)
    return out


def _month_session_tag(month: str) -> str:
    """Rough school-session tag for Lakeside demand window."""
    # month like 2025-08
    mm = int(month.split("-")[1])
    if mm in (7,):
        return "summer break"
    if mm == 6:
        return "late school / summer school"
    if mm == 8:
        return "pre/early school year"
    return "school in session"


def plot_one_chart_per_month(log: pd.DataFrame) -> list[Path]:
    """One PNG per month: actual vs model kWh + % error (warm over-predict highlighted)."""
    loaded = _load_best_scorecard(log)
    if not loaded:
        return []
    best, sc = loaded
    out_dir = PLOTS / "by_month"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    ymax = max(max(m["kwh_obs"], m["kwh_sim"]) for m in sc["monthly"]) * 1.18

    for m in sc["monthly"]:
        err = float(m["pct_error"])
        pct = 100.0 * m["kwh_sim"] / m["kwh_obs"]
        within = abs(err) <= 5.0
        warm_over = err > 15.0  # Aug–Nov / May–Jun class of miss
        tag = _month_session_tag(m["month"])
        status = "PASS ±5%" if within else ("OVER (warm)" if warm_over else "OUTSIDE ±5%")
        accent = WEEKDAY if within else (WEEKEND if warm_over else ACCENT)

        fig, ax = plt.subplots(figsize=(6.2, 4.4))
        fig.patch.set_facecolor(BG)
        style(ax)
        ax.bar(
            [0, 1],
            [m["kwh_obs"], m["kwh_sim"]],
            color=[WEEKDAY, accent],
            width=0.55,
            edgecolor=GRID,
        )
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Actual", "Model"], color=MUTED)
        ax.set_ylabel("kWh", color=MUTED)
        ax.set_ylim(0, ymax)
        ax.set_title(
            f"{m['month']}  ·  {tag}\n"
            f"model {pct:.0f}% of actual  ({err:+.1f}%)  ·  {status}\n"
            f"best iter {best}  ·  {_gl14_banner(sc)}",
            color=INK,
            fontsize=10,
        )
        for i, v in enumerate([m["kwh_obs"], m["kwh_sim"]]):
            ax.text(i, v + ymax * 0.02, f"{v:,.0f}", ha="center", color=INK, fontsize=9)
        fig.tight_layout()
        out = out_dir / f"fuel_{m['month']}_actual_vs_model.png"
        fig.savefig(out, dpi=140, facecolor=BG)
        plt.close(fig)
        paths.append(out)

        # analytics copy
        ad = ANALYTICS / "by_month"
        ad.mkdir(parents=True, exist_ok=True)
        (ad / out.name).write_bytes(out.read_bytes())
    return paths


def plot_monthly_panels_grid(log: pd.DataFrame) -> Path | None:
    """Single figure: one panel per month (actual vs model)."""
    loaded = _load_best_scorecard(log)
    if not loaded:
        return None
    best, sc = loaded
    months = sc["monthly"]
    n = len(months)
    ncols = 4
    nrows = int(np.ceil(n / ncols))
    ymax = max(max(m["kwh_obs"], m["kwh_sim"]) for m in months) * 1.15

    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 3.2 * nrows), squeeze=False)
    fig.patch.set_facecolor(BG)
    fig.suptitle(
        f"Per-month electric fuel — actual vs model (iter {best})\n{_gl14_banner(sc)}",
        color=INK,
        fontsize=13,
    )
    for i, m in enumerate(months):
        r, c = divmod(i, ncols)
        ax = axes[r][c]
        style(ax)
        err = float(m["pct_error"])
        within = abs(err) <= 5.0
        warm_over = err > 15.0
        col = WEEKDAY if within else (WEEKEND if warm_over else ACCENT)
        ax.bar([0, 1], [m["kwh_obs"], m["kwh_sim"]], color=[WEEKDAY, col], width=0.6)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Act", "Mod"], color=MUTED, fontsize=8)
        ax.set_ylim(0, ymax)
        ax.set_title(
            f"{m['month']}  {err:+.0f}%\n{_month_session_tag(m['month'])}",
            color=INK,
            fontsize=9,
        )
        ax.tick_params(axis="y", labelsize=7)
    for j in range(n, nrows * ncols):
        r, c = divmod(j, ncols)
        axes[r][c].set_facecolor(BG)
        axes[r][c].axis("off")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    out = PLOTS / "monthly_panels_actual_vs_model_best.png"
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)
    return out


def main() -> int:
    PLOTS.mkdir(parents=True, exist_ok=True)
    ANALYTICS.mkdir(parents=True, exist_ok=True)
    if not LOG.is_file():
        print(f"missing {LOG}")
        return 1
    log = pd.read_csv(LOG)
    outs: list[Path | None] = [
        plot_gl14_progress(log),
        plot_gl14_status_strip(log),
        plot_monthly_kwh(log),
        plot_monthly_fuel_pct_of_actual(log),
        plot_monthly_fuel_share_pct(log),
        plot_monthly_panels_grid(log),
        plot_monthly_peak(log),
        plot_error_heatmap(log),
    ]
    per_month = plot_one_chart_per_month(log)
    for p in outs:
        if p:
            dest = ANALYTICS / p.name
            dest.write_bytes(p.read_bytes())
            print(f"chart: {p} (+ analytics copy)")
    for p in per_month:
        print(f"chart: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
