"""GL14 gate charts for W2A enhanced dial models (E20 → SC02 → R02 → A04 ladder).

Run after a dial campaign updates scorecard CSVs under
``SITE_ROOT/plots/analytics/eplus_gl14_vs_peak285/``.  Each enhanced model must
still sit inside the partial-period utility GL14 screen (|NMBE| < 5%, CVRMSE < 15%).

This is not purchased ASHRAE Guideline 14-2023 and does not validate 15-minute DSM.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

NMBE_GATE = 5.0
CVRMSE_GATE = 15.0


def _gl14_pass(nmbe: float, cvrmse: float) -> bool:
    return abs(nmbe) < NMBE_GATE and cvrmse < CVRMSE_GATE


def _load_scorecard(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "gl14" in df.columns:
        df["gl14_pass"] = df["gl14"].astype(str).str.upper().eq("PASS")
    elif "gl14_pass" not in df.columns:
        df["gl14_pass"] = df.apply(
            lambda r: _gl14_pass(float(r["nmbe_pct"]), float(r["cvrmse_pct"])),
            axis=1,
        )
    return df


def _validate_scorecard(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    for _, row in df.iterrows():
        model = str(row.get("model") or row.get("trial_id") or "?")
        nmbe = float(row["nmbe_pct"])
        cv = float(row["cvrmse_pct"])
        computed = _gl14_pass(nmbe, cv)
        if "gl14_pass" in row.index and bool(row["gl14_pass"]) != computed:
            issues.append(
                f"{model}: gl14 label={row['gl14_pass']!r} but "
                f"|NMBE|={abs(nmbe):.2f}% CVRMSE={cv:.2f}% => {computed}"
            )
    return issues


def plot_gl14_gate_scatter(df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    pass_mask = df["gl14_pass"].astype(bool)
    ax.axvspan(-NMBE_GATE, NMBE_GATE, color="#d4edda", alpha=0.35, zorder=0)
    ax.axhspan(0, CVRMSE_GATE, color="#d4edda", alpha=0.35, zorder=0)
    ax.axvline(-NMBE_GATE, color="#c45c26", ls="--", lw=1)
    ax.axvline(NMBE_GATE, color="#c45c26", ls="--", lw=1)
    ax.axhline(CVRMSE_GATE, color="#c45c26", ls="--", lw=1)
    ax.scatter(
        df.loc[~pass_mask, "nmbe_pct"],
        df.loc[~pass_mask, "cvrmse_pct"],
        c="#b33",
        s=90,
        label="GL14 fail",
        zorder=3,
    )
    ax.scatter(
        df.loc[pass_mask, "nmbe_pct"],
        df.loc[pass_mask, "cvrmse_pct"],
        c="#1f4e79",
        s=110,
        label="GL14 pass",
        zorder=4,
    )
    for _, row in df.iterrows():
        label = str(row.get("model") or row.get("trial_id"))
        ax.annotate(
            label,
            (float(row["nmbe_pct"]), float(row["cvrmse_pct"])),
            textcoords="offset points",
            xytext=(4, 4),
            fontsize=9,
        )
    ax.set_xlabel("NMBE (%)")
    ax.set_ylabel("CVRMSE (%)")
    ax.set_title("W2A enhanced models — utility monthly GL14 screen")
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=140)
    plt.close(fig)


def plot_peak_gl14_pareto(df: pd.DataFrame, out: Path) -> None:
    if "jan26_peak_kw" not in df.columns:
        return
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    pass_mask = df["gl14_pass"].astype(bool)
    ax.scatter(
        df.loc[~pass_mask, "jan26_peak_kw"],
        df.loc[~pass_mask, "cvrmse_pct"],
        c="#b33",
        s=90,
        label="GL14 fail",
    )
    ax.scatter(
        df.loc[pass_mask, "jan26_peak_kw"],
        df.loc[pass_mask, "cvrmse_pct"],
        c="#1f4e79",
        s=110,
        label="GL14 pass",
    )
    ax.axhline(CVRMSE_GATE, color="#c45c26", ls="--", lw=1, label="CVRMSE 15% gate")
    ax.axvline(285, color="#888", ls=":", lw=1.2, label="Utility Jan-2026 demand ~285 kW")
    for _, row in df.iterrows():
        label = str(row.get("model") or row.get("trial_id"))
        ax.annotate(
            label,
            (float(row["jan26_peak_kw"]), float(row["cvrmse_pct"])),
            textcoords="offset points",
            xytext=(4, 4),
            fontsize=9,
        )
    ax.set_xlabel("Jan-26 design-day peak (kW)")
    ax.set_ylabel("CVRMSE (%)")
    ax.set_title("Peak vs monthly GL14 — dual-objective dial ladder")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=140)
    plt.close(fig)


def plot_enhanced_dial_trials(trials: pd.DataFrame, out: Path) -> None:
    trials = trials.copy()
    trials.columns = [c.strip().lower() for c in trials.columns]
    if "gl14_pass" not in trials.columns:
        trials["gl14_pass"] = trials.apply(
            lambda r: _gl14_pass(float(r["nmbe_pct"]), float(r["cvrmse_pct"])),
            axis=1,
        )
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    x = np.arange(len(trials))
    colors = ["#1f4e79" if p else "#ccc" for p in trials["gl14_pass"]]
    ax.bar(x, trials["jan26_peak_kw"], color=colors, edgecolor="#333", lw=0.4)
    ax.axhline(285, color="#888", ls=":", lw=1.2, label="~285 kW utility demand")
    ax.set_xticks(x)
    ax.set_xticklabels(trials["trial_id"], rotation=60, ha="right", fontsize=7)
    ax.set_ylabel("Jan-26 peak (kW)")
    ax.set_title("Enhanced dial trials — blue = GL14 pass")
    ax.legend(frameon=False)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=140)
    plt.close(fig)


def build_charts(
    *,
    analytics_dir: Path,
    scorecard_name: str = "a04_dial_scorecard.csv",
    trials_name: str = "enhanced_dial_trials.csv",
) -> dict:
    scorecard_path = analytics_dir / scorecard_name
    if not scorecard_path.is_file():
        raise FileNotFoundError(f"missing scorecard: {scorecard_path}")

    scorecard = _load_scorecard(scorecard_path)
    issues = _validate_scorecard(scorecard)
    if issues:
        raise ValueError("scorecard GL14 labels inconsistent with metrics:\n" + "\n".join(issues))

    out_scatter = analytics_dir / "gl14_gate_scatter_enhanced.png"
    out_pareto = analytics_dir / "gl14_peak_pareto_enhanced.png"
    plot_gl14_gate_scatter(scorecard, out_scatter)
    plot_peak_gl14_pareto(scorecard, out_pareto)

    outputs = [out_scatter.name, out_pareto.name]
    trials_path = analytics_dir / trials_name
    if trials_path.is_file():
        trials = pd.read_csv(trials_path)
        out_trials = analytics_dir / "enhanced_dial_trials_gl14.png"
        plot_enhanced_dial_trials(trials, out_trials)
        outputs.append(out_trials.name)

    payload = {
        "scorecard": scorecard_name,
        "models": [
            {
                "model": str(r.get("model") or r.get("trial_id")),
                "nmbe_pct": float(r["nmbe_pct"]),
                "cvrmse_pct": float(r["cvrmse_pct"]),
                "gl14_pass": bool(r["gl14_pass"]),
                "jan26_peak_kw": float(r["jan26_peak_kw"]) if "jan26_peak_kw" in r else None,
            }
            for _, r in scorecard.iterrows()
        ],
        "outputs": outputs,
        "gates": {"nmbe_abs_pct": NMBE_GATE, "cvrmse_pct": CVRMSE_GATE},
    }
    (analytics_dir / "enhanced_gl14_payload.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--site-root",
        type=Path,
        default=None,
        help="Practice pack root (default: SITE_ROOT env).",
    )
    ap.add_argument(
        "--analytics-subdir",
        default="plots/analytics/eplus_gl14_vs_peak285",
        help="Relative path under site root for dial analytics.",
    )
    args = ap.parse_args()

    site = args.site_root
    if site is None:
        env = os.environ.get("SITE_ROOT") or os.environ.get("LAKESIDE_SITE_ROOT")
        if not env:
            raise SystemExit("set SITE_ROOT or pass --site-root")
        site = Path(env)

    analytics_dir = site / args.analytics_subdir
    payload = build_charts(analytics_dir=analytics_dir)
    print(json.dumps({"outputs": payload["outputs"], "models": len(payload["models"])}, indent=2))


if __name__ == "__main__":
    main()
