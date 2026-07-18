from __future__ import annotations
from pathlib import Path
from typing import Any
from .config import load_config
from .models import ProjectConfig
from .registry import get
from . import algorithms  # noqa: F401
from . import esco  # noqa: F401

def run_document(config: ProjectConfig) -> dict[str, Any]:
    rows = []
    totals = {"savings_kwh": 0.0, "savings_therms": 0.0}
    for spec in config.calculations:
        if not spec.enabled:
            rows.append({"id": spec.id, "algorithm": spec.algorithm, "status": "SKIPPED_DISABLED"})
            continue
        try:
            result = get(spec.algorithm)(spec.inputs)
            for key in totals:
                if key in result:
                    totals[key] += float(result[key])
            rows.append({
                "id": spec.id,
                "algorithm": spec.algorithm,
                "status": "OK",
                "result": result,
                "tags": spec.tags,
                "notes": spec.notes,
            })
        except Exception as exc:
            rows.append({
                "id": spec.id,
                "algorithm": spec.algorithm,
                "status": "ERROR",
                "error": str(exc),
            })
    return {
        "schema_version": config.schema_version,
        "project": config.project,
        "assumptions": config.assumptions,
        "calculations": rows,
        "totals": totals,
    }

def run_config(path: str | Path) -> dict[str, Any]:
    return run_document(load_config(path))
