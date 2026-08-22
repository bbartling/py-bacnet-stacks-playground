"""RL compute fact import + frozen-policy inference micro-benchmark (no training)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from eplus_gym.rl.nightly_grid_instrument import percentile
from eplus_gym.rl.research_eval import load_sb3_model


def import_recorded_rl_facts(app_root: Path) -> dict[str, Any]:
    results = json.loads((Path(app_root) / "docs/results/vibe22_rl_poc_results.json").read_text(encoding="utf-8"))
    grid = json.loads(
        (Path(app_root) / "docs/results/grid_search/grid_search_compute_comparison.json").read_text(encoding="utf-8")
    )
    return {
        "note": "Workloads differ: one-time RL training vs historical multi-day grid vs nightly single-day grid.",
        "PRIMARY": {
            "models": 4,
            "transitions_per_model": 8192,
            "transitions": 32768,
            "elapsed_s": float(results["primary"]["elapsed_s"]),
        },
        "SECONDARY": {
            "models": 4,
            "transitions_per_model": 8192,
            "transitions": 32768,
            "elapsed_s": float(results["secondary"]["elapsed_s"]),
        },
        "historical_grid_screen": {
            "unique_fixed_policies": int(grid["grid"]["unique_fixed_policies"]),
            "candidate_days": int(grid["grid"]["candidate_days"]),
            "n_process_starts": int(grid["grid"].get("n_process_starts") or 131),
            "wall_clock_s": float(grid["grid"]["wall_clock_s"]),
        },
        "categories": [
            "one_time_offline_rl_training",
            "once_per_day_rl_inference",
            "once_per_day_energyplus_grid_search",
        ],
    }


def benchmark_inference(
    *,
    zip_path: Path,
    algo: str,
    n_calls: int = 1000,
    obs_dim: int = 206,
) -> dict[str, Any]:
    if not zip_path.is_file():
        return {"status": "NOT_RUN_MISSING_POLICY_ZIP", "path": str(zip_path)}
    t_load0 = time.perf_counter()
    model = load_sb3_model(zip_path, algo=algo)
    load_s = time.perf_counter() - t_load0
    # Warmup
    obs = np.zeros((obs_dim,), dtype=np.float32)
    # Prefer model obs dim if present
    shape = getattr(getattr(model, "observation_space", None), "shape", None)
    if shape:
        obs = np.zeros(int(shape[0]), dtype=np.float32)
    for _ in range(20):
        model.predict(obs, deterministic=True)
    samples_ms: list[float] = []
    peak_rss = None
    try:
        import os
        import psutil

        proc = psutil.Process(os.getpid())
        peak_rss = int(proc.memory_info().rss)
    except Exception:  # noqa: BLE001
        peak_rss = None
    for _ in range(int(n_calls)):
        t0 = time.perf_counter()
        model.predict(obs, deterministic=True)
        samples_ms.append((time.perf_counter() - t0) * 1000.0)
        if peak_rss is not None:
            try:
                peak_rss = max(peak_rss, int(proc.memory_info().rss))
            except Exception:  # noqa: BLE001
                pass
    return {
        "status": "OK",
        "path": str(zip_path),
        "algo": algo,
        "n_calls": n_calls,
        "model_load_s": load_s,
        "p50_ms": percentile(samples_ms, 50),
        "p95_ms": percentile(samples_ms, 95),
        "p99_ms": percentile(samples_ms, 99),
        "peak_rss_bytes": peak_rss,
        "obs_dim": int(obs.size),
        "note": "Inference bench uses a zero observation vector for timing only; not a policy claim.",
    }
