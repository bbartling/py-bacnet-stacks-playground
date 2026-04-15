"""Helpers for BACnet present-value normalization (JSON-RPC returns vary by stack)."""

from __future__ import annotations

import json
import os
from typing import Any


def pv_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.strip())
        except ValueError:
            return None
    if isinstance(val, dict):
        for k in ("presentValue", "present-value", "value"):
            if k in val:
                return pv_float(val[k])
    return None


def load_json_env(name: str, default: Any) -> Any:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default
