"""Model seed, parameter ledger, and run-manifest helpers for Vibe 23.

The helpers make every candidate model traceable, but they do not invoke
EnergyPlus or promote a seed model to calibrated status.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

LEDGER_STATUSES = {"SOURCE_FACT", "DATA_BOUND", "ASSUMPTION", "UNRESOLVED"}
_REQUIRED_LEDGER_FIELDS = {"id", "parameter_family", "status", "value", "units", "source_ref", "rationale"}


class ModelEvidenceError(ValueError):
    """Raised when a model artifact would lose evidence/provenance."""


def sha256_file(path: Path) -> str:
    path = Path(path)
    if not path.is_file():
        raise ModelEvidenceError(f"Required file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_parameter_ledger(path: Path) -> dict[str, Any]:
    try:
        ledger = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ModelEvidenceError(f"Invalid parameter ledger JSON: {path}") from exc
    validate_parameter_ledger(ledger)
    return ledger


def validate_parameter_ledger(ledger: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a ledger and expose facts that still block a model freeze."""
    if ledger.get("schema") != "vibe23.parameter_ledger.v1":
        raise ModelEvidenceError("parameter ledger schema must be vibe23.parameter_ledger.v1")
    entries = ledger.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ModelEvidenceError("parameter ledger must contain a non-empty entries list")
    ids: set[str] = set()
    unresolved: list[str] = []
    families: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ModelEvidenceError("each parameter ledger entry must be an object")
        missing = _REQUIRED_LEDGER_FIELDS - set(entry)
        if missing:
            raise ModelEvidenceError(f"parameter ledger entry missing fields: {sorted(missing)}")
        identifier = str(entry["id"])
        if identifier in ids:
            raise ModelEvidenceError(f"duplicate parameter ledger id: {identifier}")
        ids.add(identifier)
        status = entry["status"]
        if status not in LEDGER_STATUSES:
            raise ModelEvidenceError(f"unknown parameter ledger status: {status}")
        families.add(str(entry["parameter_family"]))
        if status == "UNRESOLVED":
            unresolved.append(identifier)
    return {
        "entries": len(entries),
        "parameter_families": sorted(families),
        "unresolved_ids": sorted(unresolved),
        "model_freeze_eligible": not unresolved,
    }


