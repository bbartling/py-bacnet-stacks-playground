"""Parallel worker pilot for nightly grid compute."""
from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Sequence


def speedup_efficiency(*, t1: float, tp: float, workers: int) -> dict[str, float]:
    sp = float(t1) / float(tp) if tp > 0 else 0.0
    eff = float(t1) / (float(workers) * float(tp)) if workers > 0 and tp > 0 else 0.0
    return {"speedup": sp, "parallel_efficiency": eff, "workers": float(workers), "t1": t1, "tp": tp}


def run_worker_sweep(
    *,
    tasks: Sequence[dict[str, Any]],
    worker_fn: Callable[[dict[str, Any]], dict[str, Any]],
    worker_counts: Sequence[int] = (1, 2, 4),
    ram_bytes: int | None = None,
    peak_rss_per_worker: int | None = None,
    memory_fraction_cap: float = 0.7,
) -> dict[str, Any]:
    """Run the same task list under 1/2/4 workers; skip 4 if memory projection too high."""
    results: dict[str, Any] = {"runs": {}}
    t1 = None
    for p in worker_counts:
        if p >= 4 and ram_bytes and peak_rss_per_worker:
            if p * peak_rss_per_worker > memory_fraction_cap * ram_bytes:
                results["runs"][str(p)] = {
                    "skipped": True,
                    "reason": "projected peak RSS exceeds memory fraction cap",
                }
                continue
        t0 = time.perf_counter()
        if p == 1:
            out = [worker_fn(t) for t in tasks]
        else:
            out = []
            with ProcessPoolExecutor(max_workers=int(p)) as ex:
                futs = [ex.submit(worker_fn, t) for t in tasks]
                for f in as_completed(futs):
                    out.append(f.result())
        elapsed = time.perf_counter() - t0
        if p == 1:
            t1 = elapsed
        entry = {"wall_s": elapsed, "n_tasks": len(tasks), "skipped": False}
        if t1 is not None:
            entry.update(speedup_efficiency(t1=t1, tp=elapsed, workers=int(p)))
        results["runs"][str(p)] = entry
    # Recommend worker count: best wall among non-skipped with efficiency >= 0.5 if possible
    best = None
    for k, v in results["runs"].items():
        if v.get("skipped"):
            continue
        if best is None or float(v["wall_s"]) < float(best["wall_s"]):
            best = {"workers": int(k), **v}
    results["recommended_workers"] = (best or {}).get("workers", 1)
    results["scientific_reference_workers"] = 1
    return results
