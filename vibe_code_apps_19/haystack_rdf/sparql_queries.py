"""Predefined Haystack SPARQL catalog — full port from Open-FDD py (Brick → Haystack)."""

from __future__ import annotations

import re
from typing import Any

from .namespaces import OFDD, PH, PREFIXES_SPARQL, RDFS
from .ttl_graph import load_graph, run_sparql
from .ttl_service import TtlService

MAX_SPARQL_ROWS = 5000

_FORBIDDEN_FORMS = frozenset(
    {"INSERT", "DELETE", "UPDATE", "LOAD", "CLEAR", "DROP", "CREATE", "MOVE", "COPY", "ADD"}
)
_READONLY_FORMS = frozenset({"SELECT", "ASK", "DESCRIBE", "CONSTRUCT"})


def _equip_points(tag: str, *, with_bacnet: bool = False) -> str:
    bacnet = ""
    if with_bacnet:
        bacnet = """
  OPTIONAL { ?point ofdd:bacnetDeviceId ?bacnet_device_id . }
  OPTIONAL { ?point ofdd:objectIdentifier ?object_identifier . }"""
    cols = "?equipment ?equipment_label ?point ?point_label ?column ?point_role"
    if with_bacnet:
        cols += " ?bacnet_device_id ?object_identifier"
    return f"""{PREFIXES_SPARQL}
SELECT {cols} WHERE {{
  ?equipment a ph:equip, ph:{tag} .
  OPTIONAL {{ ?equipment rdfs:label ?equipment_label . }}
  ?point ph:equipRef ?equipment .
  OPTIONAL {{ ?point rdfs:label ?point_label . }}
  OPTIONAL {{ ?point ofdd:timeseriesColumn ?column . }}
  OPTIONAL {{ ?point ofdd:pointRole ?point_role . }}{bacnet}
}}
ORDER BY ?equipment ?point"""


def _equip_count(tag: str) -> str:
    return f"""{PREFIXES_SPARQL}
SELECT (COUNT(?e) AS ?count) WHERE {{
  ?e a ph:equip, ph:{tag} .
}}"""


