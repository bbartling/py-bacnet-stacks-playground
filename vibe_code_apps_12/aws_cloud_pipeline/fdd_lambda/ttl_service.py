"""JSON canonical model → BRICK Turtle projection."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

_log = logging.getLogger(__name__)

FEEDS_PREDICATES = frozenset({"feeds", "isFedBy", "hasPart", "isPartOf"})


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _safe_brick_type(value: str, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    token = re.sub(r"_+", "_", token).strip("_")
    if not token:
        return fallback
    if not (token[0].isalpha() or token[0] == "_"):
        token = f"_{token}"
    return token


def _sanitize_local_name(value: Any) -> str | None:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", str(value).strip())
    token = re.sub(r"_+", "_", token).strip("_")
    if not token:
        return None
    if token[0].isdigit():
        token = f"_{token}"
    return token


def _entity_uri(entity_id: str) -> str:
    safe = _sanitize_local_name(entity_id)
    if safe is None:
        return ":unknown"
    if safe.startswith("site_") or safe.startswith("eq_") or safe.startswith("pt_"):
        return f":{safe}"
    return f":ent_{safe}"


@dataclass
class TtlService:
    """Build Turtle from in-memory model dict (no filesystem)."""

    def build_ttl(self, model: dict[str, Any]) -> str:
        lines = [
            "@prefix brick: <https://brickschema.org/schema/Brick#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix vibe12: <http://vibe12.local/ontology#> .",
            "@prefix : <http://vibe12.local/site#> .",
            "",
        ]
        for site in model.get("sites", []):
            if not isinstance(site, dict):
                continue
            sid = _sanitize_local_name(site.get("id"))
            if sid is None:
                continue
            lines.append(f":site_{sid} a brick:Site ;")
            lines.append(f'  rdfs:label "{_escape(str(site.get("name", "Site")))}" ;')
            site_metadata = site.get("metadata") if isinstance(site.get("metadata"), dict) else {}
            rule_pack = site_metadata.get("rule_pack")
            if rule_pack:
                lines.append(f'  vibe12:faultRulePack "{_escape(str(rule_pack))}" ;')
            fault_rule = site_metadata.get("fault_rule")
            if fault_rule:
                lines.append(f'  vibe12:faultRule "{_escape(str(fault_rule))}" ;')
            lines[-1] = lines[-1].rstrip(" ;") + " ."
            lines.append("")

        for eq in model.get("equipment", []):
            if not isinstance(eq, dict):
                continue
            eid = _sanitize_local_name(eq.get("id"))
            sid = _sanitize_local_name(eq.get("site_id"))
            if eid is None or sid is None:
                continue
            et = _safe_brick_type(str(eq.get("equipment_type") or "Equipment"), "Equipment")
            lines.append(f":eq_{eid} a brick:{et} ;")
            lines.append(f'  rdfs:label "{_escape(str(eq.get("name", "Equipment")))}" ;')
            lines.append(f"  brick:isPartOf :site_{sid} .")
            lines.append("")

        for pt in model.get("points", []):
            if not isinstance(pt, dict):
                continue
            pid = _sanitize_local_name(pt.get("id"))
            if pid is None:
                continue
            bt = _safe_brick_type(str(pt.get("brick_type") or "Point"), "Point")
            object_name = str(pt.get("object_name") or "")
            external_id = str(pt.get("external_id") or "")
            label = object_name or external_id or pid
            lines.append(f":pt_{pid} a brick:{bt} ;")
            lines.append(f'  rdfs:label "{_escape(label)}" ;')
            if external_id:
                lines.append(f'  vibe12:operatorTag "{_escape(external_id)}" ;')
            if object_name:
                lines.append(f'  vibe12:objectName "{_escape(object_name)}" ;')
            if pt.get("equipment_id"):
                eid = _sanitize_local_name(pt.get("equipment_id"))
                if eid is not None:
                    lines.append(f"  brick:isPointOf :eq_{eid} ;")
            sid = _sanitize_local_name(pt.get("site_id"))
            if sid is not None:
                lines.append(f"  brick:isPartOf :site_{sid} ;")
            maps_rule_input = str(pt.get("fdd_input") or "").strip()
            if not maps_rule_input and bt and bt != "Point":
                maps_rule_input = bt
            if maps_rule_input:
                lines.append(f'  vibe12:mapsToRuleInput "{_escape(maps_rule_input)}" ;')
            meta = pt.get("metadata") if isinstance(pt.get("metadata"), dict) else {}
            ext = meta.get("external_ref")
            if ext:
                lines.append(f'  vibe12:externalReference "{_escape(str(ext))}" ;')
            unit = pt.get("unit") or meta.get("unit")
            if unit:
                lines.append(f'  vibe12:unit "{_escape(str(unit))}" ;')
            lines[-1] = lines[-1].rstrip(" ;") + " ."
            lines.append("")

        for rel in model.get("relationships", []):
            if not isinstance(rel, dict):
                continue
            subj = _entity_uri(str(rel.get("subject", "")))
            obj = _entity_uri(str(rel.get("object", "")))
            pred = str(rel.get("predicate") or "feeds").strip()
            if pred in FEEDS_PREDICATES:
                lines.append(f"{subj} brick:{pred} {obj} .")
            else:
                lines.append(f"{subj} vibe12:{pred} {obj} .")
            lines.append("")

        return "\n".join(lines)

    def sync_to_store(self, ts_store, site_id: str, building_id: str, model: dict[str, Any]) -> str:
        ttl = self.build_ttl(model)
        ts_store.put_ttl(site_id, building_id, ttl)
        return ttl
