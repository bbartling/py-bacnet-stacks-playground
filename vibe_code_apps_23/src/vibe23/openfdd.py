"""Build provenance-rich ``openfdd_package_v1`` historian adapter bundles.

The adapter is intentionally narrow: it creates an importable package only from
an explicit Vibe 23 mapping.  It never guesses Building 59 point names, never
fills gaps, and never converts a naive timestamp without the mapping's declared
IANA timezone.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from .mapping import EquipmentBinding, MappingValidationError, OpenFddMapping, load_mapping, sha256_file

ADAPTER_SCHEMA = "vibe23_openfdd_adapter_v1"
PACKAGE_SCHEMA = "openfdd_package_v1"


def _resolve_source(raw_root: Path, relative_path: str) -> Path:
    root = raw_root.resolve()
    source = (root / relative_path).resolve()
    if source != root and root not in source.parents:
        raise MappingValidationError(f"Source path escapes raw_root: {relative_path!r}")
    if not source.is_file():
        raise FileNotFoundError(f"Mapped source CSV does not exist: {source}")
    return source


def _canonical_timestamp(series: pd.Series, timezone: str, *, context: str) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", format="mixed")
    if parsed.isna().any():
        raise MappingValidationError(f"{context}: {int(parsed.isna().sum())} timestamps cannot be parsed")
    index = pd.DatetimeIndex(parsed)
    try:
        if index.tz is None:
            # Ambiguous/nonexistent local time is a data issue requiring an explicit
            # resolution ledger entry; do not silently choose an occurrence around DST.
            index = index.tz_localize(timezone, ambiguous="raise", nonexistent="raise")
        index = index.tz_convert("UTC")
    except (TypeError, ValueError) as exc:
        raise MappingValidationError(f"{context}: timezone/DST conversion failed: {exc}") from exc
    if index.has_duplicates:
        raise MappingValidationError(f"{context}: duplicate timestamps after UTC normalization")
    if not index.is_monotonic_increasing:
        raise MappingValidationError(
            f"{context}: timestamps are not strictly chronological; fix source ordering explicitly"
        )
    return pd.Series(index.strftime("%Y-%m-%dT%H:%M:%SZ"), index=series.index, name="timestamp_utc")


def _median_interval_minutes(timestamp_utc: pd.Series) -> float | None:
    if len(timestamp_utc) < 2:
        return None
    parsed = pd.DatetimeIndex(pd.to_datetime(timestamp_utc, utc=True))
    values = pd.Series(parsed[1:] - parsed[:-1]).dt.total_seconds() / 60.0
    return float(values.median())


def _write_equipment(binding: EquipmentBinding, source: Path, package_root: Path) -> dict[str, Any]:
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise MappingValidationError(f"Could not read {source}: {type(exc).__name__}: {exc}") from exc
    requested = [binding.timestamp_column, *(point.source_column for point in binding.points)]
    missing = [column for column in requested if column not in frame.columns]
    if missing:
        raise MappingValidationError(f"{binding.equipment_id}: mapped columns not found in {source.name}: {missing}")
    if frame.empty:
        raise MappingValidationError(f"{binding.equipment_id}: source CSV has no rows")
    out = frame.loc[:, requested].copy()
    out.insert(0, "timestamp_utc", _canonical_timestamp(out.pop(binding.timestamp_column), binding.source_timezone, context=binding.equipment_id))
    for point in binding.points:
        nulls = int(out[point.source_column].isna().sum())
        if nulls and not point.allow_nulls:
            raise MappingValidationError(
                f"{binding.equipment_id}.{point.source_column}: {nulls} null values; "
                "set allow_nulls only with a documented quality decision"
            )
    equipment_dir = package_root / binding.equipment_id
    equipment_dir.mkdir(parents=True, exist_ok=False)
    history = equipment_dir / "history_wide.csv"
    out.to_csv(history, index=False, lineterminator="\n")
    points = {point.haystack_point: point.source_column for point in binding.points}
    sidecar = {
        "equipType": binding.equip_type,
        "equipment_type": binding.equip_type,
        "device": binding.equipment_id,
        "points": points,
        "generated_by": ADAPTER_SCHEMA,
        "notes": "Explicit Vibe 23 source bindings only; see root VIBE23_OPENFDD_ADAPTER.json for units and provenance.",
    }
    (equipment_dir / "history_wide.json").write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Do not ship ``columns.csv`` here. It is optional in openfdd_package_v1 and
    # each Open-FDD importer generates its own normalized ``column,role`` file
    # from the Haystack sidecar. Units/evidence remain in the versioned root
    # adapter ledger instead of being squeezed into a non-contract CSV shape.
    return {
        "equipment_id": binding.equipment_id,
        "equip_type": binding.equip_type,
        "source_file": binding.source_file,
        "source_sha256": sha256_file(source),
        "source_rows": len(frame),
        "export_rows": len(out),
        "timestamp_column": binding.timestamp_column,
        "source_timezone": binding.source_timezone,
        "timestamp_utc_first": out["timestamp_utc"].iloc[0],
        "timestamp_utc_last": out["timestamp_utc"].iloc[-1],
        "median_interval_minutes": _median_interval_minutes(out["timestamp_utc"]),
        "history_wide_sha256": sha256_file(history),
        "points": [asdict(point) for point in binding.points],
    }


def _mapping_hash(path: Path) -> str:
    # Hash original bytes rather than a parsed/reformatted mapping document.
    return sha256_file(path)


def _safe_zip(package_root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    if partial.exists():
        partial.unlink()
    try:
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(package_root.rglob("*")):
                if not path.is_file():
                    continue
                archive.write(path, path.relative_to(package_root.parent).as_posix())
        os.replace(partial, destination)
    finally:
        if partial.exists():
            partial.unlink()


def build_openfdd_package(mapping_path: Path, raw_root: Path, output_zip: Path) -> dict[str, Any]:
    """Build a package compatible with the current public Open-FDD zip import.

    The returned report is also written inside the zip.  The package has no
    invented weather, roles, equipment topology, value filling, unit conversion,
    or inferred point mappings.
    """
    mapping_path = mapping_path.resolve()
    mapping: OpenFddMapping = load_mapping(mapping_path)
    if output_zip.suffix.lower() != ".zip":
        raise ValueError("output_zip must end in .zip")
    raw_root = Path(raw_root).resolve()
    output_zip = output_zip.resolve()
    if output_zip == raw_root or raw_root in output_zip.parents:
        raise MappingValidationError("output_zip must be outside immutable raw_root")
    sources = {binding.source_file: _resolve_source(raw_root, binding.source_file) for binding in mapping.equipment}
    # Refuse to overwrite a raw input regardless of a coincidental requested name.
    if output_zip in {path.resolve() for path in sources.values()}:
        raise MappingValidationError("output_zip must not overwrite a mapped raw source")

    with tempfile.TemporaryDirectory(prefix="vibe23-openfdd-") as temporary:
        package_root = Path(temporary) / mapping.building_id
        package_root.mkdir()
        manifest = {
            "schema_version": PACKAGE_SCHEMA,
            "building_id": mapping.building_id,
            "grid_minutes": mapping.grid_minutes,
            "timezone": "UTC",
            "notes": "Vibe 23 explicit source adapter; units and source hashes in VIBE23_OPENFDD_ADAPTER.json.",
        }
        (package_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        exports = [_write_equipment(binding, sources[binding.source_file], package_root) for binding in mapping.equipment]
        adapter = {
            "schema_version": ADAPTER_SCHEMA,
            "openfdd_package_schema": PACKAGE_SCHEMA,
            "building_id": mapping.building_id,
            "dataset_doi": mapping.dataset_doi,
            "acquisition_manifest_sha256": mapping.acquisition_manifest_sha256,
            "mapping_sha256": _mapping_hash(mapping_path),
            "mapping_evidence": mapping.mapping_evidence,
            "transformations": [
                "selected explicitly bound source columns",
                "localized declared source timezone to UTC without value conversion",
                "wrote RFC3339 timestamp_utc",
            ],
            "not_performed": [
                "point-name inference",
                "unit conversion",
                "gap filling",
                "resampling",
                "weather synthesis",
                "topology inference",
            ],
            "exports": exports,
        }
        adapter_path = package_root / "VIBE23_OPENFDD_ADAPTER.json"
        adapter_path.write_text(json.dumps(adapter, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _safe_zip(package_root, output_zip)
    report = dict(adapter)
    report["output_zip"] = str(output_zip)
    report["output_zip_sha256"] = sha256_file(output_zip)
    return report
