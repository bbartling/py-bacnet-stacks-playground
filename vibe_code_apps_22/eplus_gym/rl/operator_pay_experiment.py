"""Isolated operator-pay 2x/3x experiment. Never mixes year2xsyn or legacy rewards."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from eplus_gym.episode import SCREENING_CLAIM
from eplus_gym.objective import BAS_ZONE_COLS
from eplus_gym.rl import SIMULATOR_REQUIRED
from eplus_gym.rl.experiment_ledger import A04_SHA256
from eplus_gym.rl.live_day_worker import run_live_day_subprocess
from eplus_gym.rl.physics_ramp_gate import VERDICT_FAIL
from eplus_gym.rl.reward import (
    INFEASIBLE_TRAIN_REWARD,
    MONEY_ILLUSTRATIVE,
    operator_paycheck,
    score_day,
)
from eplus_gym.rl.spaces import decode_discrete, discrete_n, sample_random_params
from eplus_gym.site_pins import resolve_a04_and_epw, sha256_file
from eplus_gym.six_zone_daily_controller import SixZoneDailyParams, incumbent_lookback_params

ALLOWED_REWARDS = frozenset({"operator_pay_2x_v1", "operator_pay_3x_v1"})
FORBIDDEN_RUN_IDS = frozenset({"year2xsyn"})
SMOKE_DAYS = ("2026-01-25", "2026-01-26", "2026-03-16")
SMOKE_LABEL = "SMOKE_NOT_EVIDENCE"
UNTRAINED_LABEL = "UNTRAINED_POLICY_SMOKE"
PLOT_FOOTER = (
    "EnergyPlus screening experiment; illustrative tariff; not an operational recommendation."
)
SMOKE_WATERMARK = "SMOKE ONLY — NOT EVIDENCE OF LEARNING."
ARMS = ("incumbent", "no_setback", "random_policy", "ppo", "dqn")
EXCLUDED_KINDS = frozenset(
    {
        "year2xsyn",
        "legacy_reward_v1",
        "manual_control_perturbation",
        "jan26_pair",
    }
)
SCREENING_ONLY = "SCREENING_ONLY"


class OperatorPayExperimentError(ValueError):
    """Fail-closed experiment configuration or aggregation error."""


def _git_sha(app_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(app_root),
            text=True,
            timeout=15,
        )
        return out.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def assert_run_id(run_id: str) -> str:
    rid = str(run_id).strip()
    if not rid or rid in FORBIDDEN_RUN_IDS:
        raise OperatorPayExperimentError(f"run_id {rid!r} is forbidden")
    if "year2xsyn" in rid.lower():
        raise OperatorPayExperimentError("run_id must not contain year2xsyn")
    return rid


def assert_reward_name(reward_name: str) -> str:
    name = str(reward_name)
    if name not in ALLOWED_REWARDS:
        raise OperatorPayExperimentError(
            f"reward_name must be operator_pay_2x_v1 or operator_pay_3x_v1, got {name!r}"
        )
    return name


def assert_a04_sha(idf: Path) -> str:
    digest = sha256_file(Path(idf))
    if digest != A04_SHA256:
        raise OperatorPayExperimentError(f"A04 sha {digest} != pin {A04_SHA256}")
    return digest


def load_ramp_gate(app_root: Path) -> dict[str, Any]:
    path = Path(app_root) / "docs" / "audits" / "figures" / "postfix" / "ramp_gate.json"
    if not path.is_file():
        raise OperatorPayExperimentError(f"missing ramp gate {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def full_mode_allowed(ramp: Mapping[str, Any]) -> bool:
    return bool(ramp.get("passed")) and str(ramp.get("verdict")) != VERDICT_FAIL


def refuse_full_campaign(app_root: Path) -> dict[str, Any]:
    from eplus_gym.rl.active_model import ActiveModelError, verify_active_model

    try:
        ramp = load_ramp_gate(app_root)
    except Exception as exc:  # noqa: BLE001
        ramp = {"passed": False, "verdict": VERDICT_FAIL, "error": str(exc)}
    try:
        manifest = verify_active_model(app_root)
    except ActiveModelError as exc:
        extra = ""
        if not full_mode_allowed(ramp):
            extra = "; A04 postfix physics-ramp gate is also not PASS"
        return {
            "allowed": False,
            "ramp": ramp,
            "verdict": str(ramp.get("verdict") or VERDICT_FAIL),
            "reason": f"{exc}{extra}",
        }
    if not full_mode_allowed(ramp):
        return {
            "allowed": False,
            "ramp": ramp,
            "manifest": manifest,
            "verdict": str(ramp.get("verdict") or VERDICT_FAIL),
            "reason": "physics-ramp gate is not PASS; nonempty artifact path is not evidence",
        }
    return {"allowed": True, "ramp": ramp, "manifest": manifest}


def no_setback_params() -> SixZoneDailyParams:
    p = incumbent_lookback_params()
    p.unoccupied_heating_f = 70.0
    p.occupied_heating_f = 70.0
    return p


def arm_params(arm: str, *, seed: int, day_index: int) -> tuple[dict[str, Any], str]:
    name = str(arm)
    if name == "incumbent":
        return incumbent_lookback_params().to_dict(), "fixed_incumbent_70_65"
    if name == "no_setback":
        return no_setback_params().to_dict(), "fixed_no_setback_70_70"
    if name == "random_policy":
        rng = np.random.default_rng(int(seed) + 17 * int(day_index))
        return sample_random_params(rng).to_dict(), "random_policy_iid"
    if name == "ppo":
        rng = np.random.default_rng(int(seed) + 101 + int(day_index))
        return sample_random_params(rng).to_dict(), UNTRAINED_LABEL
    if name == "dqn":
        idx = int((int(seed) + int(day_index)) % discrete_n())
        return decode_discrete(idx).to_dict(), UNTRAINED_LABEL
    raise OperatorPayExperimentError(f"unknown arm {name!r}")


def validate_scored_episode(
    payload: Mapping[str, Any],
    *,
    require_success: bool = True,
) -> None:
    if payload.get("failed"):
        if require_success:
            raise OperatorPayExperimentError(f"failed episode: {payload.get('error')}")
        return
    n_rows = int(payload.get("n_rows") or 0)
    n_all = int(payload.get("n_all_rows") or 0)
    if n_rows != 96:
        raise OperatorPayExperimentError(f"expected 96 scored rows, got {n_rows}")
    if n_all != 192:
        raise OperatorPayExperimentError(f"expected 192 simulated rows, got {n_all}")
    extras = payload.get("extras") or {}
    name = str(extras.get("reward_name") or payload.get("reward_name") or "")
    if name not in ALLOWED_REWARDS:
        raise OperatorPayExperimentError(f"non-operator-pay reward on episode: {name!r}")
    if extras.get("money_mode") not in {MONEY_ILLUSTRATIVE, None}:
        raise OperatorPayExperimentError("money_mode must be ILLUSTRATIVE")
    if extras.get("infeasible"):
        if float(extras.get("display_paycheck_usd") or 0) != 0.0:
            raise OperatorPayExperimentError("readiness fail must display $0")
        if float(payload.get("reward") or extras.get("training_reward") or 0) != float(
            INFEASIBLE_TRAIN_REWARD
        ):
            raise OperatorPayExperimentError("readiness fail train reward must be -10")


def filter_operator_pay_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        rid = str(row.get("run_id") or "")
        kind = str(row.get("kind") or row.get("artifact_kind") or "")
        reward = str(row.get("reward_name") or "")
        if rid in FORBIDDEN_RUN_IDS or "year2xsyn" in rid.lower():
            continue
        if reward == "legacy_reward_v1" or kind in EXCLUDED_KINDS:
            continue
        if reward and reward not in ALLOWED_REWARDS:
            continue
        kept.append(row)
    return kept


def flatten_payload(
    payload: Mapping[str, Any],
    *,
    arm: str,
    run_id: str,
    policy_kind: str,
) -> dict[str, Any]:
    extras = dict(payload.get("extras") or {})
    row = {
        "run_id": run_id,
        "arm": arm,
        "policy_kind": policy_kind,
        "day": payload.get("day"),
        "reward": payload.get("reward"),
        "failed": bool(payload.get("failed")),
        "daily_kwh": payload.get("daily_kwh"),
        "peak_kw": payload.get("peak_kw"),
        "n_rows": payload.get("n_rows"),
        "n_all_rows": payload.get("n_all_rows"),
        "reward_name": extras.get("reward_name") or payload.get("reward_name"),
        "money_mode": extras.get("money_mode") or MONEY_ILLUSTRATIVE,
        "claim": extras.get("claim") or SCREENING_ONLY.lower(),
        "display_paycheck_usd": extras.get("display_paycheck_usd"),
        "training_reward": extras.get("training_reward") or payload.get("reward"),
        "readiness_ok": extras.get("readiness_ok"),
        "infeasible": extras.get("infeasible"),
        "baseline_kwh": extras.get("baseline_kwh"),
        "baseline_peak_kw": extras.get("baseline_peak_kw"),
        "error": payload.get("error"),
        "label": SMOKE_LABEL,
        "advisory_only": True,
        "bacnet_writes": False,
        "simulator": SIMULATOR_REQUIRED,
    }
    return row


def summarize_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    valid = [r for r in rows if not r.get("failed")]
    failed = [r for r in rows if r.get("failed")]
    by_arm: dict[str, Any] = {}
    for arm in ARMS:
        arm_rows = [r for r in rows if r.get("arm") == arm]
        ok = [r for r in arm_rows if not r.get("failed")]
        ready_fail = [r for r in ok if r.get("infeasible")]
        pays = [float(r["display_paycheck_usd"]) for r in ok if r.get("display_paycheck_usd") is not None]
        kwh = [float(r["daily_kwh"]) for r in ok if r.get("daily_kwh") is not None]
        peak = [float(r["peak_kw"]) for r in ok if r.get("peak_kw") is not None]
        by_arm[arm] = {
            "candidate_count": len(arm_rows),
            "failed_eplus_calls": sum(1 for r in arm_rows if r.get("failed")),
            "readiness_failures": len(ready_fail),
            "mean_illustrative_paycheck": float(np.mean(pays)) if pays else None,
            "mean_kwh": float(np.mean(kwh)) if kwh else None,
            "mean_peak_kw": float(np.mean(peak)) if peak else None,
        }
    return {
        "valid_operator_pay_episodes": len(valid),
        "failed_eplus_calls": len(failed),
        "n_rows": len(rows),
        "by_arm": by_arm,
        "ppo_dqn_learned": False,
        "deterministic_validation": False,
        "held_out_evaluation": False,
        "training_campaign": "not_run_ramp_gate_fail",
        "label": SMOKE_LABEL,
    }


def build_manifest(
    *,
    app_root: Path,
    run_id: str,
    reward_name: str,
    mode: str,
    days: list[str],
    seed: int,
    a04_sha: str,
    epw_sha: str,
    ramp: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "vibe22.operator_pay_experiment.v1",
        "scientific_claim": SCREENING_CLAIM,
        "run_id": run_id,
        "reward_name": reward_name,
        "mode": mode,
        "label": SMOKE_LABEL if mode == "smoke" else "FULL_REFUSED_OR_RUN",
        "days": list(days),
        "seed": int(seed),
        "arms": list(ARMS),
        "a04_sha256": a04_sha,
        "a04_sha256_pin": A04_SHA256,
        "epw_sha256": epw_sha,
        "git_sha": _git_sha(app_root),
        "python": sys.version.split()[0],
        "simulator": SIMULATOR_REQUIRED,
        "obs_schema": "vibe22.obs.v2",
        "action_schema": "vibe22.act.v1",
        "ppo_action": "continuous_11d",
        "dqn_action": "discrete_64",
        "reward_constants": {
            "infeasible_train_reward": INFEASIBLE_TRAIN_REWARD,
            "money_mode": MONEY_ILLUSTRATIVE,
            "claim": SCREENING_ONLY,
        },
        "ramp_gate_passed": bool(ramp.get("passed")),
        "ramp_gate_verdict": ramp.get("verdict"),
        "advisory_only": True,
        "bacnet_writes": False,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }


ARM_LABELS = {
    "incumbent": "incumbent",
    "no_setback": "no setback",
    "random_policy": "random policy",
    "ppo": "untrained PPO",
    "dqn": "untrained DQN",
}


def _banner_footer(fig) -> None:
    fig.text(
        0.5,
        0.99,
        SMOKE_WATERMARK,
        ha="center",
        va="top",
        fontsize=10,
        color="#a33",
        fontweight="bold",
    )
    fig.text(0.5, 0.01, PLOT_FOOTER, ha="center", va="bottom", fontsize=8)


def plot_reward_anatomy(plots_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.set_axis_off()
    ax.set_title("Reward anatomy (illustrative operator_pay_2x_v1)")
    ax.text(
        0.04,
        0.88,
        "baseline cost → candidate cost → savings\n"
        "→ readiness gate → display paycheck → training reward\n\n"
        "savings = paired_baseline_cost - candidate_cost\n"
        "display = clip(100 + k * savings, 0, 500)\n"
        "valid + readiness fail: display $0, train reward -10\n"
        "crashed/empty EnergyPlus: FAIL_REWARD -1e6",
        va="top",
        fontsize=11,
        family="monospace",
        transform=ax.transAxes,
    )
    _banner_footer(fig)
    fig.subplots_adjust(top=0.86, bottom=0.10)
    path = Path(plots_dir) / "01-reward-anatomy.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_action_space_schematic(plots_dir: Path) -> Path:
    """Two-column schematic. Never bar-plot 11 dimensions against 64 discrete actions."""
    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(12.5, 6.8))
    for ax in (ax_l, ax_r):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_axis_off()
    ax_l.set_title("PPO — Box(11), continuous")
    ax_l.text(
        0.06,
        0.92,
        "occupied heating setpoint\n"
        "unoccupied heating setpoint\n"
        "occupancy start\n"
        "occupancy end\n"
        "recovery duration\n"
        "six zone-specific setback offsets",
        va="top",
        fontsize=11,
        family="monospace",
        transform=ax_l.transAxes,
    )
    ax_r.set_title("DQN — Discrete(64), coarse ablation")
    ax_r.text(
        0.06,
        0.92,
        "4 unoccupied setpoints\n"
        "4 recovery durations\n"
        "4 shared setback levels\n"
        "4 × 4 × 4 = 64 actions\n\n"
        "Not the same measurement as Box(11).\n"
        "No ranking. Untrained smoke only.",
        va="top",
        fontsize=11,
        family="monospace",
        transform=ax_r.transAxes,
    )
    _banner_footer(fig)
    fig.subplots_adjust(top=0.84, bottom=0.10)
    path = Path(plots_dir) / "02-action-space.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def _rows_frame(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        raise OperatorPayExperimentError("no episode rows for smoke figures")
    if "infeasible" in df.columns:
        df = df.copy()
        df["infeasible"] = df["infeasible"].map(
            lambda v: str(v).strip().lower() in {"true", "1", "yes"} if not isinstance(v, bool) else bool(v)
        )
    if "failed" in df.columns:
        df = df.copy()
        df["failed"] = df["failed"].map(
            lambda v: str(v).strip().lower() in {"true", "1", "yes"} if not isinstance(v, bool) else bool(v)
        )
    return df


def plot_arm_scorecard(plots_dir: Path, rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> Path:
    df = _rows_frame(rows)
    labels = [ARM_LABELS[a] for a in ARMS]
    means_pay: list[float] = []
    means_kwh: list[float] = []
    means_peak: list[float] = []
    n_ready_fail: list[int] = []
    n_ok: list[int] = []
    for arm in ARMS:
        sub = df[df["arm"] == arm]
        ok = sub[~sub["failed"].astype(bool)]
        n_ok.append(int(len(ok)))
        n_ready_fail.append(int(ok["infeasible"].fillna(False).astype(bool).sum()))
        means_pay.append(float(ok["display_paycheck_usd"].astype(float).mean()) if len(ok) else 0.0)
        means_kwh.append(float(ok["daily_kwh"].astype(float).mean()) if len(ok) else 0.0)
        means_peak.append(float(ok["peak_kw"].astype(float).mean()) if len(ok) else 0.0)

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.2))
    axes[0, 0].bar(labels, means_pay, color="#127d8e")
    axes[0, 0].set_ylabel("Mean illustrative paycheck (USD)")
    axes[0, 0].set_title("Illustrative mean paycheck")
    axes[0, 1].bar(labels, means_kwh, color="#4a7c59")
    axes[0, 1].set_ylabel("Mean daily kWh")
    axes[0, 1].set_title("Mean daily energy")
    axes[1, 0].bar(labels, means_peak, color="#d17b2f")
    axes[1, 0].set_ylabel("Mean peak kW")
    axes[1, 0].set_title("Mean peak demand")
    axes[1, 1].bar(labels, n_ready_fail, color="#a33")
    axes[1, 1].set_ylabel("Readiness failures (count)")
    axes[1, 1].set_title("Readiness failures (n=3 valid E+ / arm)")
    for ax, ns in zip(axes.ravel(), (n_ok, n_ok, n_ok, n_ok)):
        ax.tick_params(axis="x", rotation=20)
        ax.set_ylim(bottom=0)
    fig.suptitle("Smoke scorecard — 15 LIVE EnergyPlus episodes; no winner", fontsize=12)
    _banner_footer(fig)
    fig.subplots_adjust(top=0.86, bottom=0.12, hspace=0.42, wspace=0.28)
    path = Path(plots_dir) / "03-arm-scorecard.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_paired_paycheck_by_day(plots_dir: Path, rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> Path:
    df = _rows_frame(rows)
    days = ["2026-01-25", "2026-01-26", "2026-03-16"]
    x = np.arange(len(days))
    width = 0.15
    fig, ax = plt.subplots(figsize=(12.5, 6.4))
    for i, arm in enumerate(ARMS):
        pays: list[float] = []
        fails: list[bool] = []
        for day in days:
            hit = df[(df["arm"] == arm) & (df["day"].astype(str) == day)]
            if hit.empty:
                pays.append(0.0)
                fails.append(False)
                continue
            pays.append(float(hit.iloc[0]["display_paycheck_usd"]))
            fails.append(bool(hit.iloc[0]["infeasible"]))
        offs = x + (i - 2) * width
        bars = ax.bar(offs, pays, width, label=ARM_LABELS[arm])
        for bar, failed in zip(bars, fails):
            if failed:
                bar.set_hatch("//")
                ax.annotate(
                    "readiness fail\n$0 / train −10",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 8),
                    textcoords="offset points",
                    ha="center",
                    fontsize=7,
                    color="#a33",
                )
    ax.set_xticks(x)
    ax.set_xticklabels(["Jan 25", "Jan 26", "Mar 16"])
    ax.set_ylabel("Illustrative paycheck (USD)")
    ax.set_title(
        "Paired per-day paycheck — reused engineering-gate dates, not validation or holdout"
    )
    ax.legend(ncols=3, fontsize=8)
    ax.set_ylim(0, 560)
    _banner_footer(fig)
    fig.subplots_adjust(top=0.82, bottom=0.12)
    path = Path(plots_dir) / "04-paired-paycheck-by-day.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def write_smoke_plots(
    plots_dir: Path,
    summary: Mapping[str, Any] | None = None,
    rows: Sequence[Mapping[str, Any]] | pd.DataFrame | None = None,
) -> list[Path]:
    plots_dir = Path(plots_dir)
    plots_dir.mkdir(parents=True, exist_ok=True)
    _ = summary
    written = [
        plot_reward_anatomy(plots_dir),
        plot_action_space_schematic(plots_dir),
    ]
    if rows is not None and len(rows) > 0:
        written.append(plot_arm_scorecard(plots_dir, rows))
        written.append(plot_paired_paycheck_by_day(plots_dir, rows))
    return written


def regenerate_plots_from_csv(app_root: Path) -> list[Path]:
    csv_path = Path(app_root) / "docs" / "audits" / "figures" / "operator_pay_smoke" / "episode_results.csv"
    if not csv_path.is_file():
        raise OperatorPayExperimentError(f"missing {csv_path}")
    df = pd.read_csv(csv_path)
    plots_dir = Path(app_root) / "plots" / "rl_report_operator_pay"
    return write_smoke_plots(plots_dir, rows=df)


def write_package(
    *,
    dest: Path,
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    plots_dir: Path | None = None,
) -> dict[str, Path]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    man_p = dest / "experiment_manifest.json"
    man_p.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    paths["manifest"] = man_p
    df = pd.DataFrame(rows)
    pq = dest / "episode_results.parquet"
    csv_p = dest / "episode_results.csv"
    if len(df):
        df.to_csv(csv_p, index=False)
        try:
            df.to_parquet(pq, index=False)
            paths["parquet"] = pq
        except ImportError:
            pass
    else:
        pd.DataFrame(columns=["run_id", "arm", "day", "failed"]).to_csv(csv_p, index=False)
    paths["csv"] = csv_p
    sum_p = dest / "summary.json"
    sum_p.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    paths["summary"] = sum_p
    readme = dest / "README.md"
    readme.write_text(
        "\n".join(
            [
                f"# {manifest['run_id']}",
                "",
                f"**{SMOKE_WATERMARK}**",
                "",
                PLOT_FOOTER,
                "",
                "## implementation and simulator smoke passed",
                f"- days: {manifest.get('days')}",
                f"- valid episodes: {summary.get('valid_operator_pay_episodes')}",
                f"- failed E+ calls: {summary.get('failed_eplus_calls')}",
                "",
                "## training campaign status",
                "- **refused / not run** (physics-ramp gate FAIL)",
                "",
                "## deterministic validation status",
                "- **none**",
                "",
                "## held-out evaluation status",
                "- **none**",
                "",
                "## operational recommendation",
                "- **NO_GO / advisory only. No BACnet writes. PPO/DQN did not learn.**",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["readme"] = readme
    if plots_dir is not None:
        write_smoke_plots(plots_dir, summary=summary, rows=rows)
    return paths


RunDay = Callable[..., dict[str, Any]]


def run_smoke_matrix(
    *,
    site_root: Path,
    epw: Path,
    champion_idf: Path,
    run_root: Path,
    days: list[str],
    reward_name: str,
    seed: int,
    run_id: str,
    run_day: RunDay | None = None,
) -> list[dict[str, Any]]:
    worker = run_day or run_live_day_subprocess
    rows: list[dict[str, Any]] = []
    for arm in ARMS:
        for i, day in enumerate(days):
            params, kind = arm_params(arm, seed=seed, day_index=i)
            ep_dir = run_root / "episodes" / arm / str(day)
            payload = worker(
                site_root=site_root,
                epw=epw,
                champion_idf=champion_idf,
                day=str(day),
                params=params,
                ep_dir=ep_dir,
                lookback_days=1,
                reward_name=reward_name,
            )
            try:
                validate_scored_episode(payload, require_success=False)
            except OperatorPayExperimentError as exc:
                payload = dict(payload)
                payload["failed"] = True
                payload["error"] = str(exc)
            row = flatten_payload(payload, arm=arm, run_id=run_id, policy_kind=kind)
            rows.append(row)
    return rows


def run_operator_pay_experiment(
    *,
    app_root: Path,
    site_root: Path,
    run_id: str,
    reward_name: str,
    mode: str,
    simulator: str,
    seed: int = 0,
    run_day: RunDay | None = None,
    skip_eplus: bool = False,
    repo_figures_dir: Path | None = None,
    plots_dir: Path | None = None,
) -> dict[str, Any]:
    app_root = Path(app_root)
    site_root = Path(site_root)
    run_id = assert_run_id(run_id)
    reward_name = assert_reward_name(reward_name)
    if simulator != SIMULATOR_REQUIRED:
        raise OperatorPayExperimentError(f"only {SIMULATOR_REQUIRED}")
    if mode not in {"smoke", "full"}:
        raise OperatorPayExperimentError("mode must be smoke or full")
    ramp = load_ramp_gate(app_root)
    site_out = site_root / "reports" / "eplus_gym" / "rl" / run_id
    repo_out = Path(repo_figures_dir) if repo_figures_dir is not None else (
        app_root / "docs" / "audits" / "figures" / "operator_pay_smoke"
    )
    plot_out = Path(plots_dir) if plots_dir is not None else (
        app_root / "plots" / "rl_report_operator_pay"
    )

    if mode == "full":
        decision = refuse_full_campaign(app_root)
        if not decision["allowed"]:
            stub = {
                "mode": "full",
                "allowed": False,
                "verdict": decision["verdict"],
                "reason": decision["reason"],
                "ppo_dqn_learned": False,
            }
            site_out.mkdir(parents=True, exist_ok=True)
            (site_out / "full_campaign_refused.json").write_text(
                json.dumps(stub, indent=2) + "\n", encoding="utf-8"
            )
            return {"exit_code": 4, **stub}

    idf, epw = resolve_a04_and_epw(site_root)
    a04_sha = assert_a04_sha(idf)
    epw_sha = sha256_file(epw)

    days = list(SMOKE_DAYS)[:3]
    manifest = build_manifest(
        app_root=app_root,
        run_id=run_id,
        reward_name=reward_name,
        mode="smoke",
        days=days,
        seed=seed,
        a04_sha=a04_sha,
        epw_sha=epw_sha,
        ramp=ramp,
    )
    if skip_eplus:
        rows: list[dict[str, Any]] = []
    else:
        rows = run_smoke_matrix(
            site_root=site_root,
            epw=epw,
            champion_idf=idf,
            run_root=site_out,
            days=days,
            reward_name=reward_name,
            seed=seed,
            run_id=run_id,
            run_day=run_day,
        )
    rows = filter_operator_pay_rows(rows)
    summary = summarize_rows(rows)
    summary["ramp_gate_allowed_training"] = False
    summary["operational_recommendation"] = "NO_GO_advisory_only"
    write_package(
        dest=site_out,
        manifest=manifest,
        rows=rows,
        summary=summary,
        plots_dir=None,
    )
    write_package(
        dest=repo_out,
        manifest=manifest,
        rows=rows,
        summary=summary,
        plots_dir=plot_out,
    )
    return {
        "exit_code": 0,
        "site_out": str(site_out),
        "repo_out": str(repo_out),
        "summary": summary,
        "manifest": manifest,
        "n_rows": len(rows),
    }


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Regenerate operator-pay smoke figures from committed CSV")
    p.add_argument("--plots-from-csv", action="store_true")
    args = p.parse_args()
    if args.plots_from_csv:
        root = Path(__file__).resolve().parents[2]
        paths = regenerate_plots_from_csv(root)
        print("\n".join(str(p) for p in paths))
    else:
        raise SystemExit("pass --plots-from-csv (does not run EnergyPlus)")
