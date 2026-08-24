"""Portable EnergyPlus capability, execution, and artifact quality gates.

The module intentionally treats an EnergyPlus engine smoke test as a lower
claim than calibration.  It can use either a native executable or the Vibe 20
``energyplus-mcp-dev`` Docker image, then records enough provenance for a later
calibration campaign to decide whether the run is admissible.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

DEFAULT_DOCKER_IMAGE = "energyplus-mcp-dev"
DEFAULT_ENERGYPLUS_VERSION = "26.1.0-6f2e40d102"
DEFAULT_MCP_COMMIT = "5a7d3bb1d2e537ba329d3412c8b79d22cedd7c70"

Engine = Literal["auto", "native", "docker"]

_END_RE = re.compile(
    r"EnergyPlus Completed Successfully--\s*(\d+)\s*Warning;\s*(\d+)\s*Severe Errors",
    re.IGNORECASE,
)
_WARNING_RE = re.compile(r"\*\*\s*Warning\s*\*\*", re.IGNORECASE)
_SEVERE_RE = re.compile(r"\*\*\s*Severe\s*\*\*", re.IGNORECASE)
_FATAL_RE = re.compile(r"\*\s*Fatal\s*\*", re.IGNORECASE)


class EnergyPlusUnavailable(RuntimeError):
    """Raised when no requested EnergyPlus execution path is usable."""


@dataclass(frozen=True)
class EnergyPlusCapability:
    schema: str
    capability: str
    native_executable: str | None
    native_version: str | None
    docker_executable: str | None
    docker_daemon_available: bool
    docker_image: str
    docker_image_present: bool
    docker_energyplus_version: str | None
    mcp_vendor_path: str | None
    mcp_vendor_present: bool
    recommended_engine: str | None
    claim_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_probe(argv: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 127, "", str(exc))


def _version_text(result: subprocess.CompletedProcess[str]) -> str | None:
    if result.returncode != 0:
        return None
    value = (result.stdout or result.stderr or "").strip()
    return value or None


def energyplus_capability(
    *,
    docker_image: str = DEFAULT_DOCKER_IMAGE,
    mcp_vendor_path: Path | None = None,
) -> EnergyPlusCapability:
    """Probe native and Docker execution paths without pulling or building images."""
    native = shutil.which("energyplus") or shutil.which("EnergyPlus")
    native_version = _version_text(_run_probe([native, "--version"])) if native else None

    docker = shutil.which("docker")
    docker_daemon = False
    image_present = False
    docker_version = None
    if docker:
        docker_daemon = _run_probe([docker, "info", "--format", "{{.ServerVersion}}"]).returncode == 0
        if docker_daemon:
            image_present = (
                _run_probe([docker, "image", "inspect", docker_image], timeout=120).returncode == 0
            )
            if image_present:
                docker_version = _version_text(
                    _run_probe([docker, "run", "--rm", docker_image, "energyplus", "--version"], timeout=120)
                )

    vendor = Path(mcp_vendor_path).resolve() if mcp_vendor_path else None
    vendor_present = bool(vendor and (vendor / "energyplus-mcp-server").is_dir())
    if native_version:
        capability = "READY_NATIVE"
        recommended = "native"
    elif docker_version:
        capability = "READY_DOCKER"
        recommended = "docker"
    elif docker_daemon and not image_present:
        capability = "BLOCKED_DOCKER_IMAGE_MISSING"
        recommended = None
    else:
        capability = "BLOCKED_ENGINE_UNAVAILABLE"
        recommended = None

    return EnergyPlusCapability(
        schema="vibe23.energyplus_capability.v1",
        capability=capability,
        native_executable=native,
        native_version=native_version,
        docker_executable=docker,
        docker_daemon_available=docker_daemon,
        docker_image=docker_image,
        docker_image_present=image_present,
        docker_energyplus_version=docker_version,
        mcp_vendor_path=str(vendor) if vendor else None,
        mcp_vendor_present=vendor_present,
        recommended_engine=recommended,
        claim_boundary=(
            "Engine availability can support an EnergyPlus smoke run; it cannot establish "
            "Building 59 calibration or Guideline 14 compliance."
        ),
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def inspect_energyplus_run(
    run_dir: Path,
    *,
    idf: Path | None = None,
    epw: Path | None = None,
    energyplus_version: str | None = None,
) -> dict[str, Any]:
    """Inspect standard EnergyPlus artifacts and fail closed on missing evidence."""
    root = Path(run_dir).resolve()
    err = root / "eplusout.err"
    end = root / "eplusout.end"
    csv_path = root / "eplusout.csv"
    err_text = _read(err)
    end_text = _read(end)
    summary_text = end_text or err_text

    match = _END_RE.search(summary_text)
    warning_count = int(match.group(1)) if match else len(_WARNING_RE.findall(err_text))
    severe_count = int(match.group(2)) if match else len(_SEVERE_RE.findall(err_text))
    fatal_count = len(_FATAL_RE.findall(err_text))
    completed = "EnergyPlus Completed Successfully" in summary_text
    first_severe = next((line.strip() for line in err_text.splitlines() if _SEVERE_RE.search(line)), None)
    first_fatal = next((line.strip() for line in err_text.splitlines() if _FATAL_RE.search(line)), None)

    required_artifacts = {
        "eplusout.err": err.is_file(),
        "eplusout.end": end.is_file(),
        "eplusout.csv": csv_path.is_file() and csv_path.stat().st_size > 0,
    }
    engine_smoke_passed = (
        all(required_artifacts.values())
        and completed
        and severe_count == 0
        and fatal_count == 0
    )

    artifact_hashes: dict[str, str] = {}
    for name in (
        "eplusout.err",
        "eplusout.end",
        "eplusout.csv",
        "eplusout.sql",
        "eplusout.eio",
    ):
        artifact = root / name
        if artifact.is_file():
            artifact_hashes[name] = sha256_file(artifact)

    input_hashes: dict[str, str | None] = {
        "idf_sha256": sha256_file(Path(idf)) if idf and Path(idf).is_file() else None,
        "epw_sha256": sha256_file(Path(epw)) if epw and Path(epw).is_file() else None,
    }
    return {
        "schema": "vibe23.energyplus_run_inspection.v1",
        "run_dir": str(root),
        "energyplus_version": energyplus_version,
        "engine_smoke_status": "ENGINE_SMOKE_PASS" if engine_smoke_passed else "ENGINE_SMOKE_FAIL",
        "engine_smoke_passed": engine_smoke_passed,
        "completed_successfully": completed,
        "warning_count": warning_count,
        "severe_count": severe_count,
        "fatal_count": fatal_count,
        "first_severe": first_severe,
        "first_fatal": first_fatal,
        "required_artifacts": required_artifacts,
        "input_hashes": input_hashes,
        "artifact_hashes": artifact_hashes,
        "claim_status": "MODEL_SEED_EVIDENCE_ONLY" if engine_smoke_passed else "MODEL_RUN_FAILED",
        "claim_boundary": (
            "A passing engine smoke inspection proves only successful execution with zero severe/fatal errors. "
            "It does not prove Guideline 14 calibration, physical fidelity, holdout validation, or DSM readiness."
        ),
    }


def _ensure_empty_output(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"Output directory is not empty; refusing to overwrite prior run: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _copy_inputs(idf: Path, epw: Path, stage: Path) -> tuple[Path, Path]:
    stage.mkdir(parents=True, exist_ok=False)
    staged_idf = stage / idf.name
    staged_epw = stage / epw.name
    shutil.copy2(idf, staged_idf)
    shutil.copy2(epw, staged_epw)
    return staged_idf, staged_epw


def run_energyplus_smoke(
    idf: Path,
    epw: Path,
    output_dir: Path,
    *,
    engine: Engine = "auto",
    docker_image: str = DEFAULT_DOCKER_IMAGE,
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    """Run EnergyPlus once and write a provenance-bearing smoke manifest."""
    idf = Path(idf).resolve()
    epw = Path(epw).resolve()
    output_dir = Path(output_dir).resolve()
    if not idf.is_file():
        raise FileNotFoundError(f"IDF not found: {idf}")
    if not epw.is_file():
        raise FileNotFoundError(f"EPW not found: {epw}")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if engine not in {"auto", "native", "docker"}:
        raise ValueError("engine must be auto, native, or docker")

    capability = energyplus_capability(docker_image=docker_image)
    selected = capability.recommended_engine if engine == "auto" else engine
    if selected == "native" and not capability.native_version:
        raise EnergyPlusUnavailable("Native EnergyPlus executable is unavailable")
    if selected == "docker" and not capability.docker_energyplus_version:
        raise EnergyPlusUnavailable(
            f"Docker EnergyPlus is unavailable; need a running daemon and image {docker_image!r}"
        )
    if selected is None:
        raise EnergyPlusUnavailable(
            "No EnergyPlus engine is available. Expose Docker plus the pinned image or install native EnergyPlus."
        )

    _ensure_empty_output(output_dir)
    stage = output_dir.parent / f"{output_dir.name}__inputs"
    if stage.exists():
        raise FileExistsError(f"Input stage already exists; refusing to overwrite: {stage}")
    staged_idf, staged_epw = _copy_inputs(idf, epw, stage)

    if selected == "native":
        assert capability.native_executable
        command = [
            capability.native_executable,
            "-w",
            str(staged_epw),
            "-d",
            str(output_dir),
            "-r",
            str(staged_idf),
        ]
        version = capability.native_version
    else:
        assert capability.docker_executable
        try:
            os.chmod(output_dir, 0o777)
        except OSError:
            pass
        command = [
            capability.docker_executable,
            "run",
            "--rm",
        ]
        docker_user = os.environ.get("ENERGYPLUS_DOCKER_USER", "1000:1000").strip()
        if docker_user:
            command.extend(["--user", docker_user])
        command.extend([
            "-v",
            f"{stage}:/work/in:ro",
            "-v",
            f"{output_dir}:/work/out",
            docker_image,
            "energyplus",
            "-w",
            f"/work/in/{staged_epw.name}",
            "-d",
            "/work/out",
            "-r",
            f"/work/in/{staged_idf.name}",
        ])
        version = capability.docker_energyplus_version

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    (output_dir / "console.log").write_text(
        (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else ""),
        encoding="utf-8",
    )
    inspection = inspect_energyplus_run(output_dir, idf=idf, epw=epw, energyplus_version=version)
    inspection.update(
        {
            "schema": "vibe23.energyplus_smoke_manifest.v1",
            "created_at_utc": datetime.now(UTC).isoformat(),
            "selected_engine": selected,
            "docker_image": docker_image if selected == "docker" else None,
            "process_returncode": completed.returncode,
            "capability": capability.to_dict(),
            "command_contract": "energyplus -w <EPW> -d <OUTPUT> -r <IDF>",
        }
    )
    manifest = output_dir / "run_manifest.json"
    manifest.write_text(json.dumps(inspection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return inspection


__all__ = [
    "DEFAULT_DOCKER_IMAGE",
    "DEFAULT_ENERGYPLUS_VERSION",
    "DEFAULT_MCP_COMMIT",
    "EnergyPlusCapability",
    "EnergyPlusUnavailable",
    "energyplus_capability",
    "inspect_energyplus_run",
    "run_energyplus_smoke",
    "sha256_file",
]
