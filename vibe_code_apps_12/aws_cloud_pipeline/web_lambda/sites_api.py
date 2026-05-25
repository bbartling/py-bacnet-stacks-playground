"""Site / building creation for cloud UI."""

from __future__ import annotations

import re
from typing import Any

from model_schema import normalize_model_payload
from model_store import ModelStore


def _slug(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return re.sub(r"-+", "-", token).strip("-") or "site"


def create_site_building(
    ts_store,
    *,
    site_id: str,
    building_id: str,
    display_name: str = "",
) -> dict[str, Any]:
    site_id = _slug(site_id) if site_id else ""
    building_id = _slug(building_id) if building_id else ""
    if not site_id or not building_id:
        raise ValueError("site_id and building_id are required")

    ts_store.ensure_building(site_id, building_id)
    name = display_name.strip() or f"{site_id} / {building_id}"
    model = normalize_model_payload(
        {
            "sites": [{"id": site_id, "name": name, "metadata": {"building_id": building_id}}],
            "equipment": [],
            "points": [],
            "relationships": [],
        }
    )
    ModelStore(ts_store).save(site_id, building_id, model)
    return {
        "ok": True,
        "site_id": site_id,
        "building_id": building_id,
        "display_name": name,
        "building_scope": f"{site_id}#{building_id}",
        "hint": "Edge MQTT topic: vibe12/{site_id}/{building_id}/{system_id}/{point_id}/telemetry",
    }
