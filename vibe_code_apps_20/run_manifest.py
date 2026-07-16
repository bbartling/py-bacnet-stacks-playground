"""Reproducible run manifests (content hashes + software pins)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DOCKER_IMAGE, EP_VERSION_PIN
from results_parse import file_sha256


def build_run_manifest(
    *,
    run_id: str,
    run_dir: Path,
    idf_path: Path | None = None,
    epw_path: Path | None = None,
    patches: list[Any] | None = None,
    weather_suitability: dict[str, Any] | None = None,
    status: str = "SUCCESS",
    started_at: str | None = None,
    finished_at: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic run manifest dict (does not write)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    patch_names: list[str] = []
    for p in patches or []:
        if isinstance(p, dict):
            name = p.get("name") or p.get("idf_patch") or p.get("patch")
            if name:
                patch_names.append(str(name))
        elif p:
            patch_names.append(str(p))

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "energyplus_version": EP_VERSION_PIN,
        "docker_image": DOCKER_IMAGE,
        "model_sha256": file_sha256(idf_path) if idf_path and Path(idf_path).is_file() else None,
        "weather_sha256": file_sha256(epw_path) if epw_path and Path(epw_path).is_file() else None,
        "model_path": str(idf_path) if idf_path else None,
        "weather_path": str(epw_path) if epw_path else None,
        "patches": patch_names,
        "weather_suitability": weather_suitability,
        "started_at": started_at or now,
        "finished_at": finished_at or now,
        "status": status,
        "artifacts_dir": str(run_dir),
    }
    if extra:
        manifest.update(extra)
    return manifest


def write_run_manifest(run_dir: Path, manifest: dict[str, Any]) -> Path:
    """Write ``run_manifest.json`` under ``run_dir``; return path."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "run_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return path
