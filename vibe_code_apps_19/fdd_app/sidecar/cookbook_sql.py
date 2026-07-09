"""Load and bind DataFusion SQL rule templates from cookbook_rules_sql.yaml."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_YAML_PATH = _HERE / "cookbook_rules_sql.yaml"


@lru_cache(maxsize=1)
def sql_catalog() -> dict[str, dict[str, Any]]:
    try:
        import yaml
    except ImportError:
        return _parse_minimal()
    if not _YAML_PATH.is_file():
        return {}
    data = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8")) or {}
    return dict(data.get("rules") or {})


def _parse_minimal() -> dict[str, dict[str, Any]]:
    """Fallback when PyYAML not installed — empty catalog."""
    return {}


def has_sql(rule_id: str) -> bool:
    return rule_id in sql_catalog()


def bind_sql(rule_id: str, *, equipment_id: str, params: dict[str, Any] | None = None) -> str | None:
    entry = sql_catalog().get(rule_id)
    if not entry:
        return None
    sql = entry.get("sql", "")
    if not sql:
        return None
    merged = {"equipment_id": equipment_id, **(params or {})}
    # Defaults from cookbook_rules
    defaults = {
        "flatline_tol": 0.1,
        "zone_lo": 68.0,
        "zone_hi": 76.0,
        "oat_err": 5.0,
        "wx_oa_t": 65.0,
    }
    merged = {**defaults, **merged}
    out = sql
    for key, val in merged.items():
        out = out.replace(f"${{{key}}}", str(val))
    return out.strip()


def confirmation_seconds(rule_id: str) -> int:
    entry = sql_catalog().get(rule_id) or {}
    return int(entry.get("confirmation_seconds", 300))


def try_sidecar_hours(
    rule_id: str,
    equipment_id: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Run rule via open-fdd sidecar if available. Returns None to fall back to pandas."""
    if not has_sql(rule_id):
        return None
    try:
        import cookbook_sidecar as cs
        if not cs.is_available():
            return None
        cs.ensure_historian_exported()
        sql = bind_sql(rule_id, equipment_id=equipment_id, params=params)
        if not sql:
            return None
        return cs.run_rule_sql(
            rule_id, sql,
            confirmation_seconds=confirmation_seconds(rule_id),
            params=params,
            equipment_id=equipment_id,
        )
    except Exception:
        return None
