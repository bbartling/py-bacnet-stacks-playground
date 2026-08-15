"""Paired baseline cache keys (no silent reuse across IDF/EPW/E+ versions)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


BASELINE_INCUMBENT = "BAS_INCUMBENT_SCHEDULE"
BASELINE_NO_SETBACK_70F = "NO_SETBACK_70F_BASELINE"


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def paired_baseline_key(
    *,
    idf_sha256: str,
    staged_epw_sha256: str,
    day: str,
    lookback_days: int,
    baseline_name: str,
    energyplus_version: str,
    reward_name: str,
    tariff_version: str = "ILLUSTRATIVE",
) -> str:
    payload = "|".join(
        [
            str(idf_sha256),
            str(staged_epw_sha256),
            str(day)[:10],
            str(int(lookback_days)),
            str(baseline_name),
            str(energyplus_version),
            str(reward_name),
            str(tariff_version),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def key_from_paths(
    *,
    idf: Path,
    staged_epw: Path,
    day: str,
    lookback_days: int,
    baseline_name: str,
    energyplus_version: str,
    reward_name: str,
    tariff_version: str = "ILLUSTRATIVE",
) -> dict[str, Any]:
    idf_sha = _file_sha256(Path(idf))
    epw_sha = _file_sha256(Path(staged_epw))
    key = paired_baseline_key(
        idf_sha256=idf_sha,
        staged_epw_sha256=epw_sha,
        day=day,
        lookback_days=lookback_days,
        baseline_name=baseline_name,
        energyplus_version=energyplus_version,
        reward_name=reward_name,
        tariff_version=tariff_version,
    )
    return {
        "key": key,
        "idf_sha256": idf_sha,
        "staged_epw_sha256": epw_sha,
        "day": str(day)[:10],
        "lookback_days": int(lookback_days),
        "baseline_name": baseline_name,
        "energyplus_version": energyplus_version,
        "reward_name": reward_name,
        "tariff_version": tariff_version,
    }
