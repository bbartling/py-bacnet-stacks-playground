"""Presentation-only catalog ordering helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_COMPLEXITY_RANK = {"low": 0, "medium": 1, "high": 2}


def _field(entry: Any, name: str, default: str = "") -> str:
    if isinstance(entry, Mapping):
        return str(entry.get(name, default))
    return str(getattr(entry, name, default))


def complexity_sort_key(entry: Any) -> tuple[int, str, str]:
    """Sort catalog entries easy-to-hard without changing package order."""
    complexity = _field(entry, "implementation_complexity").lower()
    return (
        _COMPLEXITY_RANK.get(complexity, len(_COMPLEXITY_RANK)),
        _field(entry, "category").lower(),
        _field(entry, "ecm_id").upper(),
    )


__all__ = ["complexity_sort_key"]
