"""Generate Haystack TTL from model.json (no rdflib required for writes)."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .model_store import ModelStore
from .namespaces import PREFIXES_TTL
from .paths import model_ttl_path

_log = logging.getLogger(__name__)

_HAYSTACK_EQUIP_TAG: dict[str, str] = {
    "AHU": "ahu",
    "AIR_HANDLING_UNIT": "ahu",
    "VAV": "vav",
    "VARIABLE_AIR_VOLUME_BOX": "vav",
    "CHILLER": "chiller",
    "BOILER": "boiler",
    "BOILERS_PUMPS": "boilerPlant",
    "WEATHER": "weatherStation",
    "ZONE": "zone",
    "SITE": "site",
}


def _escape(value: str) -> str:
    out: list[str] = []
    for ch in value:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif o < 32:
            out.append(f"\\u{o:04x}")
        else:
            out.append(ch)
    return "".join(out)


def _sanitize_local_name(value: object) -> str | None:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", str(value).strip())
    token = re.sub(r"_+", "_", token).strip("_")
    if not token:
        return None
    if token[0].isdigit():
        token = f"_{token}"
    return token


def _equip_haystack_tag(eq: dict) -> str:
    for raw in (eq.get("haystack_tag"), eq.get("equipment_type"), eq.get("brick_type")):
        token = str(raw or "").strip().upper().replace(" ", "_").replace("-", "_")
        if token in _HAYSTACK_EQUIP_TAG:
            return _HAYSTACK_EQUIP_TAG[token]
    name = str(eq.get("id") or eq.get("name") or "").upper()
    if name.startswith("AHU"):
        return "ahu"
    if "VAV" in name:
        return "vav"
    if "CHILLER" in name:
        return "chiller"
    if "BOILER" in name:
        return "boiler"
    return "equip"


def _point_haystack_tags(pt: dict) -> list[str]:
    tags: list[str] = ["point"]
    role = str(pt.get("point_role") or pt.get("fdd_input") or "").lower()
    kind = str(pt.get("kind") or "").lower()
    if "cmd" in role or role.endswith("_cmd"):
        tags.append("cmd")
    elif "sp" in role or "setpoint" in role:
        tags.append("sp")
    else:
        tags.append("sensor")
    if kind == "bool":
        tags.append("bool")
    elif kind == "number" or not kind:
        tags.append("number")
    return list(dict.fromkeys(tags))


@dataclass
class TtlService:
    model_store: ModelStore = field(default_factory=ModelStore)
    ttl_path: Path = field(default_factory=model_ttl_path)

    def build_ttl(self) -> str:
        model = self.model_store.load()
        lines = [PREFIXES_TTL, ""]
        for site in model.get("sites", []):
            if not isinstance(site, dict):
                continue
            sid = _sanitize_local_name(site.get("id"))
            if sid is None:
                continue
            lines.append(f":site_{sid} a ph:site ;")
            lines.append(f'  rdfs:label "{_escape(str(site.get("name", "Site")))}" ;')
            lines[-1] = lines[-1].rstrip(" ;") + " ."
            lines.append("")

        for eq in model.get("equipment", []):
            if not isinstance(eq, dict):
                continue
            eid = _sanitize_local_name(eq.get("id"))
            sid = _sanitize_local_name(eq.get("site_id"))
            if eid is None or sid is None:
                continue
            tag = _equip_haystack_tag(eq)
            lines.append(f":eq_{eid} a ph:equip, ph:{tag} ;")
            lines.append(f'  rdfs:label "{_escape(str(eq.get("name", eid)))}" ;')
            lines.append(f"  ph:siteRef :site_{sid} ;")
            hist = eq.get("history_subdir")
            if hist:
                lines.append(f'  ofdd:historySubdir "{_escape(str(hist))}" ;')
            feeds = eq.get("feeds") if isinstance(eq.get("feeds"), list) else []
            for target in feeds:
                tid = _sanitize_local_name(target)
                if tid is not None:
                    lines.append(f"  ofdd:feeds :eq_{tid} ;")
            lines[-1] = lines[-1].rstrip(" ;") + " ."
            lines.append("")

        for pt in model.get("points", []):
            if not isinstance(pt, dict):
                continue
            pid = _sanitize_local_name(pt.get("id"))
            eid = _sanitize_local_name(pt.get("equipment_id"))
            if pid is None:
                continue
            tags = _point_haystack_tags(pt)
            type_clause = ", ".join(f"ph:{t}" for t in tags)
            label = str(pt.get("name") or pt.get("column") or pt.get("external_id") or pid)
            lines.append(f":pt_{pid} a {type_clause} ;")
            lines.append(f'  rdfs:label "{_escape(label)}" ;')
            if eid is not None:
                lines.append(f"  ph:equipRef :eq_{eid} ;")
            col = pt.get("timeseries_column") or pt.get("column") or pt.get("external_id")
            if col:
                lines.append(f'  ofdd:timeseriesColumn "{_escape(str(col))}" ;')
            role = pt.get("point_role") or pt.get("fdd_input")
            if role:
                lines.append(f'  ofdd:pointRole "{_escape(str(role))}" ;')
            rule_inputs = pt.get("rule_inputs") if isinstance(pt.get("rule_inputs"), list) else []
            if not rule_inputs and pt.get("fdd_input"):
                rule_inputs = [str(pt.get("fdd_input"))]
            for rin in rule_inputs:
                if rin:
                    lines.append(f'  ofdd:mapsToRuleInput "{_escape(str(rin))}" ;')
            unit = pt.get("unit") or pt.get("units")
            if unit:
                lines.append(f'  ph:unit "{_escape(str(unit))}" ;')
            lines[-1] = lines[-1].rstrip(" ;") + " ."
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def sync(self) -> Path:
        ttl = self.build_ttl()
        self.ttl_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f"{self.ttl_path.name}.", suffix=".tmp", dir=str(self.ttl_path.parent)
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, mode="w", encoding="utf-8") as handle:
                handle.write(ttl)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.ttl_path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise
        _log.info("Synced Haystack TTL → %s", self.ttl_path)
        return self.ttl_path