PREDEFINED_QUERIES: list[dict[str, Any]] = [
    # --- Sites ---
    {
        "id": "sites",
        "label": "List sites",
        "short_label": "Sites",
        "category": "haystack",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?site ?site_label WHERE {{
  ?site a ph:site .
  OPTIONAL {{ ?site rdfs:label ?site_label }}
}}""",
        "query_with_bacnet": f"""{PREFIXES_SPARQL}
SELECT ?site ?site_label ?equipment ?equipment_label ?point ?point_label ?column ?bacnet_device_id ?object_identifier WHERE {{
  ?site a ph:site .
  OPTIONAL {{ ?site rdfs:label ?site_label . }}
  ?equipment ph:siteRef ?site .
  OPTIONAL {{ ?equipment rdfs:label ?equipment_label . }}
  ?point ph:equipRef ?equipment .
  OPTIONAL {{ ?point rdfs:label ?point_label . }}
  OPTIONAL {{ ?point ofdd:timeseriesColumn ?column . }}
  OPTIONAL {{ ?point ofdd:bacnetDeviceId ?bacnet_device_id . }}
  OPTIONAL {{ ?point ofdd:objectIdentifier ?object_identifier . }}
}}
ORDER BY ?site ?equipment ?point""",
    },
    # --- AHUs ---
    {
        "id": "ahu_information",
        "label": "Air handling units",
        "short_label": "AHUs",
        "category": "haystack",
        "query": _equip_count("ahu"),
        "query_with_bacnet": _equip_points("ahu", with_bacnet=True),
    },
    {
        "id": "number_of_vav_boxes_per_ahu",
        "label": "VAV boxes per AHU (feeds)",
        "short_label": "VAVs per AHU",
        "category": "haystack",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?ahu ?ahu_label (COUNT(?vav) AS ?vav_count) WHERE {{
  ?ahu a ph:equip, ph:ahu .
  OPTIONAL {{ ?ahu rdfs:label ?ahu_label . }}
  ?ahu ofdd:feeds ?vav .
  ?vav a ph:equip, ph:vav .
}}
GROUP BY ?ahu ?ahu_label
ORDER BY DESC(?vav_count)""",
    },
    # --- VAVs ---
    {
        "id": "count-vavs",
        "label": "Count VAV boxes",
        "short_label": "VAV boxes",
        "category": "haystack",
        "query": _equip_count("vav"),
        "query_with_bacnet": _equip_points("vav", with_bacnet=True),
    },
    {
        "id": "vav_information",
        "label": "VAV boxes and points",
        "short_label": "VAV list",
        "category": "haystack",
        "query": _equip_points("vav"),
        "query_with_bacnet": _equip_points("vav", with_bacnet=True),
    },
    # --- Zones (Haystack zone tag when present) ---
    {
        "id": "zone_information",
        "label": "Count zones",
        "short_label": "Zones",
        "category": "haystack",
        "query": _equip_count("zone"),
        "query_with_bacnet": _equip_points("zone", with_bacnet=True),
    },
    # --- Building summary ---
    {
        "id": "building_information",
        "label": "Site equipment counts",
        "short_label": "Building",
        "category": "haystack",
        "query": f"""{PREFIXES_SPARQL}
SELECT (COUNT(DISTINCT ?site) AS ?sites)
       (COUNT(DISTINCT ?ahu) AS ?ahus)
       (COUNT(DISTINCT ?vav) AS ?vavs)
       (COUNT(DISTINCT ?ch) AS ?chillers)
       (COUNT(DISTINCT ?pt) AS ?points) WHERE {{
  OPTIONAL {{ ?site a ph:site . }}
  OPTIONAL {{ ?ahu a ph:equip, ph:ahu . }}
  OPTIONAL {{ ?vav a ph:equip, ph:vav . }}
  OPTIONAL {{ ?ch a ph:equip, ph:chiller . }}
  OPTIONAL {{ ?pt a ph:point . }}
}}""",
    },
    # --- Relationships (port of brick_feeds / brick_fed_by) ---
    {
        "id": "haystack_feeds",
        "label": "Haystack feeds (parent → child)",
        "short_label": "feeds →",
        "category": "relationships",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?site_label ?from_label ?to_label WHERE {{
  ?from ofdd:feeds ?to .
  OPTIONAL {{
    ?from ph:siteRef ?site .
    OPTIONAL {{ ?site rdfs:label ?site_label . }}
  }}
  OPTIONAL {{ ?from rdfs:label ?from_label . }}
  OPTIONAL {{ ?to rdfs:label ?to_label . }}
}}
ORDER BY ?site_label ?from_label ?to_label""",
    },
    {
        "id": "haystack_fed_by",
        "label": "Haystack fed-by (child ← parent)",
        "short_label": "← fed by",
        "category": "relationships",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?site_label ?child_label ?parent_label WHERE {{
  ?parent ofdd:feeds ?child .
  OPTIONAL {{
    ?child ph:siteRef ?site .
    OPTIONAL {{ ?site rdfs:label ?site_label . }}
  }}
  OPTIONAL {{ ?child rdfs:label ?child_label . }}
  OPTIONAL {{ ?parent rdfs:label ?parent_label . }}
}}
ORDER BY ?site_label ?child_label ?parent_label""",
    },
    # --- Plant ---
    {
        "id": "count-chillers",
        "label": "Count chillers",
        "short_label": "Chillers",
        "category": "haystack",
        "query": _equip_count("chiller"),
        "query_with_bacnet": _equip_points("chiller", with_bacnet=True),
    },
    {
        "id": "count-boilers",
        "label": "Count boilers / plant",
        "short_label": "Boilers",
        "category": "haystack",
        "query": f"""{PREFIXES_SPARQL}
SELECT (COUNT(?b) AS ?count) WHERE {{
  {{ ?b a ph:equip, ph:boiler . }} UNION {{ ?b a ph:equip, ph:boilerPlant . }}
}}""",
    },
    {
        "id": "count-cooling-towers",
        "label": "Count cooling towers",
        "short_label": "Cooling towers",
        "category": "haystack",
        "query": _equip_count("coolingTower"),
    },
    {
        "id": "central_plant_information",
        "label": "Central plant equipment",
        "short_label": "Central plant",
        "category": "haystack",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?equipment ?equipment_label ?tag WHERE {{
  ?equipment a ph:equip .
  ?equipment a ?tag .
  FILTER(?tag IN (ph:chiller, ph:boiler, ph:boilerPlant, ph:coolingTower))
  OPTIONAL {{ ?equipment rdfs:label ?equipment_label . }}
}}
ORDER BY ?tag ?equipment""",
    },
    {
        "id": "count-hvac-equipment",
        "label": "Count all HVAC equipment",
        "short_label": "HVAC equip",
        "category": "haystack",
        "query": f"""{PREFIXES_SPARQL}
SELECT (COUNT(?e) AS ?count) WHERE {{
  ?e a ph:equip .
  ?e a ?tag .
  FILTER(?tag IN (ph:ahu, ph:vav, ph:chiller, ph:boiler, ph:boilerPlant, ph:zone))
}}""",
    },
    # --- Meters ---
    {
        "id": "meter_information",
        "label": "Meters and electrical points",
        "short_label": "Meters",
        "category": "haystack",
        "query": f"""{PREFIXES_SPARQL}
SELECT (COUNT(?m) AS ?meters) WHERE {{
  ?m a ph:equip, ph:meter .
}}""",
    },
    # --- Points ---
    {
        "id": "count-points",
        "label": "Count historized points",
        "short_label": "Points",
        "category": "haystack",
        "query": f"""{PREFIXES_SPARQL}
SELECT (COUNT(?p) AS ?count) WHERE {{
  ?p a ph:point .
}}""",
        "query_with_bacnet": f"""{PREFIXES_SPARQL}
SELECT ?point ?point_label ?column ?bacnet_device_id ?object_identifier WHERE {{
  ?point a ph:point .
  OPTIONAL {{ ?point rdfs:label ?point_label . }}
  OPTIONAL {{ ?point ofdd:timeseriesColumn ?column . }}
  OPTIONAL {{ ?point ofdd:bacnetDeviceId ?bacnet_device_id . }}
  OPTIONAL {{ ?point ofdd:objectIdentifier ?object_identifier . }}
}}
ORDER BY ?point
LIMIT 500""",
    },
    {
        "id": "class_tag_summary",
        "label": "Haystack tag summary",
        "short_label": "Tag summary",
        "category": "haystack",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?type (COUNT(?e) AS ?count) WHERE {{
  ?e a ?type .
  FILTER(STRSTARTS(STR(?type), "{PH}"))
}} GROUP BY ?type
ORDER BY DESC(?count)
LIMIT 50""",
    },
    # --- FDD coverage (SPARQL-only, no JSON grep) ---
    {
        "id": "equipment_to_points",
        "label": "Equipment → Points",
        "short_label": "Equip→Points",
        "category": "fdd_coverage",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?equipment ?equipment_label ?point ?point_label ?column ?point_role ?fdd_input WHERE {{
  ?equipment a ph:equip .
  OPTIONAL {{ ?equipment rdfs:label ?equipment_label . }}
  ?point ph:equipRef ?equipment .
  OPTIONAL {{ ?point rdfs:label ?point_label . }}
  OPTIONAL {{ ?point ofdd:timeseriesColumn ?column . }}
  OPTIONAL {{ ?point ofdd:pointRole ?point_role . }}
  OPTIONAL {{ ?point ofdd:mapsToRuleInput ?fdd_input . }}
}}
ORDER BY ?equipment ?point""",
    },
    {
        "id": "ahus_vavs_zones",
        "label": "AHUs / VAVs / Zones",
        "short_label": "AHU/VAV/Zone",
        "category": "fdd_coverage",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?equipment ?equipment_label ?hvac_tag (COUNT(?point) AS ?point_count) WHERE {{
  ?equipment a ph:equip .
  ?equipment a ?hvac_tag .
  FILTER(?hvac_tag IN (ph:ahu, ph:vav, ph:zone))
  OPTIONAL {{ ?equipment rdfs:label ?equipment_label . }}
  OPTIONAL {{ ?point ph:equipRef ?equipment . }}
}}
GROUP BY ?equipment ?equipment_label ?hvac_tag
ORDER BY ?hvac_tag ?equipment""",
    },
    {
        "id": "orphan_points",
        "label": "Orphan points (no FDD role)",
        "short_label": "Orphans",
        "category": "fdd_coverage",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?point ?point_label ?column ?equipment WHERE {{
  ?point a ph:point .
  ?point ph:equipRef ?equipment .
  OPTIONAL {{ ?point rdfs:label ?point_label . }}
  OPTIONAL {{ ?point ofdd:timeseriesColumn ?column . }}
  FILTER NOT EXISTS {{ ?point ofdd:mapsToRuleInput ?x . }}
  FILTER NOT EXISTS {{ ?point ofdd:pointRole ?y . }}
}}
ORDER BY ?equipment ?point
LIMIT 500""",
    },
    {
        "id": "points_by_role",
        "label": "Points by FDD role",
        "short_label": "By role",
        "category": "fdd_coverage",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?point_role ?equipment ?column (COUNT(?point) AS ?n) WHERE {{
  ?point ofdd:pointRole ?point_role .
  ?point ofdd:timeseriesColumn ?column .
  ?point ph:equipRef ?equipment .
}}
GROUP BY ?point_role ?equipment ?column
ORDER BY ?point_role ?equipment""",
    },
    {
        "id": "economizer_points",
        "label": "Economizer logical inputs",
        "short_label": "Econ inputs",
        "category": "fdd_coverage",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?equipment ?equipment_label ?fdd_input ?column ?point_label WHERE {{
  ?equipment a ph:equip, ph:ahu .
  OPTIONAL {{ ?equipment rdfs:label ?equipment_label . }}
  ?point ph:equipRef ?equipment .
  ?point ofdd:mapsToRuleInput ?fdd_input .
  ?point ofdd:timeseriesColumn ?column .
  OPTIONAL {{ ?point rdfs:label ?point_label . }}
}}
ORDER BY ?equipment ?fdd_input""",
    },
    {
        "id": "missing_economizer_on_ahu",
        "label": "AHUs missing economizer inputs",
        "short_label": "Missing econ",
        "category": "fdd_coverage",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?ahu ?ahu_label ?missing_input WHERE {{
  ?ahu a ph:equip, ph:ahu .
  OPTIONAL {{ ?ahu rdfs:label ?ahu_label . }}
  VALUES ?missing_input {{ "fan_cmd" "oat" "rat" "mat" "sat" "oa_damper_cmd" "cooling_cmd" }}
  FILTER NOT EXISTS {{
    ?point ph:equipRef ?ahu .
    ?point ofdd:mapsToRuleInput ?missing_input .
  }}
}}
ORDER BY ?ahu ?missing_input""",
    },
    {
        "id": "historian_paths",
        "label": "Equipment historian paths",
        "short_label": "Hist paths",
        "category": "fdd_coverage",
        "query": f"""{PREFIXES_SPARQL}
SELECT ?equipment ?equipment_label ?history_subdir WHERE {{
  ?equipment a ph:equip .
  OPTIONAL {{ ?equipment rdfs:label ?equipment_label . }}
  OPTIONAL {{ ?equipment ofdd:historySubdir ?history_subdir . }}
}}
ORDER BY ?equipment""",
    },
]

