"""Persist Haystack commissioning model as model.json."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import model_json_path


def empty_model() -> dict[str, Any]:
    return {"version": 1, "sites": [], "equipment": [], "points": []}


@dataclass
class ModelStore:
    path: Path = field(default_factory=model_json_path)

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return empty_model()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return empty_model()
        for key in ("sites", "equipment", "points"):
            if not isinstance(data.get(key), list):
                data[key] = []
        data.setdefault("version", 1)
        return data

    def save(self, model: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(model, indent=2)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f"{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, mode="w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise
