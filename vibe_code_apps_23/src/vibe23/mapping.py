"""Explicit, provenance-bearing point bindings for Vibe 23 exports.

This module deliberately does *not* infer point names from CSV headers.  The
Building 59 source contains many similarly named telemetry streams and an
incorrect but plausible FDD map is worse than no map.  A human must bind every
exported point in a versioned JSON mapping after reviewing source metadata.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAPPING_SCHEMA = "vibe23_openfdd_mapping_v1"
BUILDING59_DATASET_DOI = "10.7941/D1N33Q"
# Matches the current public Rust package importer: one safe path component
# using ASCII alphanumeric, hyphen, or underscore.  Do not accept a name the
# downstream importer will later skip.
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_ALLOWED_EQUIPMENT_TYPES = {"ahu", "vav", "chwPlant", "boiler", "heatPump"}


class MappingValidationError(ValueError):
    """The proposed export is incomplete, ambiguous, or unsafe to author."""


def sha256_file(path: Path) -> str:
    """Return the byte-level SHA-256 of a source or generated artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MappingValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _require_bool(value: Any, field: str, *, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise MappingValidationError(f"{field} must be a JSON boolean")
    return value


def _safe_id(value: Any, field: str) -> str:
    result = _require_string(value, field)
    if not _SAFE_ID.fullmatch(result):
        raise MappingValidationError(f"{field} contains unsupported characters: {result!r}")
    return result


def _relative_file(value: Any, field: str) -> str:
    result = _require_string(value, field).replace("\\", "/")
    path = Path(result)
    if path.is_absolute() or ".." in path.parts or not result or result.startswith("/"):
        raise MappingValidationError(f"{field} must be a relative path inside raw_root")
    return path.as_posix()


def _iana_timezone(value: Any, field: str) -> str:
    result = _require_string(value, field)
    try:
        ZoneInfo(result)
    except ZoneInfoNotFoundError as exc:
        raise MappingValidationError(f"{field} is not an IANA timezone: {result!r}") from exc
    return result


@dataclass(frozen=True)
class PointBinding:
    """One positively identified source column and its Open-FDD point name."""

    haystack_point: str
    source_column: str
    units: str
    evidence: str
    allow_nulls: bool = False

    @classmethod
    def from_dict(cls, value: Any, *, context: str) -> "PointBinding":
        if not isinstance(value, dict):
            raise MappingValidationError(f"{context} must be an object")
        return cls(
            haystack_point=_safe_id(value.get("haystack_point"), f"{context}.haystack_point"),
            source_column=_require_string(value.get("source_column"), f"{context}.source_column"),
            units=_require_string(value.get("units"), f"{context}.units"),
            evidence=_require_string(value.get("evidence"), f"{context}.evidence"),
            allow_nulls=_require_bool(value.get("allow_nulls"), f"{context}.allow_nulls"),
        )


@dataclass(frozen=True)
class EquipmentBinding:
    equipment_id: str
    equip_type: str
    source_file: str
    timestamp_column: str
    source_timezone: str
    points: tuple[PointBinding, ...]

    @classmethod
    def from_dict(cls, value: Any, *, index: int) -> "EquipmentBinding":
        context = f"equipment[{index}]"
        if not isinstance(value, dict):
            raise MappingValidationError(f"{context} must be an object")
        equip_type = _require_string(value.get("equip_type"), f"{context}.equip_type")
        if equip_type not in _ALLOWED_EQUIPMENT_TYPES:
            raise MappingValidationError(
                f"{context}.equip_type must be one of {sorted(_ALLOWED_EQUIPMENT_TYPES)}; "
                "weather must be supplied separately, not relabeled as web weather"
            )
        raw_points = value.get("points")
        if not isinstance(raw_points, list) or not raw_points:
            raise MappingValidationError(f"{context}.points must be a non-empty list of verified bindings")
        points = tuple(PointBinding.from_dict(item, context=f"{context}.points[{i}]") for i, item in enumerate(raw_points))
        point_names = [item.haystack_point for item in points]
        source_columns = [item.source_column for item in points]
        if len(point_names) != len(set(point_names)):
            raise MappingValidationError(f"{context} maps a Haystack point more than once")
        if len(source_columns) != len(set(source_columns)):
            raise MappingValidationError(f"{context} maps one source column to multiple points")
        return cls(
            equipment_id=_safe_id(value.get("equipment_id"), f"{context}.equipment_id"),
            equip_type=equip_type,
            source_file=_relative_file(value.get("source_file"), f"{context}.source_file"),
            timestamp_column=_require_string(value.get("timestamp_column"), f"{context}.timestamp_column"),
            source_timezone=_iana_timezone(value.get("source_timezone"), f"{context}.source_timezone"),
            points=points,
        )


@dataclass(frozen=True)
class OpenFddMapping:
    """Complete, explicit contract for one Open-FDD package export."""

    building_id: str
    grid_minutes: int
    dataset_doi: str
    acquisition_manifest_sha256: str
    mapping_evidence: str
    equipment: tuple[EquipmentBinding, ...]

    @classmethod
    def from_dict(cls, value: Any) -> "OpenFddMapping":
        if not isinstance(value, dict):
            raise MappingValidationError("mapping document must be a JSON object")
        if value.get("schema_version") != MAPPING_SCHEMA:
            raise MappingValidationError(f"schema_version must be {MAPPING_SCHEMA!r}")
        grid_minutes = value.get("grid_minutes")
        if isinstance(grid_minutes, bool) or not isinstance(grid_minutes, int) or not 1 <= grid_minutes <= 60:
            raise MappingValidationError("grid_minutes must be an integer from 1 through 60")
        acquisition_hash = _require_string(value.get("acquisition_manifest_sha256"), "acquisition_manifest_sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", acquisition_hash):
            raise MappingValidationError("acquisition_manifest_sha256 must be a lowercase SHA-256")
        raw_equipment = value.get("equipment")
        if not isinstance(raw_equipment, list) or not raw_equipment:
            raise MappingValidationError("equipment must be a non-empty list")
        equipment = tuple(EquipmentBinding.from_dict(item, index=i) for i, item in enumerate(raw_equipment))
        ids = [item.equipment_id for item in equipment]
        if len(ids) != len(set(ids)):
            raise MappingValidationError("equipment_id values must be unique")
        dataset_doi = _require_string(value.get("dataset_doi"), "dataset_doi")
        if dataset_doi != BUILDING59_DATASET_DOI:
            raise MappingValidationError(f"dataset_doi must be {BUILDING59_DATASET_DOI!r}")
        return cls(
            building_id=_safe_id(value.get("building_id"), "building_id"),
            grid_minutes=grid_minutes,
            dataset_doi=dataset_doi,
            acquisition_manifest_sha256=acquisition_hash,
            mapping_evidence=_require_string(value.get("mapping_evidence"), "mapping_evidence"),
            equipment=equipment,
        )


def load_mapping(path: Path) -> OpenFddMapping:
    """Load a JSON mapping; YAML and heuristic/inferred mappings are rejected."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MappingValidationError(f"Invalid mapping JSON: {path}: {exc}") from exc
    return OpenFddMapping.from_dict(raw)
