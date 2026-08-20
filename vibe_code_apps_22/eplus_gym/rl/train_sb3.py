"""Stable-Baselines3 training. Campaign factory is MultiDayDailyEnv (LIVE continuity)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np

from eplus_gym.rl import SCREENING_CLAIM, SIMULATOR_REQUIRED
from eplus_gym.rl.daily_env import DailySixZoneGymEnv
from eplus_gym.rl.multiday_env import MultiDayDailyEnv
from eplus_gym.rl.plots import plot_algo_bakeoff_bars, plot_learning_curve
from eplus_gym.rl.policy_pack import pack_from_sb3_zip
from eplus_gym.rl.sb3_configs import named_config
from eplus_gym.rl.split_manifest import assert_train_fold_only

campaign_env_class = MultiDayDailyEnv


def should_write_policy_pack(cfg: Dict[str, Any] | None) -> bool:
    """Research contracts must not emit a dishonest obs-v2 / dim-19 daily_policy.pkl."""
    body = dict(cfg or {})
    contract = str(body.get("action_contract_version") or "")
    if contract.startswith("research_action_contract"):
        return False
    return bool(body.get("write_policy_pack", True))


def _new_run_id(prefix: str = "rl") -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def make_legacy_daily_env(cfg: Dict[str, Any]) -> DailySixZoneGymEnv:
    """Explicit diagnostic command only. Unreachable from campaign mode."""
    return DailySixZoneGymEnv(cfg)


def make_env(cfg: Dict[str, Any]) -> MultiDayDailyEnv | DailySixZoneGymEnv:
    cfg = dict(cfg or {})
    if cfg.get("legacy_diagnostic"):
        return make_legacy_daily_env(cfg)
    cfg.setdefault("require_live_energyplus", True)
    cfg.setdefault("reward_name", "reward_v2")
    days = list(cfg.get("days") or [])
    if days and not cfg.get("start_day"):
        cfg["start_day"] = str(days[0])
        cfg["n_days"] = len(days)
    if cfg.get("plant") is None and cfg.get("require_live_energyplus"):
        from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant

        cfg["plant"] = EnergyPlusContinuityPlant(
            site_root=Path(cfg["site_root"]),
            epw=Path(cfg["epw"]),
            idf=Path(str(cfg.get("champion_idf") or cfg.get("idf"))),
            output=Path(str(cfg.get("output_root") or ".")) / "continuity",
            days=days or [str(cfg.get("start_day") or "2026-01-12")],
        )
    return MultiDayDailyEnv(cfg)


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
    reward_name: str = "reward_v2",
    sb3_config: str = "smoke",
    extra_env_cfg: Dict[str, Any] | None = None,
    extra_callback: Any | None = None,
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
    assert_train_fold_only(days)
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
    if extra_env_cfg:
        cfg.update(dict(extra_env_cfg))
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
    cfg_named = named_config(sb3_config)
    ppo_kw = dict(cfg_named.get("ppo") or {})
    dqn_kw = dict(cfg_named.get("dqn") or {})
    n_steps = int(ppo_kw.get("n_steps") or max(2, min(8, int(timesteps))))
    if algo_u == "PPO":
        model = PPO(
            "MlpPolicy",
            env,
            verbose=0,
            seed=int(seed),
            n_steps=n_steps,
            batch_size=int(ppo_kw.get("batch_size") or min(64, n_steps)),
        )
    else:
        model = DQN(
            "MlpPolicy",
            env,
            verbose=0,
            seed=int(seed),
            learning_starts=int(dqn_kw.get("learning_starts") or 2),
            buffer_size=int(dqn_kw.get("buffer_size") or max(64, int(timesteps) * 8)),
            exploration_fraction=float(dqn_kw.get("exploration_fraction") or 0.5),
            target_update_interval=int(dqn_kw.get("target_update_interval") or 10),
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
                        "reward": info.get("training_reward", br.get("reward")),
                        "day": info.get("day"),
                        "block_id": info.get("block_id"),
                        "action": info.get("action"),
                        "decoded_schedule_fingerprint": info.get("decoded_schedule_fingerprint"),
                        "daily_kwh": info.get("daily_kwh", br.get("daily_kwh")),
                        "peak_kw": info.get("peak_kw", br.get("peak_kw")),
                        "savings": info.get("savings"),
                        "energy_cost": info.get("energy_cost"),
                        "incremental_demand_cost": info.get("incremental_demand_cost"),
                        "opening_mtd_kw": info.get("opening_mtd_kw"),
                        "closing_mtd_kw": info.get("closing_mtd_kw"),
                        "readiness": info.get("readiness"),
                        "occupied_low_DH": info.get("occupied_low_DH"),
                        "occupied_high_DH": info.get("occupied_high_DH"),
                        "within_day_schedule_movement": info.get("within_day_schedule_movement"),
                        "between_day_action_movement": info.get("between_day_action_movement"),
                        "eplus_quality_ref": info.get("eplus_quality_ref"),
                        "model_sha256": info.get("model_sha256"),
                        "epw_sha256": info.get("epw_sha256"),
                        "trajectory_sha256": info.get("trajectory_sha256"),
                        "pre8_violations": br.get("pre8_violations"),
                        "failed": info.get("failed"),
                        "learnable": info.get("learnable"),
                        "reward_name": str(reward_name),
                    }
                )
            return True

    cb: Any = LogCallback()
    if extra_callback is not None:
        from stable_baselines3.common.callbacks import CallbackList

        cb = CallbackList([LogCallback(), extra_callback])
    model.learn(total_timesteps=max(2, int(cfg_named.get("timesteps") or timesteps)), callback=cb)
    model_path = models_dir / f"{algo_u.lower()}_final.zip"
    model.save(str(model_path))
    if algo_u == "DQN" and (
        str(cfg.get("action_contract_version") or "").startswith("research_action_contract")
        or bool(cfg.get("save_replay_buffer"))
    ):
        model.save_replay_buffer(str(models_dir / "replay_buffer.pkl"))

    with (run_root / "episodes.jsonl").open("w", encoding="utf-8") as f:
        for row in episode_log:
            f.write(json.dumps(row) + "\n")

    plot_learning_curve(
        rewards or [float("nan")],
        plots_dir,
        title=f"{algo_u} LIVE learning curve TRAINING ONLY",
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
        "sb3_config": cfg_named.get("name"),
        "label": "PRELIMINARY_SINGLE_SEED",
        "not_pure_algorithm_comparison": True,
        "winner_rule": "not_mean_training_reward",
    }
    contract = str(cfg.get("action_contract_version") or "")
    write_pack = should_write_policy_pack(cfg)
    if write_pack:
        pack = pack_from_sb3_zip(
            model_path,
            algo=algo_u,
            meta={"run_root": str(run_root), "days": list(days), "timesteps": int(timesteps)},
        )
        pack_path = models_dir / "daily_policy.pkl"
        pack.save(pack_path)
        summary["policy_pack"] = str(pack_path)
    else:
        summary["policy_pack"] = None
        summary["policy_pack_skipped"] = "research_sb3_zip_canonical"
        obs_schema = str(cfg.get("obs_schema") or "v3")
        if obs_schema == "v4":
            from eplus_gym.mega.obs_tariff_v4 import N_OBS_V4, OBS_SCHEMA_V4

            summary["observation_contract"] = OBS_SCHEMA_V4
            summary["observation_dim"] = N_OBS_V4
        else:
            summary["observation_contract"] = "vibe22.obs.v3"
            summary["observation_dim"] = 80
        summary["action_contract_version"] = contract or None
        summary["tariff_mode"] = cfg.get("tariff_mode")
        summary["cooling_action_space"] = False
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
    out = {
        "scientific_claim": SCREENING_CLAIM,
        "simulator": SIMULATOR_REQUIRED,
        "run_id": rid,
        "root": str(root),
        "results": results,
        "winner": None,
        "winner_rule": "not_mean_reward",
        "comparison_note": (
            "PPO vs DQN is not a pure algorithm comparison; action spaces differ. "
            "Single-seed mean reward cannot crown a winner."
        ),
        "label": "PRELIMINARY_SINGLE_SEED",
        "days": list(days),
        "timesteps_per_algo": int(timesteps),
    }
    (root / "bakeoff_summary.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out
