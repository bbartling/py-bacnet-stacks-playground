"""Good / Better / Best measure set expansion for WattLab easy button."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

SETS_PATH = Path(__file__).resolve().parent / "measure_sets.json"


def load_measure_sets() -> dict[str, Any]:
    return json.loads(SETS_PATH.read_text(encoding="utf-8"))


def expand_measure_set(set_id: str) -> list[dict[str, Any]]:
    """Expand good/better/best into ordered approved measure dicts."""
    data = load_measure_sets()
    key = (set_id or "").strip().lower()
    if key not in ("good", "better", "best"):
        raise ValueError(f"Unknown measure_set: {set_id!r} (expected good|better|best)")
    catalog = data.get("catalog") or {}
    out: list[dict[str, Any]] = []
    for mid in (data.get(key) or {}).get("measure_ids") or []:
        base = catalog.get(mid)
        if not base:
            continue
        m = deepcopy(base)
        m["source"] = "measure_set"
        m["measure_set"] = key
        out.append(m)
    return out


def list_measure_sets() -> list[dict[str, Any]]:
    data = load_measure_sets()
    return [
        {
            "id": k,
            "label": (data[k] or {}).get("label") or k,
            "description": (data[k] or {}).get("description") or "",
            "measure_ids": list((data[k] or {}).get("measure_ids") or []),
        }
        for k in ("good", "better", "best")
        if k in data
    ]
