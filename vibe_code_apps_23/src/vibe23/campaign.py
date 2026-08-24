"""Fail-closed, append-only bookkeeping for bounded calibration campaigns.

This module deliberately does not run EnergyPlus.  A caller stages an immutable
``CampaignRunSpec``, obtains an EnergyPlus inspection report elsewhere, then
records the admitted result.  That separation prevents a completed simulation
from being mistaken for a calibrated model.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

MAX_CAMPAIGN_RUNS = 50
_HEX = set("0123456789abcdef")


class CampaignError(ValueError):
    """Raised when campaign provenance, budget, or gates are incomplete."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _hash(value: str, *, label: str) -> str:
    value = str(value)
    if len(value) != 64 or any(ch not in _HEX for ch in value):
        raise CampaignError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


def _families(values: Iterable[str]) -> tuple[str, ...]:
    result = tuple(sorted({str(value).strip() for value in values if str(value).strip()}))
    if not result:
        raise CampaignError("at least one named parameter family is required")
    return result


@dataclass(frozen=True)
class CampaignManifest:
    """Immutable campaign contract; the budget can never exceed 50 published runs."""

    campaign_id: str
    declared_parameter_families: tuple[str, ...]
    input_hashes: Mapping[str, str]
    max_runs: int = MAX_CAMPAIGN_RUNS
    schema: str = "vibe23.calibration_campaign.v1"

    def __post_init__(self) -> None:
        if not self.campaign_id.strip():
            raise CampaignError("campaign_id is required")
        if not 1 <= self.max_runs <= MAX_CAMPAIGN_RUNS:
            raise CampaignError(f"max_runs must be between 1 and {MAX_CAMPAIGN_RUNS}")
        families = _families(self.declared_parameter_families)
        hashes = {str(key): _hash(value, label=str(key)) for key, value in self.input_hashes.items()}
        required = {"idf_sha256", "epw_sha256", "source_data_sha256", "point_map_sha256", "calibration_contract_sha256"}
        missing = sorted(required - set(hashes))
        if missing:
            raise CampaignError(f"campaign manifest missing required hashes: {missing}")
        object.__setattr__(self, "declared_parameter_families", families)
        object.__setattr__(self, "input_hashes", MappingProxyType(dict(sorted(hashes.items()))))

    @property
    def manifest_sha256(self) -> str:
        return canonical_sha256(self._identity())

    def _identity(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "declared_parameter_families": self.declared_parameter_families,
            "input_hashes": dict(self.input_hashes),
            "max_runs": self.max_runs,
            "schema": self.schema,
        }

    def as_dict(self) -> dict[str, Any]:
        data = self._identity()
        data["manifest_sha256"] = self.manifest_sha256
        return data


@dataclass(frozen=True)
class CampaignRunSpec:
    """One narrow, deterministic candidate; it contains no executable command."""

    campaign_manifest_sha256: str
    ordinal: int
    parent_candidate_id: str | None
    changed_parameter_families: tuple[str, ...]
    parameter_values: Mapping[str, Any]
    hypothesis: str
    input_hashes: Mapping[str, str]

    def __post_init__(self) -> None:
        _hash(self.campaign_manifest_sha256, label="campaign_manifest_sha256")
        if not 1 <= self.ordinal <= MAX_CAMPAIGN_RUNS:
            raise CampaignError(f"ordinal must be between 1 and {MAX_CAMPAIGN_RUNS}")
        if not self.hypothesis.strip():
            raise CampaignError("hypothesis is required")
        families = _families(self.changed_parameter_families)
        if len(families) > 2:
            raise CampaignError("each candidate may change only one or two parameter families")
        if not isinstance(self.parameter_values, Mapping) or not self.parameter_values:
            raise CampaignError("parameter_values must be a non-empty mapping")
        hashes = {str(key): _hash(value, label=str(key)) for key, value in self.input_hashes.items()}
        object.__setattr__(self, "changed_parameter_families", families)
        object.__setattr__(self, "parameter_values", MappingProxyType(dict(sorted(self.parameter_values.items()))))
        object.__setattr__(self, "input_hashes", MappingProxyType(dict(sorted(hashes.items()))))

    def _identity(self) -> dict[str, Any]:
        return {
            "campaign_manifest_sha256": self.campaign_manifest_sha256,
            "parent_candidate_id": self.parent_candidate_id,
            "changed_parameter_families": self.changed_parameter_families,
            "parameter_values": dict(self.parameter_values),
            "hypothesis": self.hypothesis,
            "input_hashes": dict(self.input_hashes),
        }

    @property
    def cache_key(self) -> str:
        return canonical_sha256(self._identity())

    @property
    def candidate_id(self) -> str:
        return f"cand_{self.cache_key[:16]}"

    def as_dict(self) -> dict[str, Any]:
        data = {
            "campaign_manifest_sha256": self.campaign_manifest_sha256,
            "ordinal": self.ordinal,
            "parent_candidate_id": self.parent_candidate_id,
            "changed_parameter_families": self.changed_parameter_families,
            "parameter_values": dict(self.parameter_values),
            "hypothesis": self.hypothesis,
            "input_hashes": dict(self.input_hashes),
        }
        data.update({"candidate_id": self.candidate_id, "cache_key": self.cache_key})
        return data


