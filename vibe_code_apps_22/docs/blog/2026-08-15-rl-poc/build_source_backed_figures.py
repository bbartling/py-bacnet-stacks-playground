"""Build blog figures only from saved post-fix EnergyPlus and real BAS artifacts.

This script does not run EnergyPlus and does not train an RL model. It fails if
the expected source artifacts are missing and labels the paired case as a
manual control perturbation rather than an RL result.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ZONE_COLS = [
    "zone_temp_1F_A_f",
    "zone_temp_1F_B_f",
    "zone_temp_1F_C_f",
    "zone_temp_1F_D_f",
    "zone_temp_2F_A_f",
    "zone_temp_2F_B_f",
]
SP_COLS = [
    "htg_sp_applied_1F_A_f",
    "htg_sp_applied_1F_B_f",
    "htg_sp_applied_1F_C_f",
    "htg_sp_applied_1F_D_f",
    "htg_sp_applied_2F_A_f",
    "htg_sp_applied_2F_B_f",
]


def _require(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _load_pair(vibe22_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    blog_data = Path(__file__).resolve().parent / "data"
    committed_inc = blog_data / "pair_incumbent_trajectory.parquet"
    committed_pert = blog_data / "pair_perturbed_trajectory.parquet"
    root = vibe22_root / "docs" / "audits" / "figures" / "postfix"
    inc_path = committed_inc if committed_inc.is_file() else root / "pair_incumbent" / "trajectory.parquet"
    pert_path = committed_pert if committed_pert.is_file() else root / "pair_perturbed" / "trajectory.parquet"
    incumbent = pd.read_parquet(_require(inc_path))
    perturbed = pd.read_parquet(_require(pert_path))
    for name, frame in (("incumbent", incumbent), ("perturbed", perturbed)):
        missing = set(["facility_kw", "local_step", *ZONE_COLS, *SP_COLS]) - set(frame.columns)
        if missing:
            raise ValueError(f"{name} trajectory missing columns: {sorted(missing)}")
        if len(frame) != 96:
            raise ValueError(f"{name} trajectory must contain 96 scored rows, got {len(frame)}")
    return incumbent, perturbed


def _metrics(frame: pd.DataFrame) -> tuple[float, float]:
    return float(frame["facility_kw"].max()), float(frame["facility_kw"].sum() * 0.25)


def build_pair_figure(inc: pd.DataFrame, pert: pd.DataFrame, output: Path) -> None:
    colors = {"inc": "#127d8e", "pert": "#d17b2f"}
    hours = (inc["local_step"].to_numpy(dtype=float) + 1.0) * 0.25
    inc_peak, inc_kwh = _metrics(inc)
    pert_peak, pert_kwh = _metrics(pert)

    fig = plt.figure(figsize=(15.5, 9), constrained_layout=False, facecolor="#f7fafb")
    gs = fig.add_gridspec(2, 2, width_ratios=[2.25, 1.0])
    ax_kw = fig.add_subplot(gs[0, 0])
    ax_t = fig.add_subplot(gs[1, 0], sharex=ax_kw)
    ax_trade = fig.add_subplot(gs[:, 1])

    ax_kw.plot(hours, inc["facility_kw"], color=colors["inc"], lw=2.5, label="Assumed incumbent 70/65°F")
    ax_kw.plot(hours, pert["facility_kw"], color=colors["pert"], lw=2.5, label="Manual perturbation 68/58°F")
    ax_kw.set_ylabel("Facility demand (kW)")
    ax_kw.set_title("A real post-fix EnergyPlus pair responds to daily controls", loc="left", weight="bold")
    ax_kw.grid(alpha=0.25)
    ax_kw.legend(frameon=False, ncol=2, loc="upper right")

    for frame, color, label in (
        (inc, colors["inc"], "Incumbent zone mean"),
        (pert, colors["pert"], "Perturbed zone mean"),
    ):
        zone = frame[ZONE_COLS].astype(float)
        mean = zone.mean(axis=1).to_numpy()
        ax_t.plot(hours, mean, color=color, lw=2.5, label=label)
        ax_t.fill_between(hours, zone.min(axis=1), zone.max(axis=1), color=color, alpha=0.11)
    ax_t.plot(hours, inc[SP_COLS].astype(float).mean(axis=1), color=colors["inc"], lw=1.2, ls="--", alpha=0.8)
    ax_t.plot(hours, pert[SP_COLS].astype(float).mean(axis=1), color=colors["pert"], lw=1.2, ls="--", alpha=0.8)
    ax_t.axvspan(7, 17, color="#c9d8df", alpha=0.28, label="illustrative occupied window")
    ax_t.set_xlabel("Hour of January 26, 2026")
    ax_t.set_ylabel("Six-zone temperature (°F)")
    ax_t.set_xlim(0, 24)
    ax_t.set_xticks(np.arange(0, 25, 3))
    ax_t.grid(alpha=0.25)
    ax_t.legend(frameon=False, ncol=3, fontsize=9, loc="upper right")

    ax_trade.scatter([inc_kwh], [inc_peak], s=170, color=colors["inc"], zorder=3)
    ax_trade.scatter([pert_kwh], [pert_peak], s=170, color=colors["pert"], zorder=3)
    ax_trade.annotate("assumed\nincumbent", (inc_kwh, inc_peak), xytext=(-86, 8), textcoords="offset points", fontsize=11)
    ax_trade.annotate("manual\nperturbation", (pert_kwh, pert_peak), xytext=(14, -42), textcoords="offset points", fontsize=11)
    ax_trade.annotate("", xy=(pert_kwh, pert_peak), xytext=(inc_kwh, inc_peak), arrowprops=dict(arrowstyle="->", lw=2, color="#536873"))
    ax_trade.set_xlabel("Daily electricity (kWh)")
    ax_trade.set_ylabel("Daily peak (kW)")
    ax_trade.set_title("The tradeoff", weight="bold")
    ax_trade.grid(alpha=0.25)
    ax_trade.margins(x=0.08, y=0.08)
    ax_trade.text(
        0.04,
        0.42,
        f"Δ peak  +{pert_peak-inc_peak:.2f} kW\nΔ energy {pert_kwh-inc_kwh:.2f} kWh\n\nEnergy fell, but peak rose.",
        transform=ax_trade.transAxes,
        fontsize=13,
        va="bottom",
        bbox=dict(boxstyle="round,pad=.55", fc="#fff4df", ec="#d6a64d"),
    )

    fig.subplots_adjust(left=0.065, right=0.985, top=0.88, bottom=0.12, wspace=0.14, hspace=0.18)
    fig.suptitle("Control sensitivity, not RL learning", fontsize=22, weight="bold", y=0.975)
    fig.text(
        0.5,
        0.025,
        "Source: saved A04 post-fix trajectory Parquet files. Five valid gate runs total; valid post-fix RL training episodes = 0.",
        ha="center",
        fontsize=10,
        color="#42535c",
    )
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def build_ramp_figure(inc: pd.DataFrame, pert: pd.DataFrame, real_bas: pd.DataFrame, output: Path) -> None:
    missing = set(ZONE_COLS) - set(real_bas.columns)
    if missing:
        raise ValueError(f"real BAS artifact missing columns: {sorted(missing)}")
    real_delta = real_bas[ZONE_COLS].astype(float).diff().abs().to_numpy().reshape(-1)
    real_delta = real_delta[np.isfinite(real_delta)]
    inc_delta = inc[ZONE_COLS].astype(float).diff().abs().to_numpy().reshape(-1)
    pert_delta = pert[ZONE_COLS].astype(float).diff().abs().to_numpy().reshape(-1)
    inc_max = float(np.nanmax(inc_delta))
    pert_max = float(np.nanmax(pert_delta))
    qs = np.quantile(real_delta, [0.5, 0.95, 0.99, 0.999, 1.0])

    sorted_real = np.sort(real_delta)
    cdf = np.arange(1, len(sorted_real) + 1) / len(sorted_real)
    fig, ax = plt.subplots(figsize=(15.5, 8.5), facecolor="#f7fafb")
    ax.plot(sorted_real, cdf * 100, color="#147d8d", lw=3, label="Real BAS: all six-zone 15-minute changes")
    ax.axvline(inc_max, color="#a65b25", lw=2.5, ls="--", label=f"A04 incumbent max: {inc_max:.2f}°F / 15 min")
    ax.axvline(pert_max, color="#b22d3c", lw=2.5, ls="--", label=f"A04 perturbed max: {pert_max:.2f}°F / 15 min")
    ax.set_xlim(0, max(10.0, pert_max * 1.08))
    ax.set_ylim(0, 100.5)
    ax.set_xlabel("Absolute zone-temperature change (°F per 15 minutes)")
    ax.set_ylabel("Empirical cumulative share of real BAS observations (%)")
    ax.set_title("Monthly calibration does not guarantee control-dynamic realism", fontsize=22, weight="bold", loc="left")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=12, loc="lower right")
    ax.text(
        0.02,
        0.58,
        "Real BAS distribution\n"
        f"median  {qs[0]:.3f}°F\n"
        f"95th       {qs[1]:.3f}°F\n"
        f"99th       {qs[2]:.3f}°F\n"
        f"99.9th    {qs[3]:.3f}°F\n"
        f"maximum {qs[4]:.3f}°F",
        transform=ax.transAxes,
        fontsize=13,
        va="top",
        family="monospace",
        bbox=dict(boxstyle="round,pad=.65", fc="white", ec="#9fb4bd"),
    )
    ax.text(
        0.02,
        0.13,
        "Risk: an optimizer may exploit recovery speed that the real building cannot reproduce.\n"
        "Treat zone-ramp plausibility as a gate before long RL training or BACnet deployment.",
        transform=ax.transAxes,
        fontsize=13,
        va="bottom",
        bbox=dict(boxstyle="round,pad=.65", fc="#fff0f1", ec="#c6535e"),
    )
    fig.text(
        0.5,
        0.015,
        "Sources: real_baseline_15min_v1.parquet and saved A04 post-fix January 26 paired trajectories.",
        ha="center",
        fontsize=10,
        color="#42535c",
    )
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vibe22-root", type=Path, required=True)
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    if args.output_dir is None:
        args.output_dir = Path(__file__).resolve().parent / "figures"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inc, pert = _load_pair(args.vibe22_root)
    real_path = _require(args.site_root / "ml" / "artifacts" / "real_baseline_15min_v1.parquet")
    real_bas = pd.read_parquet(real_path)
    build_pair_figure(inc, pert, args.output_dir / "04-jan26-paired-physics.png")
    build_ramp_figure(inc, pert, real_bas, args.output_dir / "05-zone-ramp-honesty.png")
    print(f"Wrote source-backed figures to {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
