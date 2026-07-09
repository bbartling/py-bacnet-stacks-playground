"""HTTP client for open-fdd edge DataFusion SQL sidecar — with pandas fallback."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

_EDGE_URL = os.environ.get("OPENFDD_EDGE_URL", "http://127.0.0.1:9090")
_TIMEOUT = float(os.environ.get("OPENFDD_EDGE_TIMEOUT", "120"))


def edge_url() -> str:
    return _EDGE_URL.rstrip("/")


def is_available() -> bool:
    """Quick health check — sidecar reachable."""
    try:
        req = urllib.request.Request(f"{edge_url()}/api/fdd-schema/tables", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def run_sql(
    sql: str,
    *,
    confirmation_seconds: int = 300,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one SQL rule against open-fdd historian via POST /api/fdd/run."""
    payload = {
        "sql": sql,
        "confirmation_seconds": confirmation_seconds,
        "params": params or {},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{edge_url()}/api/fdd/run",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_rule_sql(
    rule_id: str,
    sql: str,
    *,
    confirmation_seconds: int = 300,
    params: dict[str, Any] | None = None,
    equipment_id: str | None = None,
) -> dict[str, Any]:
    """Run SQL and summarize fault hours for one equipment (if equipment_id given)."""
    result = run_sql(sql, confirmation_seconds=confirmation_seconds, params=params)
    if not result.get("ok"):
        return {"ok": False, "rule_id": rule_id, "error": result.get("error", "sidecar error")}

    rows = result.get("rows") or []
    poll = 300.0
    fault_hours = 0.0
    n_fault = 0
    for row in rows:
        if equipment_id and row.get("equipment_id") != equipment_id:
            continue
        confirmed = (
            row.get("confirmed_fault") is True
            or row.get("fault_raw") is True
            or row.get("raw_fault") is True
        )
        if confirmed:
            n_fault += 1
    fault_hours = round(n_fault * poll / 3600.0, 1)
    total_h = round(len(rows) * poll / 3600.0, 1) if rows else 0.0
    pct = round(100.0 * fault_hours / total_h, 2) if total_h else 0.0

    return {
        "ok": True,
        "rule_id": rule_id,
        "fault_hours": fault_hours,
        "fault_pct": pct,
        "total_hours": total_h,
        "row_count": len(rows),
        "engine": "datafusion",
        "confirmation": result.get("confirmation"),
    }


def ensure_historian_exported() -> dict[str, Any]:
    """Export vibe19 historian if stale, so sidecar has data."""
    import historian_export as he
    if he.needs_export():
        return he.export_all()
    dest = he.export_dir()
    meta_path = dest / "export_meta.json"
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return he.export_all()
