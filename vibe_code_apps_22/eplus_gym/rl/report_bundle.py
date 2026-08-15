"""Assemble PPO vs random-walk vs heuristic vs descent report (LIVE)."""
from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from eplus_gym.rl import SCREENING_CLAIM, SIMULATOR_REQUIRED
from eplus_gym.rl.compare_baseline import (
    _run_day,
    load_params_from_recommendation,
)
from eplus_gym.rl.day_pool import calendar_day, spec_epw
from eplus_gym.rl.midnight_forecast import forecast_from_epw_replay
from eplus_gym.rl.plots import (
    plot_cumulative_reward,
    plot_peak_vs_kwh_scatter,
    plot_policy_learning_overlay,
    plot_pre8_bars,
    plot_recovery_hist,
    plot_reward_violin,
)
from eplus_gym.rl.policy_pack import DailyPolicyPack
from eplus_gym.rl.spaces import sample_random_params
from eplus_gym.rl.spaces import build_day_observation
from eplus_gym.six_zone_daily_controller import SixZoneDailyController

RunDayFn = Callable[..., Dict[str, Any]]

WINTER_DAYS = [
    "2026-01-20",
    "2026-01-21",
    "2026-01-22",
    "2026-01-23",
    "2026-01-24",
    "2026-01-25",
    "2026-01-26",
]


def load_jsonl_episodes(path: Path, *, policy: str = "PPO") -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        rec["policy"] = policy
        rec["recovery_min"] = rec.get("recovery_min")
        rec.setdefault("artifact_kind", "train_exploration")
        rows.append(rec)
    names = {str(r.get("reward_name")) for r in rows if r.get("reward_name")}
    if len(names) > 1:
        raise ValueError(f"mixed reward_name in {path}: {sorted(names)}")
    return rows


def _row_from_live(payload: Dict[str, Any], *, policy: str, day: str) -> Dict[str, Any]:
    params = payload.get("params") or {}
    return {
        "policy": policy,
        "day": day,
        "reward": payload.get("reward"),
        "daily_kwh": payload.get("daily_kwh"),
        "peak_kw": payload.get("peak_kw"),
        "pre8_violations": payload.get("pre8_violations"),
        "failed": payload.get("failed"),
        "recovery_min": (params or {}).get("recovery_start_minutes_before_occupancy"),
    }


