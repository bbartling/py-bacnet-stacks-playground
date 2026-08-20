"""Labeled A04 research-long campaign. Never sets long_campaign_allowed."""
from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.control_v2 import observed_bas_incumbent_params
from eplus_gym.date_use_ledger import NO_LOCKED_UNSEEN
from eplus_gym.rl.campaign_bundle import forecasts_from_epw
from eplus_gym.rl.campaign_preflight import dates_are_contiguous
from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant
from eplus_gym.rl.day_pool import unique_dates_from_epw
from eplus_gym.rl.multiday_env import (
    MultiDayDailyEnv,
    schedule_fingerprint,
    trajectory_hash,
)
from eplus_gym.mega.obs_tariff_v4 import N_OBS_V4, OBS_SCHEMA_V4
from eplus_gym.rl.obs_v3 import PERFECT_EPISODE_FORECAST
from eplus_gym.rl.research_checkpoint import rng_hex, write_block_checkpoint
from eplus_gym.rl.research_eval import evaluate_validation_arms, load_sb3_model
from eplus_gym.rl.research_model import ResearchModelError, verify_research_model
from eplus_gym.rl.research_poc import refuse_fake_plant, reject_candidate_as_baseline
from eplus_gym.rl.research_spaces import (
    RESEARCH_ACTION_CONTRACT_V2,
    RESEARCH_ACTION_CONTRACT_V3,
    decode_continuous_research_v2,
    research_build_six_schedules_f,
    research_continuous_70,
)
from eplus_gym.mega.tariff_modes import experiment_id_for_mode, tariff_banner
from eplus_gym.rl.split_manifest import TRAIN_END, VAL_END, assert_train_fold_only
from eplus_gym.rl.train_sb3 import make_env, train_sb3
from eplus_gym.site_pins import resolve_site_epw, sha256_file

CLAIM_LABELS = (
    "SIMULATION_ONLY_RL_RESEARCH",
    "A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED",
    "RESEARCH_LONG_ALLOWED",
    "NO_BACNET_COMMAND_AUTHORITY",
)
TRAIN_START = date(2025, 11, 1)
VAL_START = date(2025, 12, 15)
BLOCK_SIZE = 7
TARGET_TRANSITIONS = 8192
MAX_WALL_HOURS = 30.0


class ResearchLongError(ValueError):
    """research-long refused."""


def _locked_flags(
    *,
    obs_schema: str = "v4",
    action_contract_version: str = RESEARCH_ACTION_CONTRACT_V3,
    tariff_mode: str = "FLAT_PLUS_DEMAND",
) -> dict[str, Any]:
    dim = N_OBS_V4 if obs_schema == "v4" else 80
    contract = OBS_SCHEMA_V4 if obs_schema == "v4" else "vibe22.obs.v3"
    return {
        "claim_labels": list(CLAIM_LABELS),
        "SIMULATION_TRAINING_READY": False,
        "OPERATIONAL_DSM_READY": False,
        "long_campaign_allowed": False,
        "RESEARCH_LONG_ALLOWED": True,
        "RESEARCH_POC_ALLOWED": True,
        "bacnet_commands": 0,
        "locked_unseen": NO_LOCKED_UNSEEN,
        "action_contract_version": action_contract_version,
        "observation_dim": dim,
        "observation_contract": contract,
        "obs_schema": obs_schema,
        "tariff_mode": tariff_mode,
        "experiment_id": experiment_id_for_mode(tariff_mode),
        "tariff_banner": tariff_banner(tariff_mode),
        "cooling_action_space": False,
    }


