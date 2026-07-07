"""AI commissioning export/import (Haystack model + FDD point bindings)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

LLM_COMMISSIONING_PROMPT = """You are an HVAC commissioning assistant editing a Haystack RDF commissioning bundle.

The JSON contains:
- sites, equipment, points (with point_role, timeseries_column, mapsToRuleInput / fdd_input)
- fdd_rules: logical FDD inputs bound to point ids

Rules:
1. Preserve point id, timeseries_column (historian column), and equipment_id unless intentionally remapping.
2. Use Haystack tags on equipment: ahu, vav, chiller, boiler, site.
3. Set feeds[] on AHU equipment for VAV children when topology is known.
4. Respond with a single JSON object: { "sites", "equipment", "points", "fdd_rules" } ready for POST /api/rdf/commissioning-import.
5. Do not invent historian columns — only use columns present in the export or mark point as not_available.
"""


def _infer_fdd_rules(model: dict[str, Any]) -> list[dict[str, Any]]:
    """Build rule bindings from mapsToRuleInput / fdd_input on points."""
    by_rule: dict[str, dict[str, Any]] = {}
    for pt in model.get("points") or []:
        if not isinstance(pt, dict):
            continue
        rid = str(pt.get("fdd_input") or pt.get("mapsToRuleInput") or "").strip()
        if not rid:
            continue
        entry = by_rule.setdefault(
            rid,
            {
                "id": rid,
                "name": rid.replace("_", " ").title(),
                "enabled": True,
                "bindings": {"point_ids": [], "equipment_ids": [], "brick_types": []},
            },
        )
        pid = str(pt.get("id") or "").strip()
        eid = str(pt.get("equipment_id") or "").strip()
        if pid and pid not in entry["bindings"]["point_ids"]:
            entry["bindings"]["point_ids"].append(pid)
        if eid and eid not in entry["bindings"]["equipment_ids"]:
            entry["bindings"]["equipment_ids"].append(eid)
    return sorted(by_rule.values(), key=lambda r: r["id"])


def _rules_by_point(rules: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for rule in rules:
        rid = str(rule.get("id") or "").strip()
        if not rid:
            continue
        bindings = rule.get("bindings") if isinstance(rule.get("bindings"), dict) else {}
        for pid in bindings.get("point_ids") or []:
            p = str(pid).strip()
            if p and rid not in out[p]:
                out[p].append(rid)
    return out


def build_commissioning_export(model: dict[str, Any]) -> dict[str, Any]:
    rules = _infer_fdd_rules(model)
    if isinstance(model.get("fdd_rules"), list) and model["fdd_rules"]:
        rules = list(model["fdd_rules"])
    by_point = _rules_by_point(rules)
    rule_names = {str(r["id"]): str(r.get("name") or r["id"]) for r in rules}
    points: list[dict[str, Any]] = []
    for pt in model.get("points") or []:
        if not isinstance(pt, dict):
            continue
        row = dict(pt)
        pid = str(pt.get("id") or "").strip()
        bound = sorted(by_point.get(pid, []))
        if bound:
            row["fdd_rule_ids"] = bound
            row["fdd_rules_linked"] = [{"id": x, "name": rule_names.get(x, x)} for x in bound]
        points.append(row)
    return {
        "version": model.get("version", 1),
        "sites": list(model.get("sites") or []),
        "equipment": list(model.get("equipment") or []),
        "points": points,
        "fdd_rules": rules,
    }


def apply_commissioning_import(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize commissioning payload → model.json shape."""
    points = []
    for pt in payload.get("points") or []:
        if not isinstance(pt, dict):
            continue
        row = dict(pt)
        row.pop("fdd_rule_ids", None)
        row.pop("fdd_rules_linked", None)
        points.append(row)
    model = {
        "version": payload.get("version", 1),
        "sites": list(payload.get("sites") or []),
        "equipment": list(payload.get("equipment") or []),
        "points": points,
    }
    if isinstance(payload.get("fdd_rules"), list):
        model["fdd_rules"] = list(payload["fdd_rules"])
    return model


def build_llm_bundle(model: dict[str, Any]) -> str:
    import json

    bundle = build_commissioning_export(model)
    return (
        f"{LLM_COMMISSIONING_PROMPT.strip()}\n\n---\n"
        f"CURRENT haystack-commissioning.json:\n\n```json\n"
        f"{json.dumps(bundle, indent=2)}\n```\n"
    )
