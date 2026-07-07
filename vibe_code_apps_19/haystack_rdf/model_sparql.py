"""Domain SPARQL helpers for dashboard integration."""

from __future__ import annotations

from typing import Any

from .namespaces import PREFIXES_SPARQL
from .ttl_graph import TtlGraphError, load_graph, local_name, run_sparql
from .ttl_service import TtlService


def _list_equipment_from_json(
    ttl: TtlService | None,
    *,
    haystack_tag: str | None = None,
) -> list[dict[str, str]]:
    svc = ttl or TtlService()
    model = svc.model_store.load()
    out: list[dict[str, str]] = []
    for eq in model.get("equipment") or []:
        if not isinstance(eq, dict):
            continue
        tag = str(eq.get("haystack_tag") or "").lower()
        if haystack_tag and tag != haystack_tag.lower():
            continue
        eq_id = str(eq.get("id") or "")
        if not eq_id:
            continue
        out.append(
            {
                "id": eq_id,
                "label": str(eq.get("name") or eq_id),
                "history_subdir": str(eq.get("history_subdir") or eq_id),
            }
        )
    return out


def list_equipment(ttl: TtlService | None = None, *, haystack_tag: str | None = None) -> list[dict[str, str]]:
    """Prefer model.json (fast); SPARQL only when JSON catalog is empty."""
    from_json = _list_equipment_from_json(ttl, haystack_tag=haystack_tag)
    if from_json:
        return from_json
    try:
        tag_filter = f", ph:{haystack_tag}" if haystack_tag else ""
        query = f"""{PREFIXES_SPARQL}
SELECT ?equipment ?label ?history_subdir WHERE {{
  ?equipment a ph:equip{tag_filter} .
  OPTIONAL {{ ?equipment rdfs:label ?label . }}
  OPTIONAL {{ ?equipment ofdd:historySubdir ?history_subdir . }}
}}
ORDER BY ?equipment"""
        graph = load_graph(ttl or TtlService())
        rows = run_sparql(graph, query)
        out: list[dict[str, str]] = []
        for row in rows:
            eq_uri = row.get("equipment", "")
            eq_id = local_name(eq_uri, "eq")
            out.append(
                {
                    "id": eq_id,
                    "label": row.get("label") or eq_id,
                    "history_subdir": row.get("history_subdir") or eq_id,
                }
            )
        if out:
            return out
    except (TtlGraphError, Exception):
        pass
    return from_json


def column_for_role(
    equipment_id: str,
    role: str,
    ttl: TtlService | None = None,
) -> str | None:
    """Resolve historian column for equipment + logical role via SPARQL."""
    eq_local = equipment_id.replace(":", "_")
    safe_role = role.replace('"', "")
    query = f"""{PREFIXES_SPARQL}
SELECT ?column WHERE {{
  :eq_{eq_local} a ph:equip .
  ?point ph:equipRef :eq_{eq_local} .
  {{ ?point ofdd:pointRole "{safe_role}" . }} UNION {{ ?point ofdd:mapsToRuleInput "{safe_role}" . }}
  ?point ofdd:timeseriesColumn ?column .
}}
LIMIT 1"""
    graph = load_graph(ttl or TtlService())
    rows = run_sparql(graph, query)
    if rows:
        return rows[0].get("column") or None
    return None


def resolve_equipment_columns(
    equipment_id: str,
    logical_keys: list[str],
    ttl: TtlService | None = None,
) -> dict[str, str | None]:
    return {key: column_for_role(equipment_id, key, ttl=ttl) for key in logical_keys}


def query_model_summary(ttl: TtlService | None = None) -> dict[str, Any]:
    graph = load_graph(ttl or TtlService())
    counts: dict[str, int] = {}
    for tag, key in (("ahu", "ahus"), ("vav", "vavs"), ("chiller", "chillers"), ("point", "points")):
        q = f"""{PREFIXES_SPARQL}
SELECT (COUNT(?x) AS ?count) WHERE {{ ?x a ph:{tag} . }}"""
        rows = run_sparql(graph, q)
        counts[key] = int(rows[0].get("count", "0")) if rows else 0
    return counts