def run_random_walk(
    *,
    site_root: Path,
    epw: Path,
    champion_idf: Path,
    days: Sequence[str],
    n: int,
    run_root: Path,
    seed: int = 1,
    run_day: RunDayFn = _run_day,
    day_pool: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    rng = np.random.default_rng(int(seed))
    rows: List[Dict[str, Any]] = []
    day_list = [str(d) for d in days] or WINTER_DAYS
    for i in range(int(n)):
        day_id = day_list[i % len(day_list)]
        cal = calendar_day(day_id)
        day_epw = spec_epw(day_pool, day_id, epw)
        params = sample_random_params(rng)
        out_dir = Path(run_root) / "report" / "random" / f"{i:04d}_{day_id}"
        wr = out_dir / "worker_result.json"
        if wr.is_file():
            payload = json.loads(wr.read_text(encoding="utf-8"))
        else:
            payload = run_day(
                site_root=site_root,
                epw=day_epw,
                champion_idf=champion_idf,
                day=cal,
                ctrl=SixZoneDailyController(params),
                out_dir=out_dir,
            )
        rows.append(_row_from_live(payload, policy="random_walk", day=day_id))
    return rows


def run_heuristic_week(
    *,
    site_root: Path,
    epw: Path,
    champion_idf: Path,
    days: Sequence[str],
    run_root: Path,
    run_day: RunDayFn = _run_day,
    day_pool: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    pack = DailyPolicyPack(algo="HEURISTIC")
    rows: List[Dict[str, Any]] = []
    for i, day_id in enumerate(days):
        cal = calendar_day(str(day_id))
        d = date.fromisoformat(cal)
        day_epw = spec_epw(day_pool, str(day_id), epw)
        fc = forecast_from_epw_replay(day_epw, d)
        mean_c, min_c, max_c, morn_c, h0, hm10 = fc.features()
        obs = build_day_observation(
            month=d.month,
            dow=d.weekday(),
            doy=int(d.strftime("%j")),
            oat_mean_c=mean_c,
            oat_min_c=min_c,
            oat_max_c=max_c,
            morning_min_c=morn_c,
            hours_below_0c=h0,
            hours_below_m10c=hm10,
        )
        params = pack.predict_params(obs)
        out_dir = Path(run_root) / "report" / "heuristic" / f"{i:04d}_{day_id}"
        wr = out_dir / "worker_result.json"
        if wr.is_file():
            payload = json.loads(wr.read_text(encoding="utf-8"))
        else:
            payload = run_day(
                site_root=site_root,
                epw=day_epw,
                champion_idf=champion_idf,
                day=cal,
                ctrl=SixZoneDailyController(params),
                out_dir=out_dir,
            )
        rows.append(_row_from_live(payload, policy="heuristic", day=str(day_id)))
    return rows


def load_descent_rows(site_root: Path, run_root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    cmp = Path(run_root) / "compare_summary.json"
    # also search sibling bakeoff compares
    cands = [cmp]
    opt = Path(site_root) / "reports" / "eplus_gym" / "rl"
    if opt.is_dir():
        cands.extend(sorted(opt.glob("*/compare_summary.json")))
    for p in cands:
        if not p.is_file():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        for rec in doc.get("rows") or []:
            if rec.get("label") != "coordinate_descent":
                continue
            params = rec.get("params") or {}
            rows.append(
                {
                    "policy": "coordinate_descent",
                    "day": doc.get("day"),
                    "reward": rec.get("reward"),
                    "daily_kwh": rec.get("daily_kwh"),
                    "peak_kw": rec.get("peak_kw"),
                    "pre8_violations": rec.get("pre8_violations"),
                    "failed": rec.get("failed"),
                    "recovery_min": params.get("recovery_start_minutes_before_occupancy"),
                }
            )
        if rows:
            break
    rec_path = None
    opt2 = Path(site_root) / "reports" / "eplus_gym" / "optimization"
    if opt2.is_dir() and not rows:
        for s in sorted(opt2.iterdir(), reverse=True):
            cand = s / "recommendation.json"
            if load_params_from_recommendation(cand) is not None:
                rec_path = cand
                break
        if rec_path:
            # marker only — LIVE already stored in compare if present
            pass
    return rows


def _summarize(df: pd.DataFrame) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for policy, g in df.groupby("policy"):
        if "failed" in g.columns:
            failed = g["failed"].eq(True) | g["failed"].eq("True") | g["failed"].eq(1)
            ok = g.loc[~failed]
        else:
            ok = g
        r = pd.to_numeric(ok["reward"], errors="coerce")
        out[str(policy)] = {
            "n": int(len(ok)),
            "n_logged": int(len(g)),
            "n_failed": int(len(g) - len(ok)),
            "mean_reward": float(r.mean()) if len(r) else float("nan"),
            "median_reward": float(r.median()) if len(r) else float("nan"),
            "mean_peak_kw": float(pd.to_numeric(ok["peak_kw"], errors="coerce").mean()),
            "mean_daily_kwh": float(pd.to_numeric(ok["daily_kwh"], errors="coerce").mean()),
            "mean_pre8_violations": float(
                pd.to_numeric(ok["pre8_violations"], errors="coerce").mean()
            ),
        }
    return out


def write_report_plots(df: pd.DataFrame, plots_dir: Path) -> None:
    if len(df):
        plot_policy_learning_overlay(df, plots_dir)
    if df["policy"].nunique() >= 1 and len(df):
        plot_reward_violin(df, plots_dir)
        plot_cumulative_reward(df, plots_dir)
        plot_peak_vs_kwh_scatter(df, plots_dir)
        plot_pre8_bars(df, plots_dir)
        plot_recovery_hist(df, plots_dir)


def _wipe_repo_copy(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("episodes.csv", "comparison.json"):
        p = dest / name
        if p.is_file():
            p.unlink()
    plot_dest = dest / "plots"
    if plot_dest.is_dir():
        for png in plot_dest.glob("*.png"):
            png.unlink()


def build_report(
    *,
    site_root: Path,
    epw: Path,
    champion_idf: Path,
    run_root: Path,
    days: Sequence[str] | None = None,
    random_timesteps: int = 20,
    heuristic_days: bool = True,
    seed: int = 1,
    repo_copy: Path | None = None,
    run_day: RunDayFn = _run_day,
    dqn_run_root: Path | None = None,
    day_pool: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    run_root = Path(run_root)
    days = list(days or WINTER_DAYS)
    report_dir = run_root / "report"
    plots_dir = report_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl_episodes(run_root / "episodes.jsonl", policy="PPO_train")
    dqn_root = Path(dqn_run_root) if dqn_run_root else (run_root / "dqn")
    rows.extend(load_jsonl_episodes(dqn_root / "episodes.jsonl", policy="DQN_train"))
    rows.extend(
        run_random_walk(
            site_root=site_root,
            epw=epw,
            champion_idf=champion_idf,
            days=days,
            n=int(random_timesteps),
            run_root=run_root,
            seed=seed,
            run_day=run_day,
            day_pool=day_pool,
        )
    )
    if heuristic_days:
        rows.extend(
            run_heuristic_week(
                site_root=site_root,
                epw=epw,
                champion_idf=champion_idf,
                days=days,
                run_root=run_root,
                run_day=run_day,
                day_pool=day_pool,
            )
        )
    if not day_pool:
        rows.extend(load_descent_rows(site_root, run_root))
    df = pd.DataFrame(rows)
    csv_path = report_dir / "episodes.csv"
    df.to_csv(csv_path, index=False)
    write_report_plots(df, plots_dir)
    stats = _summarize(df)
    eligible_names = {"PPO_eval", "DQN_eval", "BAS_incumbent_eval"}
    locked = bool((day_pool or {}).get("split") == "LOCKED_TEST")
    winner = None
    winner_is_held_out = False
    if locked:
        eligible = []
        for k in stats:
            if k not in eligible_names:
                continue
            n_ok = int(stats[k].get("n") or 0)
            mean = stats[k].get("mean_reward")
            try:
                mean_f = float(mean)
            except (TypeError, ValueError):
                continue
            if n_ok > 0 and mean_f == mean_f:
                eligible.append(k)
        if eligible:
            winner = max(eligible, key=lambda k: float(stats[k]["mean_reward"]))
            winner_is_held_out = True
    comparison = {
        "scientific_claim": SCREENING_CLAIM,
        "simulator": SIMULATOR_REQUIRED,
        "policies": stats,
        "winner_mean_reward": winner,
        "winner_is_held_out_eval": winner_is_held_out,
        "train_jsonl_is_not_eval": True,
        "n_rows": int(len(df)),
        "days": list(days),
        "n_days": len(days),
        "random_timesteps": int(random_timesteps),
        "day_pool": day_pool or {},
        "dqn_run_root": str(dqn_root),
        "episodes_csv": str(csv_path),
        "plots_dir": str(plots_dir),
        "note": "PPO_train/DQN_train jsonl is SB3 exploration, not deterministic eval. "
        "Do not crown a winner from train jsonl. Random walk = uniform sample in the daily action box. "
        "DQN Discrete(64) is an ablation vs PPO continuous. Screening only.",
    }
    (report_dir / "comparison.json").write_text(
        json.dumps(comparison, indent=2) + "\n", encoding="utf-8"
    )
    if repo_copy is not None:
        dest = Path(repo_copy)
        _wipe_repo_copy(dest)
        shutil.copy2(csv_path, dest / "episodes.csv")
        shutil.copy2(report_dir / "comparison.json", dest / "comparison.json")
        plot_dest = dest / "plots"
        plot_dest.mkdir(parents=True, exist_ok=True)
        for png in plots_dir.glob("*.png"):
            shutil.copy2(png, plot_dest / png.name)
    return comparison