def create_iteration_manifest(
    *,
    iteration_id: str,
    parent_iteration_id: str | None,
    changed_parameter_families: Iterable[str],
    hypothesis: str,
    ledger: Mapping[str, Any],
    model_input_hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Create a narrow, auditable candidate-iteration record.

    Calibration is deliberately constrained to one or two named parameter
    families.  Broad "tune everything" changes are not reproducible.
    """
    summary = validate_parameter_ledger(ledger)
    changed = sorted({str(item).strip() for item in changed_parameter_families if str(item).strip()})
    if not iteration_id.strip():
        raise ModelEvidenceError("iteration_id is required")
    if not hypothesis.strip():
        raise ModelEvidenceError("hypothesis is required")
    if not 1 <= len(changed) <= 2:
        raise ModelEvidenceError("each iteration must change one or two named parameter families")
    unknown = sorted(set(changed) - set(summary["parameter_families"]))
    if unknown:
        raise ModelEvidenceError(f"iteration references unknown parameter families: {unknown}")
    required_hashes = {"idf_sha256", "epw_sha256", "source_data_sha256", "point_map_sha256", "parameter_ledger_sha256"}
    missing_hashes = sorted(key for key in required_hashes if not model_input_hashes.get(key))
    if missing_hashes:
        raise ModelEvidenceError(f"iteration manifest missing required hashes: {missing_hashes}")
    invalid_hashes = sorted(
        key
        for key in required_hashes
        if len(str(model_input_hashes[key])) != 64
        or any(character not in "0123456789abcdef" for character in str(model_input_hashes[key]))
    )
    if invalid_hashes:
        raise ModelEvidenceError(f"iteration manifest has invalid SHA-256 hashes: {invalid_hashes}")
    return {
        "schema": "vibe23.calibration_iteration.v1",
        "iteration_id": iteration_id,
        "parent_iteration_id": parent_iteration_id,
        "created_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "claim_status": "CALIBRATION_IN_PROGRESS",
        "hypothesis": hypothesis,
        "changed_parameter_families": changed,
        "parameter_ledger_sha256": canonical_json_sha256(ledger),
        "ledger_summary": summary,
        "model_input_hashes": dict(sorted(model_input_hashes.items())),
        "result": "NOT_RUN",
        "promotion_rule": "A run result alone cannot promote this candidate beyond MODEL_SEED.",
    }


def build_model_manifest(
    *,
    idf_path: Path,
    epw_path: Path,
    source_data_manifest_path: Path,
    point_map_path: Path,
    parameter_ledger_path: Path,
    energyplus_version: str,
    output_hashes: Mapping[str, str] | None = None,
    energyplus_run_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Hash the full set of artifacts required to reproduce a candidate run."""
    ledger = read_parameter_ledger(parameter_ledger_path)
    if not energyplus_version.strip():
        raise ModelEvidenceError("energyplus_version is required")
    inputs = {
        "idf_sha256": sha256_file(idf_path),
        "epw_sha256": sha256_file(epw_path),
        "source_data_sha256": sha256_file(source_data_manifest_path),
        "point_map_sha256": sha256_file(point_map_path),
        "parameter_ledger_sha256": sha256_file(parameter_ledger_path),
    }
    ledger_summary = validate_parameter_ledger(ledger)
    run_evidence = dict(energyplus_run_evidence or {})
    run_gate_passed = (
        run_evidence.get("exit_code") == 0
        and run_evidence.get("fatal_errors") == 0
        and run_evidence.get("severe_errors") == 0
        and run_evidence.get("deterministic_repeat_passed") is True
        and isinstance(run_evidence.get("run_manifest_sha256"), str)
        and len(run_evidence["run_manifest_sha256"]) == 64
        and all(character in "0123456789abcdef" for character in run_evidence["run_manifest_sha256"])
    )
    status = "MODEL_SEED" if ledger_summary["model_freeze_eligible"] and run_gate_passed else "CALIBRATION_BOOTSTRAP"
    return {
        "schema": "vibe23.model_manifest.v1",
        "created_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "claim_status": status,
        "energyplus_version": energyplus_version,
        "input_hashes": inputs,
        "output_hashes": dict(sorted((output_hashes or {}).items())),
        "parameter_ledger_summary": ledger_summary,
        "energyplus_seed_gate": {"passes": run_gate_passed, "evidence": run_evidence or None},
        "warning": "MODEL_SEED requires clean repeatable run evidence; no status asserts calibration or DSM readiness.",
    }


def render_idf_seed(template_path: Path, destination: Path, replacements: Mapping[str, str]) -> Path:
    """Render explicit ``{{TOKEN}}`` placeholders in the non-runnable seed template.

    Rendering fails if a token is unknown or left unresolved.  The resulting
    file is still only a seed until geometry, HVAC capacities, schedules and
    point bindings are evidenced and EnergyPlus has successfully run it.
    """
    text = Path(template_path).read_text(encoding="utf-8")
    for token, value in replacements.items():
        marker = "{{" + token + "}}"
        if marker not in text:
            raise ModelEvidenceError(f"Template does not contain replacement token {marker}")
        if not str(value).strip():
            raise ModelEvidenceError(f"Replacement for {marker} is blank")
        if any(fragment in str(value) for fragment in ("\r", "\n", "{{", "}}")):
            raise ModelEvidenceError(f"Replacement for {marker} contains forbidden template control text")
        text = text.replace(marker, str(value))
    if "{{" in text or "}}" in text:
        raise ModelEvidenceError("IDF seed contains unresolved template tokens")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8", newline="\n")
    return destination