def validate_run_spec(spec: CampaignRunSpec, manifest: CampaignManifest, *, published_count: int = 0) -> None:
    """Verify candidate membership and enforce the campaign's non-negotiable cap."""
    if spec.campaign_manifest_sha256 != manifest.manifest_sha256:
        raise CampaignError("run spec belongs to a different campaign manifest")
    if spec.ordinal > manifest.max_runs or published_count >= manifest.max_runs:
        raise CampaignError(f"campaign run cap ({manifest.max_runs}) has been reached")
    unknown = sorted(set(spec.changed_parameter_families) - set(manifest.declared_parameter_families))
    if unknown:
        raise CampaignError(f"candidate references undeclared parameter families: {unknown}")
    for name, digest in manifest.input_hashes.items():
        if spec.input_hashes.get(name) != digest:
            raise CampaignError(f"candidate input hash differs from campaign contract: {name}")


@dataclass(frozen=True)
class RunAdmission:
    candidate_id: str
    admitted: bool
    reasons: tuple[str, ...]
    diagnostics_sha256: str


def admit_energyplus_run(spec: CampaignRunSpec, diagnostics: Mapping[str, Any]) -> RunAdmission:
    """Admit only a clean, hash-bound EnergyPlus inspection result."""
    reasons: list[str] = []
    if diagnostics.get("engine_smoke_passed") is not True:
        reasons.append("engine_smoke_not_passed")
    for name in ("process_returncode", "warning_count", "severe_count", "fatal_count"):
        if diagnostics.get(name) != 0:
            reasons.append(f"{name}_not_zero")
    required = diagnostics.get("required_evidence")
    if not isinstance(required, Mapping) or not all(bool(value) for value in required.values()):
        reasons.append("required_evidence_incomplete")
    input_hashes = diagnostics.get("input_hashes")
    if not isinstance(input_hashes, Mapping):
        reasons.append("diagnostic_input_hashes_missing")
    else:
        for name, digest in spec.input_hashes.items():
            if name in {"calibration_contract_sha256", "source_data_sha256", "point_map_sha256"}:
                continue
            if input_hashes.get(name) != digest:
                reasons.append(f"diagnostic_input_hash_mismatch:{name}")
    return RunAdmission(spec.candidate_id, not reasons, tuple(reasons), canonical_sha256(dict(diagnostics)))


def _read_log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    previous: str | None = None
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise CampaignError(f"campaign log has a blank line at {line_number}")
            row = json.loads(line)
            stored = row.pop("record_sha256", None)
            if stored != canonical_sha256(row):
                raise CampaignError(f"campaign log record hash mismatch at line {line_number}")
            if row.get("previous_record_sha256") != previous:
                raise CampaignError(f"campaign log chain mismatch at line {line_number}")
            row["record_sha256"] = stored
            previous = stored
            rows.append(row)
    return rows


def append_campaign_log(
    path: Path,
    *,
    manifest: CampaignManifest,
    spec: CampaignRunSpec,
    admission: RunAdmission,
    metrics: Mapping[str, float],
    gates: Mapping[str, bool],
) -> dict[str, Any]:
    """Append one immutable record after validating chain, membership, and budget."""
    path = Path(path)
    rows = _read_log(path)
    validate_run_spec(spec, manifest, published_count=len(rows))
    if any(row["candidate_id"] == spec.candidate_id for row in rows):
        raise CampaignError("candidate already exists in append-only campaign log")
    normalized_metrics: dict[str, float] = {}
    for key, value in metrics.items():
        numeric = float(value)
        if not math.isfinite(numeric):
            raise CampaignError(f"metric {key} must be finite")
        normalized_metrics[str(key)] = numeric
    if not gates or not all(isinstance(value, bool) for value in gates.values()):
        raise CampaignError("gates must be a non-empty mapping of booleans")
    record: dict[str, Any] = {
        "schema": "vibe23.calibration_campaign_log.v1",
        "campaign_manifest_sha256": manifest.manifest_sha256,
        "candidate_id": spec.candidate_id,
        "cache_key": spec.cache_key,
        "ordinal": spec.ordinal,
        "admission": asdict(admission),
        "metrics": dict(sorted(normalized_metrics.items())),
        "gates": dict(sorted(gates.items())),
        "previous_record_sha256": rows[-1]["record_sha256"] if rows else None,
    }
    record["record_sha256"] = canonical_sha256(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(descriptor, (_canonical(record) + "\n").encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return record


def select_champion(
    log_path: Path,
    *,
    required_metrics: Iterable[str],
    required_gates: Iterable[str],
    ranking_metrics: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Choose a deterministic champion only from admitted records meeting declared gates."""
    metrics = tuple(str(item) for item in required_metrics)
    gates = tuple(str(item) for item in required_gates)
    if not metrics or not gates:
        raise CampaignError("champion selection requires declared metrics and gates")
    rank = tuple(str(item) for item in (ranking_metrics or metrics))
    if set(rank) - set(metrics):
        raise CampaignError("ranking_metrics must be declared required_metrics")
    candidates: list[dict[str, Any]] = []
    for row in _read_log(Path(log_path)):
        values, checks = row.get("metrics", {}), row.get("gates", {})
        if not row.get("admission", {}).get("admitted"):
            continue
        if any(name not in values or not math.isfinite(float(values[name])) for name in metrics):
            continue
        if any(checks.get(name) is not True for name in gates):
            continue
        candidates.append(row)
    if not candidates:
        raise CampaignError("no admitted candidate meets all declared champion metrics and gates")
    winner = min(candidates, key=lambda row: tuple(float(row["metrics"][name]) for name in rank) + (row["candidate_id"],))
    return {
        "schema": "vibe23.calibration_champion.v1",
        "candidate_id": winner["candidate_id"],
        "record_sha256": winner["record_sha256"],
        "required_metrics": list(metrics),
        "required_gates": list(gates),
        "ranking_metrics": list(rank),
        "metrics": winner["metrics"],
        "gates": winner["gates"],
    }
