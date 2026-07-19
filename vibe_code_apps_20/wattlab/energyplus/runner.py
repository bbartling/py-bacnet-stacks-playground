"""Cache-aware EnergyPlus scenario runner (patch chain -> simulate -> record).

``run_scenario`` applies a named patch chain (via the patch registry) to an
IDF, simulates it through the existing Docker-backed ``simulate`` helper, and
returns a result record + per-run ``run_manifest.json``.

Caching is content-addressed: the cache key is a SHA-256 over the source IDF
hash, EPW hash, the normalized patch chain, the EnergyPlus version pin, the
Docker image name, and a runner version. Completed runs write an atomic
``COMPLETE.json`` marker; a later call with the same key reuses the cached
output directory instead of re-simulating.

eplusout.err is always parsed: Severe/Fatal diagnostics mark the scenario
``RESULTS_SUSPECT`` even when EnergyPlus exits successfully.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from wattlab.config import (
    DEFAULT_ELEC_RATE_USD_PER_KWH,
    DEFAULT_GAS_RATE_USD_PER_THERM,
    DOCKER_IMAGE,
    EP_VERSION_PIN,
)
from wattlab.energyplus.err import parse_err_file
from wattlab.energyplus.manifest import build_run_manifest, write_run_manifest
from wattlab.energyplus.mcp import simulate
from wattlab.energyplus.patches.registry import apply_patch
from wattlab.energyplus.results import (
    annual_from_output_dir,
    build_result_record,
    file_sha256,
)

# Bump when runner semantics change in a way that invalidates cached runs.
RUNNER_VERSION = "1"
COMPLETE_MARKER = "COMPLETE.json"


def _normalize_patches(patches: Sequence[Any] | None) -> list[dict[str, Any]]:
    """Normalize patch specs to [{"name": str, "params": dict}, ...]."""
    out: list[dict[str, Any]] = []
    for spec in patches or []:
        if isinstance(spec, str):
            out.append({"name": spec, "params": {}})
        elif isinstance(spec, Mapping):
            name = spec.get("name")
            if not name:
                raise ValueError(f"Patch spec missing 'name': {spec!r}")
            out.append({"name": str(name), "params": dict(spec.get("params") or {})})
        else:
            name, params = spec
            out.append({"name": str(name), "params": dict(params or {})})
    return out


def scenario_cache_key(
    idf: Path,
    epw: Path,
    patches: Sequence[Any] | None = None,
    *,
    energyplus_version: str = EP_VERSION_PIN,
    docker_image: str = DOCKER_IMAGE,
) -> str:
    """Deterministic content-addressed key for one scenario run."""
    payload = {
        "idf_sha256": file_sha256(Path(idf)),
        "epw_sha256": file_sha256(Path(epw)),
        "patches": _normalize_patches(patches),
        "energyplus_version": energyplus_version,
        "docker_image": docker_image,
        "runner_version": RUNNER_VERSION,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _write_marker_atomic(marker: Path, payload: dict[str, Any]) -> None:
    """Write the completion marker atomically (temp file + os.replace)."""
    marker.parent.mkdir(parents=True, exist_ok=True)
    tmp = marker.with_suffix(marker.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, marker)


def run_scenario(
    idf: Path,
    epw: Path,
    out_dir: Path,
    *,
    patches: Sequence[Any] | None = None,
    dry_run: bool = False,
    cache_dir: Path | None = None,
    elec_rate_usd_per_kwh: float = DEFAULT_ELEC_RATE_USD_PER_KWH,
    gas_rate_usd_per_therm: float = DEFAULT_GAS_RATE_USD_PER_THERM,
) -> dict[str, Any]:
    """Patch, simulate (or reuse cache), and record one EnergyPlus scenario."""
    idf = Path(idf)
    epw = Path(epw)
    out_dir = Path(out_dir)
    patch_specs = _normalize_patches(patches)
    cache_key = scenario_cache_key(idf, epw, patch_specs)
    run_id = f"scenario_{cache_key[:12]}"

    if dry_run:
        steps: list[dict[str, Any]] = [
            {"step": "apply_patch", "name": p["name"], "params": p["params"]}
            for p in patch_specs
        ]
        steps.append({"step": "simulate", "idf": str(idf), "epw": str(epw)})
        return {
            "dry_run": True,
            "run_id": run_id,
            "cache_key": cache_key,
            "cache_dir": str(cache_dir) if cache_dir else None,
            "steps": steps,
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- patch chain ---
    patch_metas: list[dict[str, Any]] = []
    current_idf = idf
    for i, spec in enumerate(patch_specs):
        dest = out_dir / f"patched_{i:02d}_{spec['name']}.idf"
        meta = apply_patch(spec["name"], current_idf, dest, spec["params"])
        patch_metas.append(meta)
        current_idf = dest

    # --- simulate or reuse cache ---
    if cache_dir is not None:
        cache_root = Path(cache_dir) / cache_key
        sim_dir = cache_root / "output"
        marker = cache_root / COMPLETE_MARKER
        cache_hit = marker.is_file()
    else:
        sim_dir = out_dir / "output"
        marker = None
        cache_hit = False

    if cache_hit:
        sim_meta: dict[str, Any] = {
            "ok": True,
            "cached": True,
            "output_dir": str(sim_dir),
        }
    else:
        sim_meta = simulate(current_idf, epw, sim_dir)
        sim_meta["cached"] = False

    # --- results + err triage ---
    err = parse_err_file(sim_dir / "eplusout.err")
    annual = annual_from_output_dir(
        sim_dir,
        elec_rate_usd_per_kwh=elec_rate_usd_per_kwh,
        gas_rate_usd_per_therm=gas_rate_usd_per_therm,
    )
    if not sim_meta.get("ok") or not annual.get("ok"):
        status = "MODEL_RUN_FAILED"
    elif err.get("results_suspect"):
        status = "RESULTS_SUSPECT"
    else:
        status = "COMPLETE"

    extra_flags = ["wattlab_runner"]
    for meta in patch_metas:
        extra_flags.extend(meta.get("flags") or [])
    if status == "RESULTS_SUSPECT":
        extra_flags.append("energyplus_severe_errors")

    record = build_result_record(
        run_id=run_id,
        measure_id=None,
        idf_path=current_idf,
        annual=annual,
        artifacts=[str(sim_dir / "eplustbl.htm"), str(current_idf)],
        extra_flags=extra_flags,
    )
    record["status"] = status
    record["cache_hit"] = cache_hit
    record["err_summary"] = {
        "warnings": err.get("warnings"),
        "severe": err.get("severe"),
        "fatal": err.get("fatal"),
    }

    if marker is not None and not cache_hit and status in {"COMPLETE", "RESULTS_SUSPECT"}:
        _write_marker_atomic(
            marker,
            {
                "cache_key": cache_key,
                "status": status,
                "completed_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "output_dir": str(sim_dir),
            },
        )

    finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = build_run_manifest(
        run_id=run_id,
        run_dir=out_dir,
        idf_path=current_idf,
        epw_path=epw,
        patches=patch_metas,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        extra={
            "cache_key": cache_key,
            "cache_hit": cache_hit,
            "cache_dir": str(cache_dir) if cache_dir else None,
            "sim_output_dir": str(sim_dir),
            "source_idf_sha256": file_sha256(idf),
            "err_summary": {
                "warnings": err.get("warnings"),
                "severe": err.get("severe"),
                "fatal": err.get("fatal"),
                "results_suspect": err.get("results_suspect"),
            },
        },
    )
    write_run_manifest(out_dir, manifest)

    return {
        "dry_run": False,
        "run_id": run_id,
        "cache_key": cache_key,
        "cache_hit": cache_hit,
        "status": status,
        "idf": str(current_idf),
        "epw": str(epw),
        "patches": patch_metas,
        "sim": sim_meta,
        "err": err,
        "annual": annual,
        "result_record": record,
        "run_manifest": manifest,
        "output_dir": str(sim_dir),
        "artifacts_dir": str(out_dir),
    }
