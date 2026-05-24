"""Canonical {sites, equipment, points} model backed by DynamoDB."""

from __future__ import annotations

import re
from typing import Any

from mqtt_routing import CANONICAL_MODEL_TS, meta_device_id
from model_schema import normalize_model_payload


def _sanitize_id(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", str(value).strip())
    token = re.sub(r"_+", "_", token).strip("_")
    if token and token[0].isdigit():
        token = f"_{token}"
    return token or "unknown"


def _infer_equipment_type(system_id: str, points: list[dict[str, Any]]) -> str:
    """Best-effort equipment type from system_id or point metadata."""
    sys_lower = (system_id or "").lower()
    if "vav" in sys_lower:
        return "Variable_Air_Volume_Box"
    if "ahu" in sys_lower:
        return "Air_Handling_Unit"
    if "chiller" in sys_lower:
        return "Chiller"
    if "boiler" in sys_lower:
        return "Boiler"
    for p in points:
        eq_type = (p.get("equipment_type") or "").strip()
        if eq_type:
            return eq_type
    return "HVAC_Equipment"


def bootstrap_from_registry(
    site_id: str,
    building_id: str,
    points: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build open-fdd-shaped model from BACnet point registry rows."""
    site = {"id": site_id, "name": f"{site_id} / {building_id}"}
    equipment_by_key: dict[str, dict[str, Any]] = {}
    out_points: list[dict[str, Any]] = []

    for p in points:
        system_id = p.get("system_id") or "unknown"
        eq_key = system_id
        if eq_key not in equipment_by_key:
            eq_id = _sanitize_id(f"{site_id}_{building_id}_{system_id}")
            equipment_by_key[eq_key] = {
                "id": eq_id,
                "site_id": site_id,
                "name": system_id,
                "equipment_type": _infer_equipment_type(system_id, [p]),
            }
        eq_id = equipment_by_key[eq_key]["id"]
        tag = p.get("brick_tag") or p.get("point_id") or p.get("series_id", "")
        pt_id = _sanitize_id(f"{site_id}_{building_id}_{tag}")
        brick_class = p.get("brick_class") or "Sensor"
        series_id = p.get("series_id") or ""
        out_points.append(
            {
                "id": pt_id,
                "site_id": site_id,
                "equipment_id": eq_id,
                "external_id": tag or pt_id,
                "brick_type": brick_class,
                "fdd_input": brick_class,
                "unit": p.get("unit", ""),
                "metadata": {
                    "external_ref": series_id,
                    "building_id": building_id,
                    "system_id": system_id,
                },
            }
        )

    return normalize_model_payload(
        {
            "sites": [site],
            "equipment": list(equipment_by_key.values()),
            "points": out_points,
            "relationships": [],
        }
    )


class ModelStore:
    """Load/save canonical model per site/building via DynamoTimeSeriesStore."""

    def __init__(self, ts_store) -> None:
        self._store = ts_store

    def load(self, site_id: str, building_id: str, *, bootstrap: bool = True) -> dict[str, Any]:
        model = self._store.get_canonical_model(site_id, building_id)
        if model is not None:
            return model
        if not bootstrap:
            return normalize_model_payload({"sites": [], "equipment": [], "points": [], "relationships": []})
        points = self._store.list_points(site_id, building_id)
        return bootstrap_from_registry(site_id, building_id, points)

    def save(self, site_id: str, building_id: str, model: dict[str, Any]) -> None:
        normalized = normalize_model_payload(model)
        self._store.put_canonical_model(site_id, building_id, normalized)

    def load_or_bootstrap(self, site_id: str, building_id: str) -> dict[str, Any]:
        return self.load(site_id, building_id, bootstrap=True)

    @staticmethod
    def meta_key(site_id: str, building_id: str) -> dict[str, str | int]:
        return {"device_id": meta_device_id(site_id, building_id), "ts_ms": CANONICAL_MODEL_TS}
