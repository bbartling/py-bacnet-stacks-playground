"""Pydantic schemas for canonical BRICK data model (open-fdd compatible)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

BRICK_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class SiteRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None
    name: str = "Site"
    metadata: dict[str, Any] | None = None


class EquipmentRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None
    site_id: str | None = None
    name: str = "Equipment"
    equipment_type: str = "Equipment"
    metadata: dict[str, Any] | None = None


class PointRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None
    site_id: str | None = None
    equipment_id: str | None = None
    external_id: str | None = None
    brick_type: str | None = None
    fdd_input: str | None = None
    unit: str | None = None
    metadata: dict[str, Any] | None = None


class RelationshipRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    subject: str
    predicate: str
    object: str


class ModelPayload(BaseModel):
    sites: list[SiteRecord] = Field(default_factory=list)
    equipment: list[EquipmentRecord] = Field(default_factory=list)
    points: list[PointRecord] = Field(default_factory=list)
    relationships: list[RelationshipRecord] = Field(default_factory=list)


class ModelValidateBody(BaseModel):
    payload: ModelPayload


class ModelImportBody(BaseModel):
    payload: ModelPayload
    replace: bool = True


def _sanitize_brick_token(value: str | None, fallback: str = "Point") -> str:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "").strip())
    token = re.sub(r"_+", "_", token).strip("_")
    if not token:
        return fallback
    if token[0].isdigit():
        token = f"_{token}"
    return token


def normalize_model_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize lists and Brick tokens before save."""
    sites = raw.get("sites", []) if isinstance(raw.get("sites"), list) else []
    equipment = raw.get("equipment", []) if isinstance(raw.get("equipment"), list) else []
    points = raw.get("points", []) if isinstance(raw.get("points"), list) else []
    relationships = raw.get("relationships", []) if isinstance(raw.get("relationships"), list) else []
    out_eq: list[dict[str, Any]] = []
    for eq in equipment:
        if not isinstance(eq, dict):
            continue
        row = dict(eq)
        row["equipment_type"] = _sanitize_brick_token(row.get("equipment_type"), "Equipment")
        out_eq.append(row)
    out_pts: list[dict[str, Any]] = []
    for pt in points:
        if not isinstance(pt, dict):
            continue
        row = dict(pt)
        row["brick_type"] = _sanitize_brick_token(row.get("brick_type"), "Point")
        if not row.get("fdd_input"):
            row["fdd_input"] = row["brick_type"]
        out_pts.append(row)
    return {
        "sites": [s for s in sites if isinstance(s, dict)],
        "equipment": out_eq,
        "points": out_pts,
        "relationships": [r for r in relationships if isinstance(r, dict)],
    }


def validate_model(
    payload: dict[str, Any],
    *,
    registry_series_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Pydantic parse + FK + telemetry linkage + health score."""
    issues: list[str] = []
    try:
        normalized = normalize_model_payload(payload)
        ModelPayload.model_validate(normalized)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", ()))
            issues.append(f"pydantic:{loc}: {err.get('msg', 'invalid')}")
        normalized = normalize_model_payload(payload)
    except Exception as exc:  # noqa: BLE001
        issues.append(f"parse_error: {exc}")
        normalized = normalize_model_payload(payload if isinstance(payload, dict) else {})

    sites = normalized.get("sites", [])
    equipment = normalized.get("equipment", [])
    points = normalized.get("points", [])

    site_ids = {str(s.get("id")) for s in sites if isinstance(s, dict) and s.get("id")}
    equipment_ids = {str(e.get("id")) for e in equipment if isinstance(e, dict) and e.get("id")}

    orphan_equipment = 0
    orphan_points_site = 0
    orphan_points_equipment = 0
    missing_brick_type = 0
    missing_fdd_input = 0
    missing_external_ref = 0
    unregistered_external_ref = 0
    invalid_brick_token = 0
    duplicate_map: dict[tuple[str, str, str], int] = {}
    equipment_with_zero_points: set[str] = set(equipment_ids)

    for idx, eq in enumerate(equipment):
        if not isinstance(eq, dict):
            continue
        et = str(eq.get("equipment_type") or "")
        if et and not BRICK_TOKEN_RE.match(et):
            invalid_brick_token += 1
            issues.append(f"equipment[{idx}] invalid equipment_type token: {et}")
        sid = eq.get("site_id")
        if sid and str(sid) not in site_ids:
            orphan_equipment += 1
            issues.append(f"equipment[{idx}] references missing site_id={sid}")

    for idx, pt in enumerate(points):
        if not isinstance(pt, dict):
            continue
        sid = pt.get("site_id")
        eqid = pt.get("equipment_id")
        if sid and str(sid) not in site_ids:
            orphan_points_site += 1
            issues.append(f"points[{idx}] references missing site_id={sid}")
        if eqid:
            if str(eqid) not in equipment_ids:
                orphan_points_equipment += 1
                issues.append(f"points[{idx}] references missing equipment_id={eqid}")
            else:
                equipment_with_zero_points.discard(str(eqid))
        bt = str(pt.get("brick_type") or "").strip()
        if not bt:
            missing_brick_type += 1
            issues.append(f"points[{idx}] missing brick_type")
        elif not BRICK_TOKEN_RE.match(bt):
            invalid_brick_token += 1
            issues.append(f"points[{idx}] invalid brick_type token: {bt}")
        if not str(pt.get("fdd_input") or "").strip():
            missing_fdd_input += 1
        meta = pt.get("metadata") if isinstance(pt.get("metadata"), dict) else {}
        ext_ref = str(meta.get("external_ref") or "").strip()
        if not ext_ref:
            missing_external_ref += 1
            issues.append(f"points[{idx}] missing metadata.external_ref (series_id)")
        elif registry_series_ids is not None and ext_ref not in registry_series_ids:
            unregistered_external_ref += 1
            issues.append(f"points[{idx}] external_ref not in point registry: {ext_ref}")
        key = (
            str(pt.get("site_id") or ""),
            str(pt.get("equipment_id") or ""),
            str(pt.get("external_id") or ""),
        )
        duplicate_map[key] = duplicate_map.get(key, 0) + 1

    duplicate_external_ids = sum(1 for count in duplicate_map.values() if count > 1)
    empty_equipment = len(equipment_with_zero_points)

    critical = orphan_equipment + orphan_points_site + orphan_points_equipment
    warning = (
        missing_brick_type
        + missing_fdd_input
        + duplicate_external_ids
        + missing_external_ref
        + unregistered_external_ref
        + invalid_brick_token
        + empty_equipment
    )
    score = max(0, 100 - (critical * 10) - (warning * 2))

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "score": score,
        "counts": {
            "sites": len(sites),
            "equipment": len(equipment),
            "points": len(points),
            "orphan_equipment": orphan_equipment,
            "orphan_points_site": orphan_points_site,
            "orphan_points_equipment": orphan_points_equipment,
            "missing_brick_type": missing_brick_type,
            "missing_fdd_input": missing_fdd_input,
            "duplicate_external_ids": duplicate_external_ids,
            "missing_external_ref": missing_external_ref,
            "unregistered_external_ref": unregistered_external_ref,
            "invalid_brick_token": invalid_brick_token,
            "equipment_with_zero_points": empty_equipment,
        },
        "summary": (
            f"Health score={score}; critical={critical}; warnings={warning}. "
            "Check orphan links, missing BRICK/FDD mappings, external_ref linkage, and duplicates."
        ),
    }
