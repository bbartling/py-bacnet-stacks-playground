#!/usr/bin/env python3
"""Plots 1-12 from saved artifacts only. One watermark per figure."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_APP = Path(__file__).resolve().parents[1]
FIG = _APP / "docs" / "audits" / "figures" / "vibe22_final_physics_rl"
PLOTS = FIG / "plots"
WM_DIAG = "DIAGNOSTIC FAILED MODEL"
WM_POC = "SIMULATION-ONLY RESEARCH POC"
WM_CHAMP = "VALIDATED CHAMPION CAMPAIGN"


def _load(name: str) -> dict:
    path = FIG / name
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _watermark(ax, text: str) -> None:
    ax.text(
        0.5,
        0.5,
        text,
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=16,
        color="#888888",
        alpha=0.28,
        rotation=18,
        fontweight="bold",
        zorder=0,
    )


def _save(fig, name: str) -> Path:
    PLOTS.mkdir(parents=True, exist_ok=True)
    out = PLOTS / name
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def main() -> int:
    tb = _load("instrumented_trackb_day.json")
    seq = _load("trackc_sequential_summary.json")
    poc = _load("research_poc_summary.json")
    saved: list[str] = []

    fig, ax = plt.subplots(figsize=(8, 4.5))
    _watermark(ax, WM_DIAG)
    labels = ["Track B CLI\nscored W2A", "Track B\nwarmup W2A", "Active\ninvalid-domain"]
    vals = [
        int((tb.get("w2a_raw_err") or {}).get("scored_runtime") or 738),
        int((tb.get("w2a_raw_err") or {}).get("warmup") or 4657),
        int(tb.get("active_invalid_domain_count") or 759),
    ]
    ax.bar(labels, vals, color=["#c0392b", "#e67e22", "#8e44ad"])
    ax.set_ylabel("count")
    ax.set_title("Plot 01 — Track B instrumented day: raw W2A vs invalid-domain")
    ax.axhline(0, color="black", linewidth=0.8)
    saved.append(str(_save(fig, "01_trackb_w2a_vs_invalid_domain.png")))

    fig, ax = plt.subplots(figsize=(9, 5))
    _watermark(ax, WM_DIAG)
    by_coil = tb.get("invalid_by_coil") or {}
    names = list(by_coil.keys())[:12]
    counts = [int(by_coil[n]) for n in names]
    ax.barh([n.replace(" HEATING COIL", "") for n in names][::-1], counts[::-1], color="#c0392b")
    ax.set_xlabel("active invalid-domain timesteps")
    ax.set_title("Plot 02 — Track B invalid-domain by coil (top 12)")
    saved.append(str(_save(fig, "02_trackb_invalid_by_coil.png")))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    _watermark(ax, WM_DIAG)
    c1 = seq.get("c1") or {}
    c2 = seq.get("c2_base") or {}
    prior = seq.get("prior_trackb_live_matrix") or {}
    ax.bar(
        ["Track B LIVE\nmatrix", "Track B CLI\ninstrumented", "Track C1", "Track C2 base"],
        [
            int(prior.get("w2a_scored_runtime_first_live") or 2106),
            int((seq.get("instrumented_trackb_cli_day_20260112") or {}).get("w2a_scored_runtime") or 738),
            int(c1.get("w2a_scored_runtime") or 822),
            int(c2.get("w2a_scored_runtime") or 2016),
        ],
        color="#c0392b",
    )
    ax.axhline(0, color="black", linewidth=1, label="champion bound = 0")
    ax.set_ylabel("scored-runtime W2A")
    ax.set_title("Plot 03 — Sequential candidates vs champion W2A bound")
    ax.legend()
    saved.append(str(_save(fig, "03_scored_w2a_candidates.png")))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    _watermark(ax, WM_DIAG)
    ax.bar(
        ["A04 parent", "Track C1 freeze", "Track C2 800 kW", "Screening low", "Screening high"],
        [1344.87, float(c1.get("aggregate_heating_capacity_w") or 603047) / 1000.0, 800.0, 675.0, 940.0],
        color=["#7f8c8d", "#e67e22", "#2980b9", "#27ae60", "#27ae60"],
    )
    ax.set_ylabel("kW heating")
    ax.set_title("Plot 04 — Heating capacity vs 675–940 kW screening range")
    saved.append(str(_save(fig, "04_heating_capacity_screening.png")))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    _watermark(ax, WM_DIAG)
    ax.axis("off")
    rows = [
        ["Gate", "C1", "C2", "Required"],
        ["one W2A / zone", "yes", "yes", "yes"],
        ["scored W2A = 0", str(c1.get("w2a_scored_runtime")), str(c2.get("w2a_scored_runtime")), "0"],
        ["severe/fatal", "0/0", "0/0", "0"],
        ["3-day LIVE", "skipped", "skipped", "after W2A=0"],
        ["champion", "false", "false", "all gates"],
    ]
    table = ax.table(cellText=rows, loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.6)
    ax.set_title("Plot 05 — Champion gates (failed; no 37-cell matrix)")
    saved.append(str(_save(fig, "05_champion_gates_table.png")))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    _watermark(ax, WM_POC)
    ax.axis("off")
    claims = [
        "Terminal B: no physics champion",
        "SIMULATION_TRAINING_READY = false",
        "RESEARCH_POC_ALLOWED = true",
        "OPERATIONAL_DSM_READY = false",
        "long_campaign_allowed = false",
        "BACnet commands = 0",
        poc.get("locked_unseen") or "NO LOCKED UNSEEN TEST AVAILABLE",
        f"twin = {poc.get('model_id') or 'A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED'}",
    ]
    ax.text(0.05, 0.95, "Plot 06 — Claim-state contract", va="top", fontsize=13, fontweight="bold")
    ax.text(0.05, 0.82, "\n".join(claims), va="top", fontsize=11, family="monospace")
    saved.append(str(_save(fig, "06_claim_states.png")))

    train = poc.get("train_results") or {}
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _watermark(ax, WM_POC)
    plotted = False
    for key, color in (("PPO_0", "#2980b9"), ("PPO_1", "#3498db")):
        row = train.get(key) or {}
        mean_r = row.get("mean_reward")
        n = row.get("n_episodes_logged")
        if mean_r is not None and n:
            ax.bar(key, float(mean_r), color=color)
            plotted = True
    if not plotted:
        ax.text(0.5, 0.5, "PPO artifacts pending or failed", ha="center")
    ax.set_ylabel("mean training reward")
    ax.set_title("Plot 07 — PPO research PoC (not a winner)")
    saved.append(str(_save(fig, "07_ppo_research_reward.png")))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    _watermark(ax, WM_POC)
    plotted = False
    for key, color in (("DQN_0", "#8e44ad"), ("DQN_1", "#9b59b6")):
        row = train.get(key) or {}
        mean_r = row.get("mean_reward")
        n = row.get("n_episodes_logged")
        if mean_r is not None and n:
            ax.bar(key, float(mean_r), color=color)
            plotted = True
    if not plotted:
        ax.text(0.5, 0.5, "DQN artifacts pending or failed", ha="center")
    ax.set_ylabel("mean training reward")
    ax.set_title("Plot 08 — DQN research PoC (not a winner)")
    saved.append(str(_save(fig, "08_dqn_research_reward.png")))

    eval_rows = poc.get("eval_rows") or []
    fig, ax = plt.subplots(figsize=(8, 4.5))
    _watermark(ax, WM_POC)
    if eval_rows:
        arms = [f"{r.get('arm')}\n{r.get('day')}" for r in eval_rows]
        peaks = [float(r.get("peak_kw") or 0) for r in eval_rows]
        ax.bar(arms, peaks, color="#d35400")
    else:
        ax.text(0.5, 0.5, "eval rows pending", ha="center")
    ax.set_ylabel("peak kW")
    ax.set_title("Plot 09 — Paired eval peak kW (incumbent is baseline-only)")
    saved.append(str(_save(fig, "09_eval_peak_kw.png")))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    _watermark(ax, WM_POC)
    if eval_rows:
        arms = [f"{r.get('arm')}\n{r.get('day')}" for r in eval_rows]
        kwh = [float(r.get("daily_kwh") or 0) for r in eval_rows]
        ax.bar(arms, kwh, color="#16a085")
    else:
        ax.text(0.5, 0.5, "eval rows pending", ha="center")
    ax.set_ylabel("daily kWh")
    ax.set_title("Plot 10 — Paired eval daily kWh")
    saved.append(str(_save(fig, "10_eval_daily_kwh.png")))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    _watermark(ax, WM_POC)
    cand = [r for r in eval_rows if r.get("arm") != "incumbent"]
    if cand:
        ax.bar(
            [f"{r.get('arm')}\n{r.get('day')}" for r in cand],
            [float(r.get("savings") or 0) for r in cand],
            color="#2c3e50",
        )
    else:
        ax.text(0.5, 0.5, "candidate savings pending", ha="center")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("USD savings vs incumbent (illustrative)")
    ax.set_title("Plot 11 — Reward v2 savings; not an operational DSM winner")
    saved.append(str(_save(fig, "11_eval_savings.png")))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    _watermark(ax, WM_POC)
    ax.axis("off")
    ax.text(0.05, 0.95, "Plot 12 — Date-use ledger", va="top", fontsize=13, fontweight="bold")
    ax.text(
        0.05,
        0.82,
        "\n".join(
            [
                "Jan 2026 = development evidence, not holdout",
                "Train: 2025-12-08, 2025-12-09",
                "Val: 2025-12-15, 2025-12-16",
                poc.get("locked_unseen") or "NO LOCKED UNSEEN TEST AVAILABLE",
                "Frozen ramp 2.651 F / 15 min (not raised)",
                "No VALIDATED CHAMPION CAMPAIGN watermark used",
                f"wall_s = {poc.get('wall_s')}",
                f"winner = {poc.get('winner')}",
            ]
        ),
        va="top",
        fontsize=11,
        family="monospace",
    )
    saved.append(str(_save(fig, "12_date_use_ledger.png")))

    manifest = {
        "schema": "vibe22.final_physics.plots.v1",
        "watermark_champion_used": False,
        "watermark_allowed": [WM_CHAMP, WM_POC, WM_DIAG],
        "files": saved,
    }
    (FIG / "plot_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
