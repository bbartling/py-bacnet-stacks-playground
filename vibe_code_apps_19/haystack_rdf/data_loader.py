"""SPARQL-driven historian loader — no hardcoded equipment folder names."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from shared.data_config import get_config

from .resolver import HaystackResolver, get_resolver


def load_history_wide(equipment_id: str, resolver: HaystackResolver | None = None) -> pd.DataFrame:
    """Load history_wide.csv for equipment using SPARQL-resolved historySubdir."""
    from .feather_cache import read_history_csv

    r = resolver or get_resolver()
    r.ensure_model()
    path = r.history_path(equipment_id) / "history_wide.csv"
    if not path.is_file():
        raise FileNotFoundError(f"No history for {equipment_id}: {path}")
    cfg = get_config()
    return read_history_csv(path, tz=cfg.site_timezone())


def list_equipment_ids(haystack_tag: str | None = None, resolver: HaystackResolver | None = None) -> list[str]:
    r = resolver or get_resolver()
    r.ensure_model()
    return [e["id"] for e in r.list_equipment(haystack_tag=haystack_tag)]


def column_for_role(equipment_id: str, role: str, resolver: HaystackResolver | None = None) -> str | None:
    r = resolver or get_resolver()
    return r.column_for_role(equipment_id, role)