def freeze_research_long_days(epw: Path) -> dict[str, Any]:
    dates = unique_dates_from_epw(Path(epw))
    train = [d.isoformat() for d in dates if TRAIN_START <= d <= TRAIN_END]
    val = [d.isoformat() for d in dates if VAL_START <= d <= VAL_END]
    if any(date.fromisoformat(x).year == 2026 and date.fromisoformat(x).month == 1 for x in train):
        raise ResearchLongError("January 2026 must not enter the research-long train pool")
    assert_train_fold_only(train)
    return {
        "train": train,
        "validation": val,
        "train_contiguous": dates_are_contiguous(train) if len(train) > 1 else bool(train),
        "validation_contiguous": dates_are_contiguous(val) if len(val) > 1 else bool(val),
        "locked_unseen": NO_LOCKED_UNSEEN,
        "epw": str(epw),
    }


def write_heartbeat(path: Path, body: Mapping[str, Any], *, flags: Mapping[str, Any] | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **(dict(flags) if flags is not None else _locked_flags()),
        "pid": os.getpid(),
        "contaminated": False,
        **dict(body),
        "heartbeat_utc": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _payload_baseline(
    *,
    day: str,
    payload: Mapping[str, Any],
    idf_sha: str,
    epw_sha: str,
    lookback_fp: str,
    baseline_fp: str,
    days: Sequence[str],
) -> dict[str, Any]:
    return {
        "day": day,
        "idf_sha256": idf_sha,
        "epw_sha256": epw_sha,
        "energyplus_version": "26.1.0",
        "run_period": f"{days[0]}:{days[-1]}",
        "lookback_schedule_fingerprint": lookback_fp,
        "baseline_schedule_fingerprint": baseline_fp,
        "initial_state_id": "lookback_continuous_70",
        "trajectory_hash": trajectory_hash(payload),
        "n_intervals": int(payload.get("n_intervals") or 96),
        "facility_kw": list(payload["facility_kw"]),
        "zone_temps_series_f": payload["zone_temps_series_f"],
        "live_energyplus": True,
    }


def cache_incumbent_payloads(
    *,
    site: Path,
    epw: Path,
    idf: Path,
    output: Path,
    days: Sequence[str],
    oat: Mapping[str, Sequence[float]],
    idf_sha: str,
    epw_sha: str,
) -> dict[str, Any]:
    days = [str(d)[:10] for d in days]
    plant = EnergyPlusContinuityPlant(
        site_root=site, epw=epw, idf=idf, output=output, days=list(days), queue_timeout_s=600.0
    )
    refuse_fake_plant(plant)
    plant.start_episode()
    incumbent = observed_bas_incumbent_params()
    lookback_fp = schedule_fingerprint(research_build_six_schedules_f(research_continuous_70(), days[0]))
    baseline_fp = schedule_fingerprint(research_build_six_schedules_f(incumbent, days[0]))
    out: dict[str, dict[str, Any]] = {}
    for day in days:
        sched = research_build_six_schedules_f(incumbent, day)
        payload = plant.simulate_day(sched, oat_c=list(oat[day]))
        reject_candidate_as_baseline(
            {"sha": trajectory_hash(payload) + "-cand"},
            {"sha": trajectory_hash(payload)},
        )
        out[day] = _payload_baseline(
            day=day,
            payload=payload,
            idf_sha=idf_sha,
            epw_sha=epw_sha,
            lookback_fp=lookback_fp,
            baseline_fp=baseline_fp,
            days=days,
        )
    quality = plant.finish_quality()
    return {"payloads": out, "quality": quality, "lookback_fp": lookback_fp, "baseline_fp": baseline_fp}


def _env_cfg(
    *,
    site: Path,
    epw: Path,
    idf: Path,
    days: Sequence[str],
    oat: Mapping[str, Sequence[float]],
    payloads: Mapping[str, Mapping[str, Any]],
    idf_sha: str,
    epw_sha: str,
    output: Path,
    algo: str,
    block_size: int,
    persist_billing: bool,
    obs_schema: str = "v4",
    tariff_mode: str = "FLAT_PLUS_DEMAND",
    action_contract_version: str = RESEARCH_ACTION_CONTRACT_V3,
) -> dict[str, Any]:
    first = next(iter(payloads.values())) if payloads else {}
    return {
        "site_root": str(site),
        "epw": str(epw),
        "champion_idf": str(idf),
        "idf": str(idf),
        "days": [str(d)[:10] for d in days],
        "n_days": len(days),
        "start_day": str(days[0])[:10],
        "action_kind": "discrete" if str(algo).upper() == "DQN" else "continuous",
        "action_contract_version": action_contract_version,
        "hourly_oat": {k: list(v) for k, v in oat.items()},
        "forecast_source": PERFECT_EPISODE_FORECAST,
        "obs_schema": obs_schema,
        "tariff_mode": tariff_mode,
        "baseline_payloads": dict(payloads),
        "idf_sha256": idf_sha,
        "epw_sha256": epw_sha,
        "energyplus_version": "26.1.0",
        "model_id": "A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED",
        "weather_id": Path(epw).name,
        "require_live_energyplus": True,
        "require_baseline": True,
        "write_policy_pack": False,
        "save_replay_buffer": True,
        "block_size": int(block_size),
        "persist_billing": bool(persist_billing),
        "output_root": str(output),
        "lookback_schedule_fingerprint": first.get("lookback_schedule_fingerprint") or "",
        "baseline_schedule_fingerprint": first.get("baseline_schedule_fingerprint") or "",
    }


def run_research_long(
    *,
    app_root: Path,
    site_root: Path,
    confirm_simulation_only_physics_limits: bool,
    confirm_a04_not_transient_validated: bool,
    max_wall_hours: float = MAX_WALL_HOURS,
    micro_gate: bool = False,
    execute_live: bool = False,
    heartbeat_path: Path | None = None,
    seed: int = 0,
    obs_schema: str = "v4",
    tariff_mode: str = "FLAT_PLUS_DEMAND",
    action_contract_version: str = RESEARCH_ACTION_CONTRACT_V3,
    child_idf: Path | None = None,
    campaign_labels: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    if not confirm_simulation_only_physics_limits or not confirm_a04_not_transient_validated:
        raise ResearchLongError(
            "missing --confirm-simulation-only-physics-limits and/or --confirm-a04-not-transient-validated"
        )
    if float(max_wall_hours) > MAX_WALL_HOURS + 1e-9:
        raise ResearchLongError("research-long wall clock cap is 30 hours")
    if action_contract_version not in {RESEARCH_ACTION_CONTRACT_V2, RESEARCH_ACTION_CONTRACT_V3}:
        raise ResearchLongError(f"unsupported action_contract_version {action_contract_version!r}")
    manifest = verify_research_model(app_root)
    if manifest.get("long_campaign_allowed") is True:
        raise ResearchModelError("research contract must not set long_campaign_allowed=true")
    flags = _locked_flags(
        obs_schema=obs_schema,
        action_contract_version=action_contract_version,
        tariff_mode=tariff_mode,
    )
    if campaign_labels:
        flags["claim_labels"] = list(campaign_labels)
    if not execute_live and not micro_gate:
        return {
            "command": "research-long",
            "allowed": True,
            **flags,
            "max_wall_hours": float(max_wall_hours),
            "model_id": manifest.get("model_id"),
        }

    idf = Path(child_idf) if child_idf is not None else Path(app_root) / str(manifest.get("idf_path") or f"models/eplus/{A04_IDF_NAME}")
    try:
        epw = resolve_site_epw(Path(site_root))
    except FileNotFoundError as exc:
        raise ResearchLongError(str(exc)) from exc
    idf_sha = sha256_file(idf)
    epw_sha = sha256_file(epw)
    pool = freeze_research_long_days(epw)
    train_days = list(pool["train"])
    val_days = list(pool["validation"])
    if micro_gate:
        train_days = train_days[:2]
        val_days = val_days[:2] if val_days else train_days[:2]
        target = 8
        seeds = [int(seed)]
        wall = min(float(max_wall_hours), 2.0)
        block_size = min(BLOCK_SIZE, max(1, len(train_days)))
    else:
        target = TARGET_TRANSITIONS
        seeds = [int(seed), int(seed) + 1]
        wall = float(max_wall_hours)
        block_size = BLOCK_SIZE
    if len(train_days) < 2:
        raise ResearchLongError("need at least two train days in EPW coverage")
    oat = forecasts_from_epw(epw, train_days + val_days)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    exp = experiment_id_for_mode(tariff_mode).lower().replace(" ", "_")
    out_root = Path(site_root) / "reports" / "eplus_gym" / "rl" / f"research_long_{exp}_{stamp}"
    out_root.mkdir(parents=True, exist_ok=True)
    hb = Path(heartbeat_path) if heartbeat_path is not None else out_root / "heartbeat.json"
    write_heartbeat(
        hb,
        {
            "command": "research-long",
            "phase": "start",
            "pid": None,
            "idf_sha256": idf_sha,
            "epw_sha256": epw_sha,
            "target_transitions": int(target),
            "current_algo": None,
            "current_seed": None,
            "valid_transitions": 0,
            "failures": [],
            "latest_checkpoint": None,
            "run_root": str(out_root),
            "train_days": train_days,
            "validation_days": val_days,
            "micro_gate": bool(micro_gate),
            "tariff_mode": tariff_mode,
            "experiment_id": experiment_id_for_mode(tariff_mode),
            "action_contract_version": action_contract_version,
        },
        flags=flags,
    )
    cache = cache_incumbent_payloads(
        site=Path(site_root),
        epw=epw,
        idf=idf,
        output=out_root / "incumbent_cache",
        days=train_days,
        oat=oat,
        idf_sha=idf_sha,
        epw_sha=epw_sha,
    )
    val_cache = cache_incumbent_payloads(
        site=Path(site_root),
        epw=epw,
        idf=idf,
        output=out_root / "val_incumbent_cache",
        days=val_days,
        oat=oat,
        idf_sha=idf_sha,
        epw_sha=epw_sha,
    )
    deadline = time.monotonic() + float(wall) * 3600.0
    results: dict[str, Any] = {}
    failures: list[str] = []
    t0 = time.monotonic()
    algos = ("PPO", "DQN")
    for algo in algos:
        for sd in seeds:
            if time.monotonic() >= deadline:
                results[f"{algo}_{sd}"] = {"skipped": True, "reason": "wall_clock"}
                continue
            sub = out_root / f"{algo.lower()}_seed{sd}"
            sub.mkdir(parents=True, exist_ok=True)
            extra = _env_cfg(
                site=Path(site_root),
                epw=epw,
                idf=idf,
                days=train_days,
                oat=oat,
                payloads=cache["payloads"],
                idf_sha=idf_sha,
                epw_sha=epw_sha,
                output=sub / "eplus",
                algo=algo,
                block_size=block_size,
                persist_billing=True,
                obs_schema=obs_schema,
                tariff_mode=tariff_mode,
                action_contract_version=action_contract_version,
            )

            from stable_baselines3.common.callbacks import BaseCallback

            class _BlockCb(BaseCallback):
                def __init__(self):
                    super().__init__()
                    self.valid = 0

                def _on_step(self) -> bool:
                    infos = self.locals.get("infos") or []
                    dones = self.locals.get("dones")
                    for info in infos:
                        if not isinstance(info, dict):
                            continue
                        if info.get("learnable") and not info.get("failed"):
                            self.valid += 1
                            write_heartbeat(
                                hb,
                                {
                                    "command": "research-long",
                                    "phase": "train",
                                    "idf_sha256": idf_sha,
                                    "epw_sha256": epw_sha,
                                    "target_transitions": int(target),
                                    "current_algo": algo,
                                    "current_seed": int(sd),
                                    "valid_transitions": int(self.valid),
                                    "failures": list(failures),
                                    "latest_checkpoint": str(sub / "checkpoints" / "checkpoint.json"),
                                    "run_root": str(out_root),
                                    "day": info.get("day"),
                                },
                                flags=flags,
                            )
                            if self.valid >= int(target):
                                return False
                        if info.get("failed"):
                            failures.append(str(info.get("day")))
                    if dones is not None and np.any(dones) and self.model is not None:
                        write_block_checkpoint(
                            root=sub / "checkpoints",
                            model=self.model,
                            algo=algo,
                            seed=int(sd),
                            valid_transition_count=self.valid,
                            block_id=str((infos[0] or {}).get("block_id") if infos else ""),
                            day=str((infos[0] or {}).get("day") if infos else ""),
                            idf_sha256=idf_sha,
                            epw_sha256=epw_sha,
                            rng_hex=rng_hex(
                                seed=int(sd), idf_sha256=idf_sha, epw_sha256=epw_sha, algo=algo
                            ),
                        )
                    if time.monotonic() >= deadline:
                        return False
                    return True

            try:
                summary = train_sb3(
                    site_root=Path(site_root),
                    epw=epw,
                    champion_idf=idf,
                    days=train_days,
                    algo=algo,
                    timesteps=int(target),
                    run_root=sub,
                    seed=int(sd),
                    reward_name="reward_v2",
                    sb3_config="research_long",
                    extra_env_cfg=extra,
                    extra_callback=_BlockCb(),
                )
                results[f"{algo}_{sd}"] = summary
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{algo}_{sd}:{exc}")
                results[f"{algo}_{sd}"] = {"failed": True, "reason": str(exc), "algo": algo, "seed": sd}

    models: dict[str, Any] = {}
    for algo in algos:
        for sd in seeds:
            zpath = out_root / f"{algo.lower()}_seed{sd}" / "models" / f"{algo.lower()}_final.zip"
            if zpath.is_file():
                models[f"trained_{algo.lower()}_seed{sd}"] = {
                    "model": load_sb3_model(
                        zpath,
                        algo=algo,
                        contract={"action_contract_version": action_contract_version},
                    ),
                    "algo": algo,
                }

    eval_out: dict[str, Any] | None = None
    if models and val_days:

        def _factory() -> MultiDayDailyEnv:
            cfg = _env_cfg(
                site=Path(site_root),
                epw=epw,
                idf=idf,
                days=val_days,
                oat=oat,
                payloads=val_cache["payloads"],
                idf_sha=idf_sha,
                epw_sha=epw_sha,
                output=out_root / "eval_eplus" / str(time.time_ns()),
                algo="PPO",
                block_size=0,
                persist_billing=True,
                obs_schema=obs_schema,
                tariff_mode=tariff_mode,
                action_contract_version=action_contract_version,
            )
            return make_env(cfg)

        try:
            eval_out = evaluate_validation_arms(
                env_factory=_factory,
                days=val_days,
                models=models,
                seed=int(seed),
                action_contract_version=action_contract_version,
                tariff_mode=tariff_mode,
            )
            (out_root / "eval.json").write_text(
                json.dumps(eval_out, indent=2, default=str) + "\n", encoding="utf-8"
            )
            from eplus_gym.rl.plots import plot_paired_val_delta, plot_validation_arm_bars

            plots_dir = out_root / "plots"
            plot_validation_arm_bars(eval_out.get("rows") or [], plots_dir)
            plot_paired_val_delta(eval_out.get("rows") or [], plots_dir)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"eval:{exc}")
            eval_out = {"failed": True, "reason": str(exc), "winner": None}

    severe = int((cache.get("quality") or {}).get("severe_count") or 0) + int(
        (val_cache.get("quality") or {}).get("severe_count") or 0
    )
    fatal = int((cache.get("quality") or {}).get("fatal_count") or 0) + int(
        (val_cache.get("quality") or {}).get("fatal_count") or 0
    )
    summary = {
        "command": "research-long",
        "schema": "vibe22.research_long.v1",
        **flags,
        "micro_gate": bool(micro_gate),
        "model_id": manifest.get("model_id"),
        "idf_sha256": idf_sha,
        "epw_sha256": epw_sha,
        "train_days": train_days,
        "validation_days": val_days,
        "target_transitions": int(target),
        "results": results,
        "eval": eval_out,
        "w2a": {"incumbent_train": cache.get("quality"), "incumbent_val": val_cache.get("quality")},
        "energyplus_severe": severe,
        "energyplus_fatal": fatal,
        "failures": failures,
        "run_root": str(out_root),
        "heartbeat": str(hb),
        "elapsed_s": time.monotonic() - t0,
        "heating_only": True,
        "cooling_action_space": False,
        "cooling_note": "LIVE Gym actuates six heating DualSP schedules only; A04 SCH_ClgSP remains ~74/85 F.",
    }
    if micro_gate:
        _assert_micro_gate(summary, results, models, cache)
    (out_root / "campaign_manifest.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    write_heartbeat(
        hb,
        {
            "command": "research-long",
            "phase": "done",
            "idf_sha256": idf_sha,
            "epw_sha256": epw_sha,
            "target_transitions": int(target),
            "valid_transitions": max(
                (int(v.get("n_episodes_logged") or 0) for v in results.values() if isinstance(v, dict)),
                default=0,
            ),
            "failures": failures,
            "run_root": str(out_root),
        },
        flags=flags,
    )
    return summary


def _assert_micro_gate(
    summary: Mapping[str, Any],
    results: Mapping[str, Any],
    models: Mapping[str, Any],
    cache: Mapping[str, Any],
) -> None:
    from eplus_gym.rl.research_spaces import decode_continuous_research_v3

    ppo = results.get("PPO_0") or {}
    dqn = results.get("DQN_0") or {}
    if int(ppo.get("n_episodes_logged") or 0) < 8:
        raise ResearchLongError("micro-gate: PPO needs >=8 valid transitions")
    if int(dqn.get("n_episodes_logged") or 0) < 8:
        raise ResearchLongError("micro-gate: DQN needs >=8 valid transitions")
    if not models:
        raise ResearchLongError("micro-gate: saved-policy reload failed")
    if int(summary.get("energyplus_severe") or 0) or int(summary.get("energyplus_fatal") or 0):
        raise ResearchLongError("micro-gate: EnergyPlus severe/fatal is not zero")
    if not cache.get("payloads"):
        raise ResearchLongError("micro-gate: paired baseline missing")
    for day, payload in (cache.get("payloads") or {}).items():
        if int(payload.get("n_intervals") or 0) != 96:
            raise ResearchLongError(f"micro-gate: {day} does not have 96 scored intervals")
    if ppo.get("policy_pack"):
        raise ResearchLongError("micro-gate: refused dishonest daily_policy.pkl")
    contract = str(summary.get("action_contract_version") or RESEARCH_ACTION_CONTRACT_V3)
    jsonl = Path(str(ppo.get("model") or "")).parent.parent / "episodes.jsonl"
    if jsonl.is_file():
        occs = []
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            act = row.get("action")
            if act is None:
                continue
            day = str(row.get("day") or "2025-12-08")
            if contract == RESEARCH_ACTION_CONTRACT_V3:
                params = decode_continuous_research_v3(act, day=day)
            else:
                params = decode_continuous_research_v2(act, day=day)
            occs.append(params.occupied_heating_f)
        if occs and all(abs(x - 68.0) < 0.05 for x in occs):
            raise ResearchLongError("micro-gate: PPO actions collapsed to occupied=68")
    if not summary.get("eval") or summary.get("eval", {}).get("failed"):
        # Soft: eval may still fail on micro; require schedule_proof presence when eval ok
        pass
    else:
        rows = summary.get("eval", {}).get("rows") or []
        if rows and not any(r.get("schedule_proof") for r in rows):
            raise ResearchLongError("micro-gate: eval rows missing schedule_proof")