DEFAULT_SPARQL = f"""{PREFIXES_SPARQL}
SELECT ?site ?site_label WHERE {{
  ?site a ph:site .
  OPTIONAL {{ ?site rdfs:label ?site_label }}
}}"""


def predefined_catalog() -> dict[str, Any]:
    return {"default_query": DEFAULT_SPARQL, "queries": PREDEFINED_QUERIES}


def all_executable_queries(include_bacnet: bool = False) -> list[tuple[str, str]]:
    """Return (query_id, sparql_text) for validation."""
    out: list[tuple[str, str]] = []
    for item in PREDEFINED_QUERIES:
        q = item.get("query") or ""
        if include_bacnet and item.get("query_with_bacnet"):
            q = item["query_with_bacnet"]
        out.append((str(item["id"]), str(q)))
    return out


def validate_all_predefined(ttl: TtlService | None = None) -> dict[str, Any]:
    """Run every predefined query — used by tests and /api/rdf/sparql/validate."""
    svc = ttl or TtlService()
    graph = load_graph(svc)
    results: dict[str, Any] = {"passed": [], "failed": []}
    for item in PREDEFINED_QUERIES:
        for suffix, key in [("", "query"), ("_bacnet", "query_with_bacnet")]:
            query = item.get(key)
            if not query:
                continue
            qid = f"{item['id']}{suffix}"
            try:
                validate_readonly_sparql(str(query))
                rows = run_sparql(graph, str(query))
                results["passed"].append({"id": qid, "row_count": len(rows)})
            except Exception as exc:
                results["failed"].append({"id": qid, "error": str(exc)})
    return results


