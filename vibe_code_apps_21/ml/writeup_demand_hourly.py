"""Generate PhD-ready charts + markdown writeup from tuned demand_hourly_v1 artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _workspace() -> Path:
    if Path("/data/runs").is_dir():
        return Path("/data")
    return Path.home() / "wattlab_workspace"


def _load(pq: Path, card: Path, tuning: Path, summary: Path):
    df = pd.read_parquet(pq)
    card_j = json.loads(card.read_text(encoding="utf-8")) if card.is_file() else {}
    tune_j = json.loads(tuning.read_text(encoding="utf-8")) if tuning.is_file() else {}
    sum_j = json.loads(summary.read_text(encoding="utf-8")) if summary.is_file() else {}
    return df, card_j, tune_j, sum_j


def chart_leaderboard(tune: dict, out: Path) -> None:
    lb = tune.get("leaderboard") or []
    if not lb:
        return
    fams = [e["family"] for e in lb]
    peak = [e["oof_metrics"]["mae_peak_14_16"] for e in lb]
    overall = [e["oof_metrics"]["mae"] for e in lb]
    pers = (tune.get("persistence") or {}).get("mae_peak_14_16")
    x = np.arange(len(fams))
    w = 0.35
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(x - w / 2, overall, w, label="OOF MAE (all hours)", color="#4C78A8")
    ax.bar(x + w / 2, peak, w, label="OOF MAE (peak 14–16)", color="#F58518")
    if pers is not None:
        ax.axhline(pers, color="#E45756", ls="--", lw=1.5, label=f"persistence peak MAE={pers:.2f}")
    ax.set_xticks(x)
    ax.set_xticklabels(fams)
    ax.set_ylabel("kW MAE")
    ax.set_title("Demand surrogate bake-off (GroupKFold by day)")
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def chart_strategy_peak(df: pd.DataFrame, out: Path) -> None:
    g = (
        df[(df["hour_ending"] > 14) & (df["hour_ending"] <= 16)]
        .groupby("strategy_id")["facility_kw"]
        .mean()
        .sort_values()
    )
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(g.index.astype(str), g.values, color="#54A24B")
    ax.set_xlabel("Mean facility kW (hour-ending 15–16)")
    ax.set_title("Physics farm: mean peak-window demand by strategy")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def chart_oat_vs_kw(df: pd.DataFrame, out: Path) -> None:
    base = df[df["strategy_id"] == "baseline"]
    if base.empty:
        return
    fig, ax = plt.subplots(figsize=(6.5, 5))
    hb = ax.hexbin(base["oat_c"], base["facility_kw"], gridsize=30, cmap="viridis", mincnt=1)
    fig.colorbar(hb, ax=ax, label="hour count")
    ax.set_xlabel("Outdoor air temperature (°C)")
    ax.set_ylabel("Facility kW")
    ax.set_title("Baseline: OAT vs hourly facility demand (E+ farm)")
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def chart_example_day(df: pd.DataFrame, out: Path) -> None:
    # Hottest day in farm
    day_max = df.groupby("day")["oat_c"].max().sort_values(ascending=False)
    if day_max.empty:
        return
    hot = day_max.index[0]
    sub = df[df["day"] == hot]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for sid, g in sub.groupby("strategy_id"):
        g = g.sort_values("hour_ending")
        ax.plot(g["hour_ending"], g["facility_kw"], label=sid, lw=1.6)
    ax.axvspan(14, 16, color="#E45756", alpha=0.12, label="DR window 14–16")
    ax.set_xlabel("Hour ending")
    ax.set_ylabel("Facility kW")
    ax.set_title(f"Strategy shapes on hottest farm day ({hot})")
    ax.legend(ncol=2, fontsize=8, frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def write_md(
    path: Path,
    *,
    df: pd.DataFrame,
    card: dict,
    tune: dict,
    summary: dict,
    fig_dir: Path,
) -> None:
    champ = card.get("champion") or tune.get("champion")
    src = card.get("training_source") or summary.get("source")
    n_rows = len(df)
    n_days = df["day"].nunique()
    n_strat = df["strategy_id"].nunique()
    pers = (tune.get("persistence") or {}).get("mae_peak_14_16")
    lb = tune.get("leaderboard") or []
    best = next((e for e in lb if e["family"] == champ), None)
    peak_mae = best["oof_metrics"]["mae_peak_14_16"] if best else None
    overall_mae = best["oof_metrics"]["mae"] if best else None
    params = card.get("best_params") or (best or {}).get("best_params") or {}

    # Strategy deltas vs baseline peak
    peak = df[(df["hour_ending"] > 14) & (df["hour_ending"] <= 16)]
    base_peak = peak[peak["strategy_id"] == "baseline"]["facility_kw"].mean()
    rows_delta = []
    for sid, g in peak.groupby("strategy_id"):
        m = g["facility_kw"].mean()
        rows_delta.append((sid, m, None if base_peak is None or np.isnan(base_peak) else base_peak - m))

    lines = [
        "# Demand-management hourly surrogate — EnergyPlus farm results",
        "",
        f"**Status:** `{card.get('status', 'CANDIDATE')}` · **Source:** `{src}` · **Engine:** `{summary.get('engine') or card.get('engine')}`",
        "",
        "## Abstract",
        "",
        "This note documents a control-oriented **hourly facility electric demand** surrogate "
        "trained on EnergyPlus single-day demand-response (DR) simulations of a G14-calibrated "
        "Building 100 Twin (`geo_b100_dual_ahu_shape_ops11`). The surrogate is intended for "
        "Unity digital-twin scrubbing of HVAC demand strategies (precool / deadband / plant shed), "
        "not for investment-grade M&V.",
        "",
        "## Experimental design",
        "",
        f"- **Physics engine:** native EnergyPlus (`ENERGYPLUS_SIMULATED` rows).",
        f"- **Weather:** AMY EPW stratified calendar days (cool / mild / hot / extreme × weekday/weekend).",
        f"- **Farm size:** {n_days} days · {n_strat} strategies · **{n_rows:,}** hourly rows.",
        "- **Strategies:** baseline, precool_shift, deadband_10f, chiller_off "
        "(+ loadshed / HVAC off / precool+chiller on a subset of days).",
        "- **Features:** OAT, RH, hour, occupancy, DR phase, action knobs, same-day lags "
        "(no future leakage; GroupKFold by **day**).",
        "- **Model search:** Ridge, ElasticNet, RandomForest, HistGradientBoosting via "
        "`RandomizedSearchCV` (GroupKFold).",
        "",
        "## Champion model",
        "",
        f"| Item | Value |",
        f"| --- | --- |",
        f"| Family | `{champ}` |",
        f"| Best params | `{json.dumps(params)}` |",
        f"| OOF MAE (all hours) | **{overall_mae:.2f} kW** |" if overall_mae is not None else "| OOF MAE | — |",
        f"| OOF MAE (peak 14–16) | **{peak_mae:.2f} kW** |" if peak_mae is not None else "| Peak MAE | — |",
        f"| Persistence peak MAE | {pers:.2f} kW |" if pers is not None else "| Persistence | — |",
        f"| Beats persistence (peak) | **{card.get('beat_persistence_peak') or tune.get('beat_persistence_peak')}** |",
        f"| Artifact | `{card.get('artifact')}` |",
        "",
        "## Figures",
        "",
        "### Model bake-off",
        "",
        f"![Leaderboard]({fig_dir.name}/fig_leaderboard.png)",
        "",
        "### Peak demand by strategy (physics)",
        "",
        f"![Strategy peak]({fig_dir.name}/fig_strategy_peak.png)",
        "",
        "### Baseline OAT–demand density",
        "",
        f"![OAT vs kW]({fig_dir.name}/fig_oat_vs_kw.png)",
        "",
        "### Hot-day strategy shapes",
        "",
        f"![Example day]({fig_dir.name}/fig_example_day.png)",
        "",
        "## Peak-window strategy means (physics)",
        "",
        "| Strategy | Mean kW (14–16) | Δ vs baseline (kW) |",
        "| --- | ---: | ---: |",
    ]
    for sid, m, d in sorted(rows_delta, key=lambda t: t[1]):
        d_s = "—" if d is None else f"{d:.1f}"
        lines.append(f"| `{sid}` | {m:.1f} | {d_s} |")

    lines += [
        "",
        "## Leaderboard (out-of-fold)",
        "",
        "| Family | MAE | Peak MAE | Beats persistence |",
        "| --- | ---: | ---: | --- |",
    ]
    for e in lb:
        om = e["oof_metrics"]
        lines.append(
            f"| `{e['family']}` | {om['mae']:.2f} | {om['mae_peak_14_16']:.2f} | "
            f"{e.get('beat_persistence_peak')} |"
        )

    lines += [
        "",
        "## Honesty / limitations",
        "",
        "- Model status remains **CANDIDATE** until validated against measured BAS DR days.",
        "- Twin is Floor×AHU lumped zones (not room-level). Comfort / unmet hours are only partially labeled.",
        "- Screening surrogate for Unity / operator what-if — **not** a bid or M&V claim.",
        "- Synthetic EnergyPlus inherits Twin calibration error (G14 PASS on utility bills ≠ perfect hourly truth).",
        "",
        "## Reproduce",
        "",
        "```bash",
        "python vibe_code_apps_21/tools/dm_hourly_farm.py --engine native --reuse-existing",
        "python vibe_code_apps_21/ml/tune_demand_hourly.py",
        "python vibe_code_apps_21/ml/writeup_demand_hourly.py",
        "```",
        "",
        f"*Generated from farm `{summary.get('parquet')}` · model card `{card.get('model_id')}`.*",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=None)
    ap.add_argument("--models-dir", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    ws = _workspace()
    pq = args.parquet or (ws / "reports" / "dm_hourly_farm" / "dm_hourly_rows.parquet")
    models = args.models_dir or (ws / "models")
    out = args.out_dir or (ws / "reports" / "dm_hourly_farm" / "writeup")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    if not pq.is_file():
        print(f"missing {pq}")
        return 2

    df, card, tune, summary = _load(
        pq,
        models / "demand_hourly_v1_model_card.json",
        models / "demand_hourly_v1_tuning.json",
        pq.parent / "farm_summary.json",
    )
    if summary.get("source") != "ENERGYPLUS_SIMULATED" and card.get("training_source") != "ENERGYPLUS_SIMULATED":
        print("WARNING: writeup expected ENERGYPLUS_SIMULATED physics farm", flush=True)

    chart_leaderboard(tune, figs / "fig_leaderboard.png")
    chart_strategy_peak(df, figs / "fig_strategy_peak.png")
    chart_oat_vs_kw(df, figs / "fig_oat_vs_kw.png")
    chart_example_day(df, figs / "fig_example_day.png")
    md = out / "DEMAND_HOURLY_SURROGATE_RESULTS.md"
    write_md(md, df=df, card=card, tune=tune, summary=summary, fig_dir=figs)
    # Repo copy for report churn (figures under vibe21_agent_spec/figures/dm_hourly/)
    repo_spec = Path(__file__).resolve().parent.parent / "vibe21_agent_spec"
    repo_figs = repo_spec / "figures" / "dm_hourly"
    repo_figs.mkdir(parents=True, exist_ok=True)
    for png in figs.glob("*.png"):
        (repo_figs / png.name).write_bytes(png.read_bytes())
    # Point markdown image links at figures/dm_hourly/
    class _Fig:
        name = "figures/dm_hourly"

    write_md(
        repo_spec / "DEMAND_HOURLY_SURROGATE_RESULTS.md",
        df=df,
        card=card,
        tune=tune,
        summary=summary,
        fig_dir=_Fig(),  # type: ignore[arg-type]
    )
    print(json.dumps({"writeup": str(md), "figures": str(figs), "repo_md": str(repo_spec / "DEMAND_HOURLY_SURROGATE_RESULTS.md"), "n_rows": len(df)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
