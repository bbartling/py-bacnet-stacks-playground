"""Load public clean-room provenance records for bin-method calculators."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


def load_provenance() -> dict[str, dict[str, Any]]:
    """Return calculator-id keyed provenance records shipped with WattLab."""

    resource = files("wattlab").joinpath("data", "bench", "provenance.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("calculator provenance must be a JSON object")
    return payload


def get_provenance(calculator_id: str) -> dict[str, Any]:
    """Return one calculator's provenance, raising KeyError for unknown ids."""

    return load_provenance()[calculator_id]
