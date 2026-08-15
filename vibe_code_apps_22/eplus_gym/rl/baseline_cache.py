"""Paired baseline cache keys and on-disk records (no candidate-as-baseline)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

SCHEMA = "vibe22.baseline_cache.v1"
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
    billing_floor_kw: float = 0.0,
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
            f"{float(billing_floor_kw):.6f}",
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
    billing_floor_kw: float = 0.0,
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
        billing_floor_kw=billing_floor_kw,
    )
    return {
        "schema": SCHEMA,
        "key": key,
        "idf_sha256": idf_sha,
        "staged_epw_sha256": epw_sha,
        "day": str(day)[:10],
        "lookback_days": int(lookback_days),
        "baseline_name": baseline_name,
        "energyplus_version": energyplus_version,
        "reward_name": reward_name,
        "tariff_version": tariff_version,
        "billing_floor_kw": float(billing_floor_kw),
    }


def _record_path(cache_dir: Path, key: str) -> Path:
    return Path(cache_dir) / f"{key}.json"


def atomic_write_json(path: Path, payload: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, indent=2) + "\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def load_record(cache_dir: Path, provenance: dict[str, Any]) -> dict[str, Any] | None:
    path = _record_path(cache_dir, str(provenance["key"]))
    if not path.is_file():
        return None
    rec = json.loads(path.read_text(encoding="utf-8"))
    if rec.get("schema") != SCHEMA:
        raise ValueError(f"baseline cache schema mismatch at {path}")
    for field in (
        "idf_sha256",
        "staged_epw_sha256",
        "day",
        "lookback_days",
        "baseline_name",
        "reward_name",
        "key",
    ):
        if rec.get(field) != provenance.get(field):
            raise ValueError(f"baseline cache provenance mismatch on {field}")
    if rec.get("baseline_kwh") is None or rec.get("baseline_peak_kw") is None:
        raise ValueError("baseline cache missing kwh/peak")
    if rec.get("source") == "candidate":
        raise ValueError("refusing candidate-as-baseline cache record")
    return rec


def store_record(cache_dir: Path, provenance: dict[str, Any], *, kwh: float, peak_kw: float) -> dict[str, Any]:
    rec = {
        **provenance,
        "schema": SCHEMA,
        "baseline_kwh": float(kwh),
        "baseline_peak_kw": float(peak_kw),
        "source": BASELINE_INCUMBENT,
    }
    atomic_write_json(_record_path(cache_dir, str(provenance["key"])), rec)
    return rec


def get_or_compute_incumbent_baseline(
    *,
    cache_dir: Path,
    provenance: dict[str, Any],
    compute: Callable[[], tuple[float, float]],
) -> dict[str, Any]:
    hit = load_record(cache_dir, provenance)
    if hit is not None:
        hit["cache_hit"] = True
        return hit
    kwh, peak = compute()
    rec = store_record(cache_dir, provenance, kwh=kwh, peak_kw=peak)
    rec["cache_hit"] = False
    return rec
