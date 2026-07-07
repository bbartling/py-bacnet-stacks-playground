"""Haystack resolver — SPARQL-first column/equipment discovery for pandas engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.data_config import DataConfig, get_config

from .model_sparql import column_for_role, list_equipment
from .ttl_service import TtlService


@dataclass
class HaystackResolver:
    cfg: DataConfig = field(default_factory=get_config)
    ttl: TtlService = field(default_factory=TtlService)
    _history_dirs: dict[str, Path] = field(default_factory=dict, repr=False)

    def ensure_model(self, *, force_bootstrap: bool = False) -> None:
        from .auto_sync import ensure_model_synced

        ensure_model_synced(self.cfg, force=force_bootstrap)

    def list_ahus(self) -> list[str]:
        self.ensure_model()
        return [e["id"] for e in list_equipment(self.ttl, haystack_tag="ahu")]

    def list_equipment(self, haystack_tag: str | None = None) -> list[dict[str, str]]:
        self.ensure_model()
        return list_equipment(self.ttl, haystack_tag=haystack_tag)

    def _rebuild_history_dirs(self) -> None:
        self._history_dirs.clear()
        for eq in list_equipment(self.ttl):
            eq_id = eq["id"]
            sub = eq.get("history_subdir") or eq_id
            if sub.startswith(".."):
                self._history_dirs[eq_id] = (self.cfg.building_dir / sub).resolve()
            else:
                self._history_dirs[eq_id] = self.cfg.building_dir / sub

    def history_path(self, equipment_id: str) -> Path:
        self.ensure_model()
        if equipment_id == "WEATHER":
            return self.cfg.weather_dir
        if not self._history_dirs:
            self._rebuild_history_dirs()
        return self._history_dirs.get(equipment_id, self.cfg.building_dir / equipment_id)

    def column_for_role(self, equipment_id: str, role: str) -> str | None:
        self.ensure_model()
        return column_for_role(equipment_id, role, ttl=self.ttl)

    def resolve_mapping(self, equipment_id: str, logical_keys: list[str]) -> dict[str, str | None]:
        return {k: self.column_for_role(equipment_id, k) for k in logical_keys}


def get_resolver() -> HaystackResolver:
    return HaystackResolver()