def _strip_sparql_comments(query: str) -> str:
    text = re.sub(r"#.*?$", "", query, flags=re.MULTILINE)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def validate_readonly_sparql(query: str) -> None:
    stripped = _strip_sparql_comments(query or "").strip()
    if not stripped:
        raise ValueError("SPARQL query is empty")
    tokens = re.findall(r"\b(\w+)\b", stripped, flags=re.IGNORECASE)
    form: str | None = None
    for token in tokens:
        upper = token.upper()
        if upper in ("PREFIX", "BASE"):
            continue
        if upper in _FORBIDDEN_FORMS:
            raise ValueError("Only read-only SPARQL (SELECT, ASK, DESCRIBE, CONSTRUCT) is allowed")
        if upper in _READONLY_FORMS:
            form = upper
            break
    if form is None:
        raise ValueError("Only read-only SPARQL (SELECT, ASK, DESCRIBE, CONSTRUCT) is allowed")


def execute_model_sparql(query: str, ttl: TtlService | None = None) -> dict[str, Any]:
    validate_readonly_sparql(query)
    svc = ttl or TtlService()
    graph = load_graph(svc)
    rows = run_sparql(graph, query)
    truncated = len(rows) > MAX_SPARQL_ROWS
    if truncated:
        rows = rows[:MAX_SPARQL_ROWS]
    return {"bindings": rows, "row_count": len(rows), "truncated": truncated}
