"""Pull Severe/Fatal lines from EnergyPlus episode folders after a failed reset."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _first_severe_or_fatal(text: str) -> str | None:
    for line in text.splitlines():
        s = line.strip()
        low = s.lower()
        if "severe" in low or "fatal" in low or "** severe **" in low or "** fatal **" in low:
            return s[:400]
    return None


def _tail(text: str, n: int = 40) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-n:])


def find_eplusout_err(output_root: Path | str | None) -> Path | None:
    if output_root is None:
        return None
    root = Path(output_root)
    if not root.exists():
        return None
    direct = root / "eplusout.err"
    if direct.is_file():
        return direct
    hits = sorted(root.rglob("eplusout.err"), key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


def diagnose_startup_failure(runner: Any) -> dict[str, Any]:
    """Build a structured diagnosis from an EnergyPlusRunner after obs is None."""
    exit_code = None
    runner_error = getattr(runner, "handle_error", None)
    sim = getattr(runner, "sim_results", None) or {}
    if isinstance(sim, dict):
        exit_code = sim.get("exit_code")
        runner_error = runner_error or sim.get("error") or sim.get("message")

    out_root = None
    cfg = getattr(runner, "runner_config", None)
    if cfg is not None:
        out_root = getattr(cfg, "output", None)

    err_path = find_eplusout_err(out_root)
    severe = None
    log_tail = None
    if err_path is not None and err_path.is_file():
        try:
            text = err_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        severe = _first_severe_or_fatal(text)
        log_tail = _tail(text)

    bits = ["EnergyPlus startup failed: gym received no observation (obs is None)"]
    if exit_code not in (None, 0):
        bits.append(f"exit_code={exit_code}")
    if runner_error:
        bits.append(f"runner={runner_error}")
    if severe:
        bits.append(severe)
    elif log_tail:
        bits.append(log_tail.splitlines()[-1][:220] if log_tail else "")
    if err_path is not None:
        bits.append(f"err={err_path}")

    return {
        "message": " · ".join(b for b in bits if b),
        "exit_code": exit_code,
        "runner_error": str(runner_error) if runner_error else None,
        "err_path": str(err_path) if err_path else None,
        "severe_or_fatal": severe,
        "log_tail": log_tail,
    }
