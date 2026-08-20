"""Phase 1 immutable evidence freeze: date-use ledger + research-long audit."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

from eplus_gym.date_use_ledger import NO_LOCKED_UNSEEN, JAN_2026_END, JAN_2026_START
from eplus_gym.eplus_err import parse_eplus_err
from eplus_gym.rl.research_eval import select_winner
from eplus_gym.rl.split_manifest import TRAIN_END, VAL_END, TEST_END

NO_PRISTINE_LOCKED_TEST = "NO_PRISTINE_LOCKED_TEST_AVAILABLE"

# Dates already used for physics / P1 development (never relabel as unseen holdout).
PHYSICS_DEVELOPMENT_DATES = (
    "2026-01-12",
    "2026-01-25",
    "2026-01-26",
    "2026-03-16",
)

ADAPTATION_DEVELOPMENT_DATES: tuple[str, ...] = ()


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_head() -> dict[str, Any]:
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(
            subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        )
        return {"branch": branch, "sha": sha, "dirty": dirty}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"branch": None, "sha": None, "dirty": None}


def build_frozen_date_use_ledger(
    *,
    rl_training_start: str = "2025-11-01",
    rl_training_end: str = TRAIN_END.isoformat(),
    validation_start: str = "2025-12-15",
    validation_end: str = VAL_END.isoformat(),
    locked_test_start: str = JAN_2026_START.isoformat(),
    locked_test_end: str = TEST_END.isoformat(),
    physics_development_dates: Sequence[str] = PHYSICS_DEVELOPMENT_DATES,
    adaptation_development_dates: Sequence[str] = ADAPTATION_DEVELOPMENT_DATES,
) -> dict[str, Any]:
    """Freeze date-use ledger before any new EnergyPlus or policy development."""
    jan_inspected = sorted(
        {
            d
            for d in physics_development_dates
            if JAN_2026_START <= date.fromisoformat(d[:10]) <= JAN_2026_END
        }
    )
    pristine_locked_test = not jan_inspected and not any(
        JAN_2026_START <= date.fromisoformat(d[:10]) <= JAN_2026_END
        for d in adaptation_development_dates
    )
    body: dict[str, Any] = {
        "schema": "vibe22.date_use_ledger.v1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "physics_development": {
            "dates": sorted({str(d)[:10] for d in physics_development_dates}),
            "note": "Includes January 2026 P1 gates and manual perturbation days; not an unseen holdout.",
        },
        "rl_training": {
            "start": rl_training_start,
            "end": rl_training_end,
            "fold": "train",
        },
        "validation": {
            "start": validation_start,
            "end": validation_end,
            "fold": "validation",
            "note": "Chronological model-selection only; not operational promotion.",
        },
        "adaptation_development": {
            "dates": sorted({str(d)[:10] for d in adaptation_development_dates}),
            "note": "Reserved for simulated shadow adaptation; empty until Phase 14.",
        },
        "locked_test": {
            "nominal_window": f"{locked_test_start}:{locked_test_end}",
            "status": "FROZEN_UNTOUCHED" if pristine_locked_test else NO_PRISTINE_LOCKED_TEST,
            "inspected_january_dates": jan_inspected,
            "rule": "Never relabel an already inspected January period as unseen.",
        },
        "locked_unseen_label": NO_LOCKED_UNSEEN if not pristine_locked_test else None,
    }
    blob = _stable_json({k: v for k, v in body.items() if k != "ledger_sha256"}).encode("utf-8")
    body["ledger_sha256"] = hashlib.sha256(blob).hexdigest()
    return body


def _sum_w2a_phases(gate: Mapping[str, Any]) -> dict[str, int]:
    phase = dict(gate.get("w2a_low_airflow_by_phase") or {})
    return {
        "warmup": int(phase.get("warmup") or 0),
        "sizing": int(phase.get("sizing") or 0),
        "scored_runtime": int(phase.get("scored_runtime") or 0),
        "total_recurring_printed": int((gate.get("recurring") or {}).get("w2a_low_airflow") or 0),
    }


def _aggregate_w2a(err_paths: Sequence[Path]) -> dict[str, Any]:
    totals = {"warmup": 0, "sizing": 0, "scored_runtime": 0, "total_recurring_printed": 0}
    by_file: list[dict[str, Any]] = []
    severe_fatal = {"severe": 0, "fatal": 0, "files": 0}
    for err in err_paths:
        gate = parse_eplus_err(err)
        phases = _sum_w2a_phases(gate)
        for k in totals:
            totals[k] += phases[k]
        severe_fatal["severe"] += int(gate.get("severe_count") or 0)
        severe_fatal["fatal"] += int(gate.get("fatal_count") or 0)
        severe_fatal["files"] += 1
        by_file.append(
            {
                "err_path": err.name,
                "parent": err.parent.name,
                **phases,
                "severe_count": gate.get("severe_count"),
                "fatal_count": gate.get("fatal_count"),
                "completed_successfully": gate.get("completed_successfully"),
            }
        )
    return {"totals": totals, "by_file": by_file, "severe_fatal": severe_fatal}


def _count_valid_transitions(seed_dir: Path) -> int:
    summary = seed_dir / "train_summary.json"
    if summary.is_file():
        doc = _load_json(summary)
        n = doc.get("n_episodes_logged") or doc.get("timesteps")
        if n is not None:
            return int(n)
    for name in ("episodes.jsonl", "train_transitions.jsonl"):
        path = seed_dir / name
        if path.is_file():
            return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_research_long_run(run_root: Path) -> dict[str, Any]:
    """Recompute research-long summary from raw site artifacts."""
    run_root = Path(run_root)
    eval_path = run_root / "eval.json"
    campaign_path = run_root / "campaign_manifest.json"
    if not eval_path.is_file():
        raise FileNotFoundError(f"missing eval.json under {run_root}")
    eval_doc = _load_json(eval_path)
    campaign = _load_json(campaign_path) if campaign_path.is_file() else {}

    rows = list(eval_doc.get("rows") or [])
    winner = eval_doc.get("winner")
    validation_selected = select_winner(rows) if rows else None

    trained_arms = sorted({str(r.get("arm")) for r in rows if str(r.get("arm", "")).startswith("trained_")})
    seeds: dict[str, list[str]] = {}
    for arm in trained_arms:
        algo = "ppo" if "ppo" in arm else ("dqn" if "dqn" in arm else "other")
        seeds.setdefault(algo, []).append(arm)

    def _arm_stats(arm: str) -> dict[str, float]:
        xs = [r for r in rows if str(r.get("arm")) == arm]
        if not xs:
            return {}
        rews = [float(r.get("training_reward") or 0.0) for r in xs]
        peaks = [float(r.get("peak_kw") or 0.0) for r in xs]
        kwh = [float(r.get("daily_kwh") or 0.0) for r in xs]
        ready = [1.0 if r.get("readiness_ok") else 0.0 for r in xs]
        return {
            "n_rows": len(xs),
            "mean_reward": float(sum(rews) / len(rews)),
            "median_reward": float(median(rews)),
            "mean_peak_kw": float(sum(peaks) / len(peaks)),
            "mean_daily_kwh": float(sum(kwh) / len(kwh)),
            "readiness_rate": float(sum(ready) / len(ready)),
        }

    policy_stats = {arm: _arm_stats(arm) for arm in trained_arms}

    fingerprints = sorted(
        {
            str(r.get("decoded_schedule_fingerprint"))
            for r in rows
            if r.get("decoded_schedule_fingerprint")
        }
    )

    transitions: dict[str, int] = {}
    for algo_seed in ("ppo_seed0", "ppo_seed1", "dqn_seed0", "dqn_seed1"):
        seed_dir = run_root / algo_seed
        transitions[algo_seed] = _count_valid_transitions(seed_dir)

    err_paths = sorted(run_root.rglob("eplusout.err"))
    w2a = _aggregate_w2a(err_paths)

    w2a_by_seed: dict[str, Any] = {}
    for seed_dir in ("ppo_seed0", "ppo_seed1", "dqn_seed0", "dqn_seed1"):
        seed_root = run_root / seed_dir
        if seed_root.is_dir():
            w2a_by_seed[seed_dir] = _aggregate_w2a(sorted(seed_root.rglob("eplusout.err")))

    eval_arms = sorted({str(r.get("arm")) for r in rows})
    w2a_by_eval_arm: dict[str, Any] = {}
    for arm in eval_arms:
        arm_dir = run_root / "eval_cache" / arm if (run_root / "eval_cache" / arm).is_dir() else None
        if arm_dir:
            w2a_by_eval_arm[arm] = _aggregate_w2a(sorted(arm_dir.rglob("eplusout.err")))

    readiness_all = [1.0 if r.get("readiness_ok") else 0.0 for r in rows]
    rews_all = [float(r.get("training_reward") or 0.0) for r in rows]

    return {
        "schema": "vibe22.research_long_audit.v1",
        "run_root_label": run_root.name,
        "campaign_manifest_sha256": _sha256_text(campaign_path.read_text(encoding="utf-8"))
        if campaign_path.is_file()
        else None,
        "trained_policies": len(trained_arms),
        "valid_transitions_per_seed": transitions,
        "total_valid_transitions": sum(transitions.values()),
        "validation_days": len(eval_doc.get("days") or []),
        "evaluation_rows": len(rows),
        "readiness_rate_all_arms": float(sum(readiness_all) / len(readiness_all)) if readiness_all else 0.0,
        "mean_reward_all_rows": float(sum(rews_all) / len(rews_all)) if rews_all else 0.0,
        "median_reward_all_rows": float(median(rews_all)) if rews_all else 0.0,
        "schedule_fingerprint_count": len(fingerprints),
        "schedule_fingerprints_sample": fingerprints[:8],
        "seed_variability": {algo: policy_stats.get(arms[0], {}) if arms else {} for algo, arms in seeds.items()},
        "policy_stats": policy_stats,
        "winner_legacy_key": winner,
        "validation_selected_policy": validation_selected,
        "winner_rule": eval_doc.get("winner_rule"),
        "factual_notes": {
            "best_individual_validation_policy": "trained_dqn_seed0"
            if "trained_dqn_seed0" in trained_arms
            else None,
            "ppo_consistency": "two seeds present" if len(seeds.get("ppo", [])) >= 2 else "insufficient seeds",
            "locked_unseen": eval_doc.get("locked_unseen") or NO_LOCKED_UNSEEN,
            "a04_physics_valid": False,
            "tariff_illustrative": True,
        },
        "w2a_low_airflow": {
            "all_eplusout_err_files": len(err_paths),
            "aggregate": w2a,
            "by_rl_seed": w2a_by_seed,
            "by_eval_arm": w2a_by_eval_arm or None,
        },
        "idf_sha256": campaign.get("idf_sha256"),
        "epw_sha256": campaign.get("epw_sha256"),
    }


def build_phase1_evidence_freeze(
    *,
    research_long_run_root: Path,
    app_root: Path | None = None,
) -> dict[str, Any]:
    app_root = Path(app_root or Path(__file__).resolve().parents[1])
    date_ledger = build_frozen_date_use_ledger()
    research_audit = audit_research_long_run(Path(research_long_run_root))

    try:
        import stable_baselines3

        sb3_version = getattr(stable_baselines3, "__version__", "unknown")
    except ImportError:
        sb3_version = None

    body: dict[str, Any] = {
        "schema": "vibe22.phase1_evidence_freeze.v1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "git": _git_head(),
        "python_version": platform.python_version(),
        "stable_baselines3_version": sb3_version,
        "energyplus_version": "26.1.0",
        "date_use_ledger": date_ledger,
        "research_long_audit": research_audit,
        "claim_labels": [
            "SIMULATION_ONLY_RL_RESEARCH",
            "A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED",
            "NO_BACNET_COMMAND_AUTHORITY",
            "Vibe19_untouched",
        ],
        "readiness_flags": {
            "SIMULATION_TRAINING_READY": False,
            "OPERATIONAL_DSM_READY": False,
            "long_campaign_allowed": False,
            "bacnet_commands": 0,
        },
    }
    blob = _stable_json({k: v for k, v in body.items() if k != "freeze_sha256"}).encode("utf-8")
    body["freeze_sha256"] = hashlib.sha256(blob).hexdigest()
    return body


def write_phase1_evidence_freeze(path: Path, body: Mapping[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(body), indent=2) + "\n", encoding="utf-8")
    return path
