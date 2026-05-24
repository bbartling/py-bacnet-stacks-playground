"""Expand BRICK class scopes into concrete evaluation targets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TargetBundle:
    target_id: str
    equipment: dict[str, Any]
    point: dict[str, Any]
    series_id: str
    series_aliases: dict[str, str] = field(default_factory=dict)
    required_series_ids: list[str] = field(default_factory=list)
    primary_series_id: str = ""


def _point_series_id(point: dict[str, Any]) -> str:
    meta = point.get("metadata") if isinstance(point.get("metadata"), dict) else {}
    return str(meta.get("external_ref") or "").strip()


def _equipment_by_id(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for eq in model.get("equipment", []):
        if isinstance(eq, dict) and eq.get("id"):
            out[str(eq["id"])] = eq
    return out


def _resolve_alias_to_series_id(model: dict[str, Any], alias_value: str) -> str | None:
    """Resolve alias key (brick_type tag or external_id) to series_id."""
    key = str(alias_value).strip()
    if not key:
        return None
    if "#" in key and len(key.split("#")) >= 3:
        return key
    key_upper = key.upper()
    for pt in model.get("points", []):
        if not isinstance(pt, dict):
            continue
        ext = str(pt.get("external_id") or "").upper()
        bt = str(pt.get("brick_type") or "").upper()
        fdd = str(pt.get("fdd_input") or "").upper()
        if key_upper in (ext, bt, fdd):
            sid = _point_series_id(pt)
            if sid:
                return sid
    return None


def expand_brick_targets(model: dict[str, Any], brick_scope: dict[str, Any]) -> list[TargetBundle]:
    """
    Expand brick_scope into evaluation targets.

    brick_scope keys:
      equipment_classes: list[str]
      point_classes: list[str]
      match_mode: "all_points_on_equipment" | "point_only" (default all_points_on_equipment)
      series_aliases: optional dict alias -> brick_type|external_id|series_id
    """
    if not brick_scope:
        return []

    eq_classes = {str(x) for x in (brick_scope.get("equipment_classes") or []) if x}
    pt_classes = {str(x) for x in (brick_scope.get("point_classes") or []) if x}
    match_mode = str(brick_scope.get("match_mode") or "all_points_on_equipment")
    extra_aliases = brick_scope.get("series_aliases") or {}

    eq_map = _equipment_by_id(model)
    targets: list[TargetBundle] = []

    for pt in model.get("points", []):
        if not isinstance(pt, dict):
            continue
        bt = str(pt.get("brick_type") or "")
        if pt_classes and bt not in pt_classes:
            continue
        eqid = str(pt.get("equipment_id") or "")
        eq = eq_map.get(eqid) if eqid else None
        if match_mode != "point_only" and eq_classes:
            if eq is None:
                continue
            et = str(eq.get("equipment_type") or "")
            if et not in eq_classes:
                continue
        series_id = _point_series_id(pt)
        if not series_id:
            continue

        eq_type = str(eq.get("equipment_type") or "") if eq else ""
        ext_id = str(pt.get("external_id") or pt.get("id") or "")
        target_id = f"{eqid}_{ext_id}" if eqid else ext_id

        aliases: dict[str, str] = {
            bt: series_id,
            ext_id: series_id,
        }
        fdd = str(pt.get("fdd_input") or "")
        if fdd:
            aliases[fdd] = series_id

        required = {series_id}
        for alias_key, alias_val in extra_aliases.items():
            resolved = _resolve_alias_to_series_id(model, str(alias_val))
            if resolved:
                aliases[str(alias_key)] = resolved
                required.add(resolved)

        targets.append(
            TargetBundle(
                target_id=target_id,
                equipment=eq or {},
                point=pt,
                series_id=series_id,
                series_aliases=aliases,
                required_series_ids=sorted(required),
                primary_series_id=series_id,
            )
        )

    return targets


def rules_with_brick_scope(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rules if isinstance(r, dict) and r.get("brick_scope")]
