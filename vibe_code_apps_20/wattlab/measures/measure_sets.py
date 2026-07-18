"""Measure-set expansion for the WattLab easy button.

Sets are defined in ``measure_sets.json``: the classic good/better/best
ladder plus scenario bundles like ``school_30yr_hydronic`` and
``school_30yr_electrify``. Any top-level key with a ``measure_ids`` list is a
set; new sets added to the JSON flow through to the CLI choices and Studio
picker without code changes.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

SETS_PATH = Path(__file__).resolve().parent / "measure_sets.json"


def load_measure_sets() -> dict[str, Any]:
    return json.loads(SETS_PATH.read_text(encoding="utf-8"))


def _set_ids(data: dict[str, Any]) -> list[str]:
    """Ordered set ids: every non-catalog entry that carries measure_ids."""
    return [
        k
        for k, v in data.items()
        if k != "catalog" and isinstance(v, dict) and "measure_ids" in v
    ]


def expand_measure_set(set_id: str) -> list[dict[str, Any]]:
    """Expand a measure-set id into ordered approved measure dicts."""
    data = load_measure_sets()
    key = (set_id or "").strip().lower()
    available = _set_ids(data)
    if key not in available:
        raise ValueError(
            f"Unknown measure_set: {set_id!r} (expected one of: "
            + ", ".join(available)
            + ")"
        )
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
        for k in _set_ids(data)
    ]
