"""Slim Brick-compatible graph + CSV import helpers."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from mqtt_routing import building_scope, meta_device_id


def empty_graph(site_id: str, building_id: str) -> dict[str, Any]:
    scope = building_scope(site_id, building_id)
    return {
        "@context": {"brick": "https://brickschema.org/schema/Brick#", "ext": "https://vibe12.local/ext#"},
        "@id": f"brick:{scope}",
        "site_id": site_id,
        "building_id": building_id,
        "entities": [],
        "relationships": [],
    }


def site_entity(entity_id: str, site_id: str, building_id: str) -> dict[str, Any]:
    return {
        "@id": entity_id,
        "brick": "Site",
        "site_id": site_id,
        "building_id": building_id,
    }


def point_entity(
    *,
    entity_id: str,
    brick_class: str,
    series_id: str,
    unit: str = "",
    brick_tag: str = "",
    system_id: str = "",
    object_name: str = "",
    bacnet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ent = {
        "@id": entity_id,
        "brick": brick_class or "Point",
        "ext:series_id": series_id,
        "ext:unit": unit,
        "ext:tag": brick_tag,
        "system_id": system_id,
    }
    if object_name:
        ent["ext:object_name"] = object_name
    if bacnet:
        ent["bacnet"] = bacnet
    return ent


def equipment_entity(entity_id: str, brick_class: str, system_id: str) -> dict[str, Any]:
    return {
        "@id": entity_id,
        "brick": brick_class or "Equipment",
        "system_id": system_id,
    }


def add_relationship(graph: dict[str, Any], subj: str, pred: str, obj: str) -> None:
    graph.setdefault("relationships", []).append(
        {"subject": subj, "predicate": pred, "object": obj}
    )


def graph_from_point_registry(
    site_id: str,
    building_id: str,
    points: list[dict[str, Any]],
) -> dict[str, Any]:
    graph = empty_graph(site_id, building_id)
    site_id_entity = f"brick:{site_id}_{building_id}_site"
    graph["entities"].append(site_entity(site_id_entity, site_id, building_id))
    equipment_ids: dict[str, str] = {}

    for p in points:
        system_id = p.get("system_id") or "unknown"
        eq_key = system_id
        if eq_key not in equipment_ids:
            eq_id = f"brick:{site_id}_{building_id}_{system_id}"
            equipment_ids[eq_key] = eq_id
            graph["entities"].append(
                equipment_entity(eq_id, "HVAC_Equipment", system_id)
            )
            add_relationship(graph, site_id_entity, "hasPart", eq_id)
            add_relationship(graph, eq_id, "isPartOf", site_id_entity)

        tag = p.get("brick_tag") or p.get("point_id") or p.get("series_id", "")
        object_name = p.get("object_name") or ""
        pt_id = f"brick:{site_id}_{building_id}_{tag}"
        graph["entities"].append(
            point_entity(
                entity_id=pt_id,
                brick_class=p.get("brick_class") or "Sensor",
                series_id=p.get("series_id", ""),
                unit=p.get("unit", ""),
                brick_tag=tag,
                system_id=system_id,
                object_name=object_name,
                bacnet=p.get("bacnet_object"),
            )
        )
        add_relationship(graph, equipment_ids[eq_key], "hasPoint", pt_id)
        add_relationship(graph, site_id_entity, "hasPart", pt_id)
        add_relationship(graph, pt_id, "isPartOf", site_id_entity)

    return graph


def graph_from_csv_text(csv_text: str, site_id: str, building_id: str) -> dict[str, Any]:
    reader = csv.DictReader(io.StringIO(csv_text))
    points: list[dict[str, Any]] = []
    for row in reader:
        if str(row.get("enabled", "0")).strip().lower() not in ("1", "true", "yes"):
            continue
        sid = row.get("site_id") or site_id
        bid = row.get("building_id") or building_id
        sys_id = row.get("system_id") or "unknown"
        pt_id = row.get("point_id") or f"{row.get('device_instance')}-{row.get('object_type')}-{row.get('object_instance')}"
        series_id = row.get("series_id") or f"{sid}#{bid}#{sys_id}#{pt_id}"
        points.append(
            {
                "site_id": sid,
                "building_id": bid,
                "system_id": sys_id,
                "point_id": pt_id,
                "series_id": series_id,
                "brick_class": row.get("brick_class", ""),
                "brick_tag": row.get("brick_tag", ""),
                "unit": row.get("units", ""),
                "object_name": row.get("object_name", ""),
            }
        )
    return graph_from_point_registry(site_id, building_id, points)


def entities_by_brick_class(graph: dict[str, Any], brick_class: str) -> list[dict[str, Any]]:
    return [e for e in graph.get("entities", []) if e.get("brick") == brick_class]


def series_ids_for_aliases(graph: dict[str, Any], aliases: dict[str, str]) -> dict[str, str]:
    """Map rule alias → series_id using ext:tag or @id suffix."""
    by_tag: dict[str, str] = {}
    for ent in graph.get("entities", []):
        sid = ent.get("ext:series_id")
        if not sid:
            continue
        tag = ent.get("ext:tag") or ent.get("@id", "").split("_")[-1]
        if tag:
            by_tag[str(tag).upper()] = sid
    out: dict[str, str] = {}
    for alias, key in (aliases or {}).items():
        out[alias] = by_tag.get(str(key).upper(), key)
    return out


def graph_to_json(graph: dict[str, Any]) -> str:
    return json.dumps(graph)


def graph_from_json(raw: str | dict) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return json.loads(raw)


def meta_key(site_id: str, building_id: str) -> dict[str, Any]:
    return {"device_id": meta_device_id(site_id, building_id), "ts_ms": -10}
