"""CRUD + import/export for Haystack model.json."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .model_store import ModelStore
from .ttl_service import TtlService

_MODEL_LOCK = threading.RLock()


@dataclass
class ModelService:
    store: ModelStore = field(default_factory=ModelStore)
    ttl: TtlService = field(default_factory=TtlService)

    def load(self) -> dict[str, Any]:
        return self.store.load()

    @contextmanager
    def transaction(self) -> Iterator[dict[str, Any]]:
        with _MODEL_LOCK:
            model = self.load()
            try:
                yield model
            except Exception:
                raise
            else:
                self.store.save(model)

    def export_json(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.load(), indent=2), encoding="utf-8")
        return target

    def normalize_import_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        sites = payload.get("sites", []) if isinstance(payload.get("sites"), list) else []
        equipment = payload.get("equipment", []) if isinstance(payload.get("equipment"), list) else []
        points = payload.get("points", []) if isinstance(payload.get("points"), list) else []
        return {
            "version": payload.get("version", 1),
            "sites": [s for s in sites if isinstance(s, dict)],
            "equipment": [e for e in equipment if isinstance(e, dict)],
            "points": [p for p in points if isinstance(p, dict)],
        }

    def import_json(self, payload: dict[str, Any], *, replace: bool = True) -> dict[str, int]:
        normalized = self.normalize_import_payload(payload)
        with self.transaction() as model:
            if replace:
                model.clear()
                model.update(normalized)
            else:
                for key in ("sites", "equipment", "points"):
                    model.setdefault(key, [])
                    model[key].extend(normalized[key])
        self.ttl.sync()
        return {
            "sites": len(normalized["sites"]),
            "equipment": len(normalized["equipment"]),
            "points": len(normalized["points"]),
        }

    def sync_ttl(self) -> str:
        path = self.ttl.sync()
        return str(path)

    def get_ttl_text(self) -> str:
        return self.ttl.build_ttl()
