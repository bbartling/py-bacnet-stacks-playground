"""Paths for Haystack model.json and synced TTL."""

from __future__ import annotations

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RDF_ROOT = APP_ROOT / "data" / "rdf"


def rdf_root() -> Path:
    env = os.environ.get("HAYSTACK_RDF_ROOT")
    return Path(env) if env else DEFAULT_RDF_ROOT


def building_rdf_dir(building: str | None = None) -> Path:
    if building is None:
        from shared.data_config import get_config

        building = get_config().building
    return rdf_root() / building


def model_json_path(building: str | None = None) -> Path:
    return building_rdf_dir(building) / "model.json"


def model_ttl_path(building: str | None = None) -> Path:
    return building_rdf_dir(building) / "data_model.ttl"
