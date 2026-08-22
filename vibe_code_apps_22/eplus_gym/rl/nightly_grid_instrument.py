"""Process-tree compute instrumentation (Windows-compatible via psutil)."""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class ProcessMetrics:
    wall_s: float | None = None
    child_user_cpu_s: float | None = None
    child_system_cpu_s: float | None = None
    peak_rss_bytes: int | None = None
    pid: int | None = None
    utc_start: str | None = None
    utc_end: str | None = None
    exit_code: int | None = None
    notes: dict[str, Any] = field(default_factory=dict)


def _tree_cpu_rss(proc: Any) -> tuple[float, float, int]:
    """Return (user_s, system_s, rss_bytes) for process + children."""
    user = system = 0.0
    rss = 0
    try:
        ct = proc.cpu_times()
        user += float(ct.user)
        system += float(ct.system)
        rss += int(proc.memory_info().rss)
        for child in proc.children(recursive=True):
            try:
                ct = child.cpu_times()
                user += float(ct.user)
                system += float(ct.system)
                rss += int(child.memory_info().rss)
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        return user, system, rss
    return user, system, rss


def run_instrumented(fn: Callable[[], Any], *, poll_s: float = 0.25) -> tuple[Any, ProcessMetrics]:
    """Run callable in-process while sampling this process tree (best-effort)."""
    metrics = ProcessMetrics(utc_start=datetime.now(timezone.utc).isoformat())
    try:
        import psutil
        import os

        proc = psutil.Process(os.getpid())
        metrics.pid = int(proc.pid)
    except Exception as exc:  # noqa: BLE001
        metrics.notes["psutil"] = f"unavailable: {exc}"
        t0 = time.perf_counter()
        result = fn()
        metrics.wall_s = time.perf_counter() - t0
        metrics.utc_end = datetime.now(timezone.utc).isoformat()
        metrics.child_user_cpu_s = None
        metrics.child_system_cpu_s = None
        metrics.peak_rss_bytes = None
        metrics.notes["reason_null_cpu_rss"] = "psutil unavailable"
        return result, metrics

    peak_rss = 0
    t0 = time.perf_counter()
    # Sample in a simple loop by running fn (caller should be the heavy work).
    # For subprocess-based work, use instrument_subprocess instead.
    result = fn()
    metrics.wall_s = time.perf_counter() - t0
    user, system, rss = _tree_cpu_rss(proc)
    peak_rss = max(peak_rss, rss)
    metrics.child_user_cpu_s = user
    metrics.child_system_cpu_s = system
    metrics.peak_rss_bytes = peak_rss
    metrics.utc_end = datetime.now(timezone.utc).isoformat()
    return result, metrics


def instrument_subprocess(cmd: list[str], *, cwd: str | None = None, poll_s: float = 0.5) -> tuple[int, str, str, ProcessMetrics]:
    """Run a subprocess and sample CPU/RSS of the child process tree."""
    import subprocess

    metrics = ProcessMetrics(utc_start=datetime.now(timezone.utc).isoformat())
    t0 = time.perf_counter()
    try:
        import psutil
    except Exception as exc:  # noqa: BLE001
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        metrics.wall_s = time.perf_counter() - t0
        metrics.exit_code = int(proc.returncode)
        metrics.utc_end = datetime.now(timezone.utc).isoformat()
        metrics.notes["psutil"] = f"unavailable: {exc}"
        metrics.notes["reason_null_cpu_rss"] = "psutil unavailable"
        return proc.returncode, proc.stdout or "", proc.stderr or "", metrics

    popen = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    metrics.pid = int(popen.pid)
    ps = psutil.Process(popen.pid)
    peak_rss = 0
    user0, sys0, _ = _tree_cpu_rss(ps)
    while popen.poll() is None:
        try:
            _, _, rss = _tree_cpu_rss(ps)
            peak_rss = max(peak_rss, rss)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(poll_s)
    stdout, stderr = popen.communicate()
    metrics.wall_s = time.perf_counter() - t0
    metrics.exit_code = int(popen.returncode)
    try:
        user1, sys1, rss = _tree_cpu_rss(ps)
        peak_rss = max(peak_rss, rss)
        metrics.child_user_cpu_s = max(0.0, user1 - user0)
        metrics.child_system_cpu_s = max(0.0, sys1 - sys0)
    except Exception as exc:  # noqa: BLE001
        metrics.notes["cpu_sample_error"] = str(exc)
        metrics.child_user_cpu_s = None
        metrics.child_system_cpu_s = None
        metrics.notes["reason_null_cpu"] = str(exc)
    metrics.peak_rss_bytes = peak_rss or None
    metrics.utc_end = datetime.now(timezone.utc).isoformat()
    return int(popen.returncode), stdout or "", stderr or "", metrics


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def aggregate_timing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    walls = [float(r["wall_s"]) for r in rows if r.get("wall_s") is not None]
    cpu = [
        float(r["child_user_cpu_s"] or 0) + float(r["child_system_cpu_s"] or 0)
        for r in rows
        if r.get("child_user_cpu_s") is not None
    ]
    rss = [int(r["peak_rss_bytes"]) for r in rows if r.get("peak_rss_bytes") is not None]
    fails = sum(1 for r in rows if int(r.get("exit_code") or 0) != 0 or r.get("status") == "FAILED")
    total_wall = float(sum(walls)) if walls else 0.0
    n = len(rows)
    return {
        "n_candidates": n,
        "total_wall_s": total_wall,
        "total_child_cpu_s": float(sum(cpu)) if cpu else None,
        "mean_latency_s": float(statistics.mean(walls)) if walls else None,
        "median_latency_s": float(statistics.median(walls)) if walls else None,
        "p95_latency_s": percentile(walls, 95),
        "max_latency_s": max(walls) if walls else None,
        "candidates_per_minute": (n / (total_wall / 60.0)) if total_wall > 0 else None,
        "intervals_per_second": ((n * 96) / total_wall) if total_wall > 0 else None,
        "failure_rate": (fails / n) if n else 0.0,
        "peak_aggregate_rss_bytes": max(rss) if rss else None,
    }
