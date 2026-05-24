"""Port of open-fdd assistant import parsing."""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_FILE_SECTION_RE = re.compile(
    r"^===\s*FILE:\s*(?P<name>[^\n]+?)\s*===\s*\n(?P<body>[\s\S]*?)(?=^===\s*FILE:|\Z)",
    re.MULTILINE,
)


def _extract_json_fence(text: str) -> str | None:
    m = _FENCE_RE.search(text)
    return m.group(1).strip() if m else None


def _extract_import_from_copy_paste_sections(text: str) -> dict[str, Any] | None:
    for m in _FILE_SECTION_RE.finditer(text):
        name = (m.group("name") or "").strip()
        body = (m.group("body") or "").strip()
        if not body:
            continue
        lower = name.lower()
        if not (
            "import_ready" in lower
            or lower.endswith(".json")
            or "data_model_import" in lower
        ):
            continue
        try:
            obj: Any = json.loads(body)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        sites = obj.get("sites")
        equipment = obj.get("equipment")
        points = obj.get("points")
        if isinstance(sites, list) and isinstance(equipment, list) and isinstance(points, list):
            return {"sites": sites, "equipment": equipment, "points": points}
    return None


def extract_import_shape_from_llm_output(content: str) -> dict[str, Any] | None:
    raw = (content or "").strip()
    if not raw:
        return None
    candidates: list[str] = [raw]
    fenced = _extract_json_fence(raw)
    if fenced:
        candidates.append(fenced)
    for candidate in candidates:
        try:
            parsed: Any = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if not isinstance(parsed, dict):
            continue
        ir = parsed.get("import_ready_json")
        if isinstance(ir, dict):
            parsed = ir
        elif isinstance(parsed.get("proposed_model_json"), dict):
            parsed = parsed["proposed_model_json"]
        sites = parsed.get("sites")
        equipment = parsed.get("equipment")
        points = parsed.get("points")
        if isinstance(sites, list) and isinstance(equipment, list) and isinstance(points, list):
            return {"sites": sites, "equipment": equipment, "points": points}
    return _extract_import_from_copy_paste_sections(raw)
