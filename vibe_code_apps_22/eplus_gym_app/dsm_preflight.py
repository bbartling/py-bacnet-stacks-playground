"""Preflight checks before any EnergyPlus Popen for DSM campaigns."""
from __future__ import annotations

import hashlib
import os
from datetime import date
from pathlib import Path
from typing import Any

from eplus_gym.discover import energyplus_available
from eplus_gym.month_calendar import DEPLOYABLE_STRATEGIES
from eplus_gym_app.open_meteo_epw import parse_epw_span


class PreflightError(ValueError):
    """Structured DSM preflight failure (no simulation started)."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {"type": "PreflightError", "message": str(self), "details": self.details}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inclusive_days(begin: str, end: str) -> int:
    b = date.fromisoformat(str(begin)[:10])
    e = date.fromisoformat(str(end)[:10])
    if e < b:
        raise PreflightError(
            f"Invalid period: end {e.isoformat()} is before begin {b.isoformat()}. "
            "No simulation started.",
            details={"begin": str(begin), "end": str(end)},
        )
    return (e - b).days + 1


def format_coverage_error(
    *,
    begin: str,
    end: str,
    epw: Path,
    span: dict[str, Any],
) -> str:
    cov_start = span.get("start")
    cov_end = span.get("end")
    cov_s = cov_start.isoformat() if hasattr(cov_start, "isoformat") else str(cov_start)
    cov_e = cov_end.isoformat() if hasattr(cov_end, "isoformat") else str(cov_end)
    return (
        f"Requested RunPeriod {str(begin)[:10]} -> {str(end)[:10]} is outside published "
        f"EPW coverage {cov_s} -> {cov_e} ({Path(epw).name}). "
        f"Invalid end relative to weather file. No simulation started."
    )


def assert_period_within_epw(begin: str, end: str, epw: Path) -> dict[str, Any]:
    epw = Path(epw)
    if not epw.is_file():
        raise PreflightError(
            f"EPW not found: {epw}. No simulation started.",
            details={"epw": str(epw)},
        )
    span = parse_epw_span(epw)
    cov_start = span.get("start")
    cov_end = span.get("end")
    if cov_start is None or cov_end is None:
        raise PreflightError(
            f"Could not parse EPW coverage from {epw}. No simulation started.",
            details={"epw": str(epw), "span": span},
        )
    b = date.fromisoformat(str(begin)[:10])
    e = date.fromisoformat(str(end)[:10])
    if b < cov_start or e > cov_end:
        raise PreflightError(
            format_coverage_error(begin=begin, end=end, epw=epw, span=span),
            details={
                "begin": b.isoformat(),
                "end": e.isoformat(),
                "epw": str(epw),
                "coverage_start": cov_start.isoformat(),
                "coverage_end": cov_end.isoformat(),
            },
        )
    return {
        "epw": str(epw),
        "coverage_start": cov_start.isoformat(),
        "coverage_end": cov_end.isoformat(),
        "n_rows": span.get("n_rows"),
    }


def run_preflight(
    *,
    idf: Path,
    epws: list[Path],
    begin: str,
    end: str,
    max_steps: int,
    strategies: list[str],
    out_root: Path,
    expected_idf_sha256: str | None = None,
    require_energyplus: bool = True,
) -> dict[str, Any]:
    """Validate campaign inputs. Raises PreflightError; never starts EnergyPlus."""
    idf = Path(idf)
    out_root = Path(out_root)
    details: dict[str, Any] = {}

    if not idf.is_file():
        raise PreflightError(
            f"Champion IDF not found: {idf}. No simulation started.",
            details={"idf": str(idf)},
        )
    idf_hash = sha256_file(idf)
    details["idf"] = str(idf)
    details["idf_sha256"] = idf_hash
    if expected_idf_sha256 and expected_idf_sha256.lower() != idf_hash.lower():
        raise PreflightError(
            f"IDF SHA-256 mismatch for {idf.name}: "
            f"runtime={idf_hash[:12]}… published={expected_idf_sha256[:12]}…. "
            "No simulation started.",
            details={
                "idf": str(idf),
                "idf_sha256": idf_hash,
                "expected_idf_sha256": expected_idf_sha256,
            },
        )

    n_days = inclusive_days(begin, end)
    expected_steps = n_days * 96
    details["begin"] = str(begin)[:10]
    details["end"] = str(end)[:10]
    details["n_days"] = n_days
    details["max_steps"] = int(max_steps)
    details["expected_max_steps"] = expected_steps
    if int(max_steps) != expected_steps:
        raise PreflightError(
            f"max_steps={max_steps} does not match inclusive days×96 "
            f"({n_days}*96={expected_steps}) for {begin}→{end}. No simulation started.",
            details=details,
        )

    bad = [s for s in strategies if s not in DEPLOYABLE_STRATEGIES]
    if bad:
        raise PreflightError(
            f"Unknown strategies {bad}; allowed={list(DEPLOYABLE_STRATEGIES)}. "
            "No simulation started.",
            details={"strategies": list(strategies), "bad": bad},
        )
    details["strategies"] = list(strategies)

    if not epws:
        raise PreflightError("No EPW paths provided. No simulation started.", details=details)

    epw_meta: list[dict[str, Any]] = []
    for epw in epws:
        epw_meta.append(assert_period_within_epw(begin, end, Path(epw)))
    details["epws"] = epw_meta

    try:
        out_root.mkdir(parents=True, exist_ok=True)
        probe = out_root / ".dsm_preflight_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise PreflightError(
            f"Out dir not writable: {out_root} ({exc}). No simulation started.",
            details={"out_root": str(out_root)},
        ) from exc
    details["out_root"] = str(out_root)

    if require_energyplus and not energyplus_available():
        raise PreflightError(
            "EnergyPlus is not discoverable (set ENERGYPLUS_ROOT). No simulation started.",
            details=details,
        )
    details["energyplus_available"] = energyplus_available()
    return details
