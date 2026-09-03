"""Portable EnergyPlus capability, execution, and artifact quality gates.

The module intentionally treats an EnergyPlus engine smoke test as a lower
claim than calibration.  It can use either a native executable or the Vibe 20
``energyplus-mcp-dev`` Docker image, then records enough provenance for a later
calibration campaign to decide whether the run is admissible.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
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
DEFAULT_WINDOWS_ENERGYPLUS = Path(r"C:\EnergyPlusV26-1-0\energyplus.exe")
DEFAULT_ENERGYPLUS_ROOT = Path(r"C:\EnergyPlusV26-1-0")

Engine = Literal["auto", "native", "docker"]

_END_RE = re.compile(
    r"EnergyPlus Completed Successfully--\s*(\d+)\s*Warning;\s*(\d+)\s*Severe Errors",
    re.IGNORECASE,
)
_WARNING_RE = re.compile(r"\*\*\s*Warning\s*\*\*", re.IGNORECASE)
_SEVERE_RE = re.compile(r"\*\*\s*Severe\s*\*\*", re.IGNORECASE)
_FATAL_RE = re.compile(r"\*\s*Fatal\s*\*", re.IGNORECASE)
_FACILITY_HEADER_RE = re.compile(
    r"^\s*Electricity:Facility\s+\[[^\]]+\]\([^)]+\)\s*$",
    re.IGNORECASE,
)
_EPLUS_TIMESTAMP_RE = re.compile(
    r"^\s*(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$"
)


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
    docker_image_id: str | None
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


def resolve_native_energyplus(explicit: Path | str | None = None) -> Path | None:
    """Locate a native energyplus executable on Windows, Linux, or macOS.

    Honors ``ENERGYPLUS_EXE`` / ``ENERGYPLUS_ROOT`` (optionally loaded from ``.env``).
    """

    from .envfile import default_energyplus_executables, load_energyplus_env

    load_energyplus_env()
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env_exe = os.environ.get("ENERGYPLUS_EXE", "").strip()
    if env_exe:
        candidates.append(Path(env_exe).expanduser())
    env_root = os.environ.get("ENERGYPLUS_ROOT", "").strip()
    if env_root:
        root = Path(env_root).expanduser()
        candidates.extend([root / "energyplus.exe", root / "energyplus"])
    candidates.extend(default_energyplus_executables())
    which = shutil.which("energyplus") or shutil.which("EnergyPlus")
    if which:
        candidates.append(Path(which))
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_file():
            return resolved
    return None


def energyplus_capability(
    *,
    docker_image: str = DEFAULT_DOCKER_IMAGE,
    mcp_vendor_path: Path | None = None,
    eplus_path: Path | str | None = None,
) -> EnergyPlusCapability:
    """Probe native and Docker execution paths without pulling or building images."""
    native_path = resolve_native_energyplus(eplus_path)
    native = str(native_path) if native_path else None
    native_version = _version_text(_run_probe([native, "--version"])) if native else None

    docker = shutil.which("docker")
    docker_daemon = False
    image_present = False
    docker_image_id = None
    docker_version = None
    if docker:
        docker_daemon = _run_probe([docker, "info", "--format", "{{.ServerVersion}}"]).returncode == 0
        if docker_daemon:
            image_present = (
                _run_probe([docker, "image", "inspect", docker_image], timeout=120).returncode == 0
            )
            if image_present:
                docker_image_id = _version_text(
                    _run_probe([docker, "image", "inspect", "--format", "{{.Id}}", docker_image], timeout=120)
                )
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
        docker_image_id=docker_image_id,
        docker_energyplus_version=docker_version,
        mcp_vendor_path=str(vendor) if vendor else None,
        mcp_vendor_present=vendor_present,
        recommended_engine=recommended,
        claim_boundary=(
            "Engine availability can support an EnergyPlus smoke run; it cannot establish "
            "ASHRAE Guideline 14 calibration. Residential DSM demos use "
            "HYPOTHETICAL_GL14_TUNED_DEMO_MODEL labeling only."
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
    process_returncode: int | None = None,
    require_zero_warnings: bool = True,
) -> dict[str, Any]:
    """Inspect standard EnergyPlus artifacts and fail closed on missing evidence.

    The default policy implements the project's requested clean-run gate:
    warnings, severe errors, fatal errors, a nonzero/unknown process return
    code, missing input hashes, or a missing Facility electricity meter all
    block a pass.
    """
    root = Path(run_dir).resolve()
    err = root / "eplusout.err"
    end = root / "eplusout.end"
    csv_path = root / "eplusout.csv"
    console = root / "console.log"
    err_text = _read(err)
    end_text = _read(end)
    console_text = _read(console)
    end_match = _END_RE.search(end_text)
    err_match = _END_RE.search(err_text)
    console_match = _END_RE.search(console_text)
    summary_matches = [match for match in (end_match, err_match, console_match) if match is not None]
    diagnostic_text = err_text + "\n" + end_text + "\n" + console_text
    warning_count = max(
        [
            len(_WARNING_RE.findall(err_text)),
            len(_WARNING_RE.findall(console_text)),
            *(int(match.group(1)) for match in summary_matches),
        ]
    )
    severe_count = max(
        [
            len(_SEVERE_RE.findall(err_text)),
            len(_SEVERE_RE.findall(console_text)),
            *(int(match.group(2)) for match in summary_matches),
        ]
    )
    fatal_count = max(len(_FATAL_RE.findall(err_text)), len(_FATAL_RE.findall(console_text)))
    completed = end_match is not None and "terminated--fatal error detected" not in diagnostic_text.casefold()
    # EnergyPlus's console normally ends with the bare phrase ``EnergyPlus
    # Completed Successfully.`` while eplusout.end/err carry the counted
    # warning/severe summary.  Compare every *parseable counted* summary and
    # require eplusout.end; a bare console success line is not contradictory.
    counted_summaries = [match for match in (err_match, console_match) if match is not None]
    summary_consistent = end_match is not None and all(
        match.groups() == end_match.groups() for match in counted_summaries
    )
    first_severe = next((line.strip() for line in err_text.splitlines() if _SEVERE_RE.search(line)), None)
    first_fatal = next((line.strip() for line in err_text.splitlines() if _FATAL_RE.search(line)), None)

    csv_header: list[str] = []
    csv_data_rows = 0
    csv_values_valid = False
    csv_invalid_reason = "missing eplusout.csv"
    if csv_path.is_file():
        try:
            with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as stream:
                reader = csv.reader(stream)
                csv_header = next(reader, [])
                facility_indexes = [index for index, value in enumerate(csv_header) if _FACILITY_HEADER_RE.fullmatch(value)]
                if len(facility_indexes) != 1:
                    csv_invalid_reason = (
                        "CSV must contain exactly one canonical Electricity:Facility meter column"
                    )
                elif not csv_header or csv_header[0].strip().casefold() != "date/time":
                    csv_invalid_reason = "first CSV column must be Date/Time"
                else:
                    facility_index = facility_indexes[0]
                    csv_values_valid = True
                    previous_timestamp: tuple[int, int, int, int, int] | None = None
                    seen_timestamps: set[tuple[int, int, int, int, int]] = set()
                    for row_number, row in enumerate(reader, start=2):
                        if not any(value.strip() for value in row):
                            continue
                        csv_data_rows += 1
                        if len(row) != len(csv_header):
                            csv_values_valid = False
                            csv_invalid_reason = f"row {row_number} has {len(row)} fields; expected {len(csv_header)}"
                            break
                        timestamp_match = _EPLUS_TIMESTAMP_RE.fullmatch(row[0])
                        if timestamp_match is None:
                            csv_values_valid = False
                            csv_invalid_reason = f"row {row_number} has an invalid EnergyPlus timestamp"
                            break
                        month, day, hour, minute, second = (
                            int(timestamp_match.group(1)),
                            int(timestamp_match.group(2)),
                            int(timestamp_match.group(3)),
                            int(timestamp_match.group(4)),
                            int(timestamp_match.group(5) or 0),
                        )
                        timestamp_key = (month, day, hour, minute, second)
                        if (
                            not 1 <= month <= 12
                            or not 1 <= day <= 31
                            or not 0 <= hour <= 24
                            or not 0 <= minute <= 59
                            or not 0 <= second <= 59
                            or timestamp_key in seen_timestamps
                            or (previous_timestamp is not None and timestamp_key <= previous_timestamp)
                        ):
                            csv_values_valid = False
                            csv_invalid_reason = f"row {row_number} has a duplicate, invalid, or unordered timestamp"
                            break
                        seen_timestamps.add(timestamp_key)
                        previous_timestamp = timestamp_key
                        try:
                            facility_value = float(row[facility_index])
                        except ValueError:
                            csv_values_valid = False
                            csv_invalid_reason = f"row {row_number} has a nonnumeric Facility value"
                            break
                        if not math.isfinite(facility_value) or facility_value < 0.0:
                            csv_values_valid = False
                            csv_invalid_reason = f"row {row_number} has a nonfinite or negative Facility value"
                            break
                    if csv_values_valid and csv_data_rows == 0:
                        csv_values_valid = False
                        csv_invalid_reason = "CSV has no data rows"
                    elif csv_values_valid:
                        csv_invalid_reason = None
        except (csv.Error, OSError) as exc:
            csv_values_valid = False
            csv_invalid_reason = f"CSV parse failed: {exc}"
    facility_meter_present = sum(bool(_FACILITY_HEADER_RE.fullmatch(value)) for value in csv_header) == 1

    input_hashes: dict[str, str | None] = {
        "idf_sha256": sha256_file(Path(idf)) if idf and Path(idf).is_file() else None,
        "epw_sha256": sha256_file(Path(epw)) if epw and Path(epw).is_file() else None,
    }
    artifact_hashes: dict[str, str] = {}
    for name in (
        "eplusout.err",
        "eplusout.end",
        "eplusout.csv",
        "eplusout.sql",
        "eplusout.eio",
        "console.log",
    ):
        artifact = root / name
        if artifact.is_file():
            artifact_hashes[name] = sha256_file(artifact)

    manifest_path = root / "run_manifest.json"
    returncode_source = "explicit_current_process" if process_returncode is not None else None
    manifest_binding_valid = False
    if process_returncode is None and manifest_path.is_file():
        try:
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            recorded_returncode = manifest_payload.get("process_returncode")
            recorded_inputs = manifest_payload.get("input_hashes")
            recorded_artifacts = manifest_payload.get("artifact_hashes")
            required_artifact_names = {"eplusout.err", "eplusout.end", "eplusout.csv"}
            manifest_binding_valid = (
                manifest_payload.get("schema") == "vibe23.energyplus_smoke_manifest.v1"
                and manifest_payload.get("energyplus_version") == energyplus_version
                and manifest_payload.get("selected_engine") in {"native", "docker"}
                and recorded_inputs == input_hashes
                and isinstance(recorded_artifacts, dict)
                and required_artifact_names.issubset(recorded_artifacts)
                and all(recorded_artifacts.get(name) == artifact_hashes.get(name) for name in required_artifact_names)
            )
            if (
                manifest_binding_valid
                and isinstance(recorded_returncode, int)
                and not isinstance(recorded_returncode, bool)
            ):
                process_returncode = recorded_returncode
                returncode_source = "hash_bound_run_manifest"
        except (json.JSONDecodeError, OSError):
            pass
    returncode_binding_valid = returncode_source == "explicit_current_process" or manifest_binding_valid
    required_evidence = {
        "eplusout.err": err.is_file(),
        "eplusout.end": end.is_file(),
        "eplusout.csv": csv_path.is_file() and csv_path.stat().st_size > 0 and csv_values_valid,
        "facility_electricity_meter": facility_meter_present,
        "idf_sha256": input_hashes["idf_sha256"] is not None,
        "epw_sha256": input_hashes["epw_sha256"] is not None,
        "energyplus_version": bool(energyplus_version and energyplus_version.strip()),
        "process_returncode_zero": process_returncode == 0,
        "process_returncode_bound_to_artifacts": returncode_binding_valid,
        "end_summary_parseable": end_match is not None,
        "summary_consistent": summary_consistent,
    }
    warning_gate_passed = warning_count == 0 if require_zero_warnings else True
    engine_smoke_passed = (
        all(required_evidence.values())
        and completed
        and warning_gate_passed
        and severe_count == 0
        and fatal_count == 0
    )

    return {
        "schema": "vibe23.energyplus_run_inspection.v1",
        "run_dir": str(root),
        "energyplus_version": energyplus_version,
        "engine_smoke_status": "ENGINE_SMOKE_PASS" if engine_smoke_passed else "ENGINE_SMOKE_FAIL",
        "engine_smoke_passed": engine_smoke_passed,
        "completed_successfully": completed,
        "process_returncode": process_returncode,
        "process_returncode_source": returncode_source,
        "manifest_binding_valid": manifest_binding_valid,
        "require_zero_warnings": require_zero_warnings,
        "warning_gate_passed": warning_gate_passed,
        "warning_count": warning_count,
        "severe_count": severe_count,
        "fatal_count": fatal_count,
        "first_severe": first_severe,
        "first_fatal": first_fatal,
        "summary_consistent": summary_consistent,
        "facility_meter_present": facility_meter_present,
        "csv_data_rows": csv_data_rows,
        "csv_values_valid": csv_values_valid,
        "csv_invalid_reason": csv_invalid_reason,
        "required_evidence": required_evidence,
        "input_hashes": input_hashes,
        "artifact_hashes": artifact_hashes,
        "claim_status": "MODEL_SEED_EVIDENCE_ONLY" if engine_smoke_passed else "MODEL_RUN_FAILED",
        "claim_boundary": (
            "A passing engine smoke inspection proves only a hashed execution with return code zero, "
            "the Facility electricity meter present, and the declared warning/error policy satisfied. "
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
    eplus_path: Path | str | None = None,
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

    capability = energyplus_capability(docker_image=docker_image, eplus_path=eplus_path)
    selected = capability.recommended_engine if engine == "auto" else engine
    if selected == "native" and not capability.native_version:
        raise EnergyPlusUnavailable("Native EnergyPlus executable is unavailable")
    if selected == "docker" and not capability.docker_energyplus_version:
        raise EnergyPlusUnavailable(
            f"Docker EnergyPlus is unavailable; need a running daemon and image {docker_image!r}"
        )
    if selected is None:
        raise EnergyPlusUnavailable(
            "No EnergyPlus engine is available. Install native EnergyPlus "
            f"(default {DEFAULT_WINDOWS_ENERGYPLUS}) or expose Docker plus the pinned image."
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
            "-x",
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
            "-x",
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
    inspection = inspect_energyplus_run(
        output_dir,
        idf=idf,
        epw=epw,
        energyplus_version=version,
        process_returncode=completed.returncode,
        require_zero_warnings=True,
    )
    inspection.update(
        {
            "schema": "vibe23.energyplus_smoke_manifest.v1",
            "created_at_utc": datetime.now(UTC).isoformat(),
            "selected_engine": selected,
            "docker_image": docker_image if selected == "docker" else None,
            "process_returncode": completed.returncode,
            "capability": capability.to_dict(),
            "command_contract": "energyplus -x -w <EPW> -d <OUTPUT> -r <IDF>",
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
