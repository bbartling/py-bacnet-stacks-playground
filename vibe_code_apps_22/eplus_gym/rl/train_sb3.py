"""Stable-Baselines3 training / bakeoff for DailySixZoneGymEnv (LIVE only)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np

from eplus_gym.rl import SCREENING_CLAIM, SIMULATOR_REQUIRED
from eplus_gym.rl.daily_env import DailySixZoneGymEnv
from eplus_gym.rl.plots import plot_algo_bakeoff_bars, plot_learning_curve
from eplus_gym.rl.policy_pack import pack_from_sb3_zip


def _new_run_id(prefix: str = "rl") -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def make_env(cfg: Dict[str, Any]) -> DailySixZoneGymEnv:
    return DailySixZoneGymEnv(cfg)


def train_sb3(
    *,
    site_root: Path,
    epw: Path,
    champion_idf: Path,
    days: Sequence[str],
    algo: str,
    timesteps: int,
    run_root: Path,
    seed: int = 0,
    occupied_heating_f: float = 70.0,
    unoccupied_heating_f: float = 65.0,
    day_specs: Sequence[Dict[str, Any]] | None = None,
    reward_name: str = "legacy_reward_v1",
) -> Dict[str, Any]:
    try:
        from stable_baselines3 import DQN, PPO
        from stable_baselines3.common.callbacks import BaseCallback
        from stable_baselines3.common.monitor import Monitor
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Install RL extras: pip install -r requirements-rl.txt"
        ) from exc

    algo_u = str(algo).upper()
    if algo_u not in {"PPO", "DQN"}:
        raise ValueError("algo must be PPO or DQN")
    run_root = Path(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    plots_dir = run_root / "plots"
    models_dir = run_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    cfg = {
        "site_root": str(site_root),
        "epw": str(epw),
        "champion_idf": str(champion_idf),
        "days": list(days),
        "simulator": SIMULATOR_REQUIRED,
        "action_kind": "discrete" if algo_u == "DQN" else "continuous",
        "output_root": str(run_root / "episodes"),
        "seed": int(seed),
        "occupied_heating_f": float(occupied_heating_f),
        "unoccupied_heating_f": float(unoccupied_heating_f),
        "day_specs": list(day_specs or []),
        "reward_name": str(reward_name),
    }
    (run_root / "config.json").write_text(
        json.dumps(
            {
                **cfg,
                "scientific_claim": SCREENING_CLAIM,
                "algo": algo_u,
                "timesteps": int(timesteps),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    env = Monitor(make_env(cfg))
    n_steps = max(2, min(8, int(timesteps)))
    if algo_u == "PPO":
        model = PPO("MlpPolicy", env, verbose=0, seed=int(seed), n_steps=n_steps, batch_size=min(64, n_steps))
    else:
        model = DQN(
            "MlpPolicy",
            env,
            verbose=0,
            seed=int(seed),
            learning_starts=max(1, min(2, int(timesteps))),
            buffer_size=max(64, int(timesteps) * 8),
        )

    episode_log: List[Dict[str, Any]] = []
    rewards: List[float] = []

    class LogCallback(BaseCallback):
        def _on_step(self) -> bool:
            infos = self.locals.get("infos") or []
            rewards_arr = self.locals.get("rewards")
            if rewards_arr is not None:
                for r in np.asarray(rewards_arr).reshape(-1):
                    rewards.append(float(r))
            for info in infos:
                if not isinstance(info, dict):
                    continue
                br = info.get("reward_breakdown") or {}
                episode_log.append(
                    {
                        "reward": br.get("reward"),
                        "day": info.get("day"),
                        "daily_kwh": br.get("daily_kwh"),
                        "peak_kw": br.get("peak_kw"),
                        "pre8_violations": br.get("pre8_violations"),
                        "failed": info.get("failed"),
                        "reward_name": str(reward_name),
                    }
                )
            return True

    model.learn(total_timesteps=max(2, int(timesteps)), callback=LogCallback())
    model_path = models_dir / f"{algo_u.lower()}_final.zip"
    model.save(str(model_path))

    with (run_root / "episodes.jsonl").open("w", encoding="utf-8") as f:
        for row in episode_log:
            f.write(json.dumps(row) + "\n")

    plot_learning_curve(
        rewards or [float("nan")],
        plots_dir,
        title=f"{algo_u} LIVE learning curve",
        filename=f"{algo_u.lower()}_learning_curve.png",
    )
    peaks = [r["peak_kw"] for r in episode_log if isinstance(r.get("peak_kw"), (int, float))]
    kwhs = [r["daily_kwh"] for r in episode_log if isinstance(r.get("daily_kwh"), (int, float))]
    summary = {
        "algo": algo_u,
        "timesteps": int(timesteps),
        "mean_reward": float(np.nanmean(rewards)) if rewards else float("nan"),
        "mean_peak_kw": float(np.nanmean(peaks)) if peaks else float("nan"),
        "mean_daily_kwh": float(np.nanmean(kwhs)) if kwhs else float("nan"),
        "model": str(model_path),
        "n_episodes_logged": len(episode_log),
        "scientific_claim": SCREENING_CLAIM,
        "simulator": SIMULATOR_REQUIRED,
    }
    (run_root / "train_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    pack = pack_from_sb3_zip(
        model_path,
        algo=algo_u,
        meta={"run_root": str(run_root), "days": list(days), "timesteps": int(timesteps)},
    )
    pack_path = models_dir / "daily_policy.pkl"
    pack.save(pack_path)
    summary["policy_pack"] = str(pack_path)
    (run_root / "train_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    env.close()
    return summary


def bakeoff(
    *,
    site_root: Path,
    epw: Path,
    champion_idf: Path,
    days: Sequence[str],
    timesteps: int,
    run_id: str | None = None,
    seed: int = 0,
) -> Dict[str, Any]:
    rid = run_id or _new_run_id("bakeoff")
    root = Path(site_root) / "reports" / "eplus_gym" / "rl" / rid
    root.mkdir(parents=True, exist_ok=True)
    results: Dict[str, Any] = {}
    for algo in ("PPO", "DQN"):
        sub = root / algo.lower()
        results[algo] = train_sb3(
            site_root=site_root,
            epw=epw,
            champion_idf=champion_idf,
            days=days,
            algo=algo,
            timesteps=timesteps,
            run_root=sub,
            seed=seed,
        )
    plot_algo_bakeoff_bars(results, root / "plots")
    winner = max(results.keys(), key=lambda a: float(results[a].get("mean_reward", -1e18)))
    out = {
        "scientific_claim": SCREENING_CLAIM,
        "simulator": SIMULATOR_REQUIRED,
        "run_id": rid,
        "root": str(root),
        "results": results,
        "winner": winner,
        "days": list(days),
        "timesteps_per_algo": int(timesteps),
    }
    (root / "bakeoff_summary.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out
