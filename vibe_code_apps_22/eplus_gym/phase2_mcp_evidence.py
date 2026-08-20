"""Phase 2 EnergyPlus MCP evidence capture and stable hashing."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

MCP_TOOLS_REQUIRED = (
    "load_idf_model",
    "get_model_summary",
    "discover_hvac_loops",
)

_TIMESTAMP_KEYS = frozenset({"diagnosed_at_utc", "frozen_at_utc", "handoff_at_utc", "registered_at_utc"})


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sanitize_for_hash(obj: Any) -> Any:
    """Strip volatile keys and absolute paths for reproducible MCP response hashes."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in _TIMESTAMP_KEYS:
                continue
            if k in {"file_path", "original_path"} and isinstance(v, str):
                out[k] = PathBasename(v)
                continue
            out[k] = sanitize_for_hash(v)
        return out
    if isinstance(obj, list):
        return [sanitize_for_hash(x) for x in obj]
    if isinstance(obj, str):
        return re.sub(r"[A-Za-z]:\\[^\\]+\\", "", obj) if "\\" in obj else obj
    return obj


def PathBasename(p: str) -> str:
    return p.replace("\\", "/").split("/")[-1]


def build_mcp_evidence_block(
    *,
    load_result: Mapping[str, Any] | None,
    model_summary: Mapping[str, Any] | None,
    hvac_loops: Mapping[str, Any] | None,
    tools_invoked: tuple[str, ...] = MCP_TOOLS_REQUIRED,
) -> dict[str, Any]:
    payloads = {
        "load_idf_model": dict(load_result or {}),
        "get_model_summary": dict(model_summary or {}),
        "discover_hvac_loops": dict(hvac_loops or {}),
    }
    hashes = {tool: sha256_text(stable_json(sanitize_for_hash(pl))) for tool, pl in payloads.items()}
    payloads_present = all(bool(payloads.get(t)) for t in tools_invoked)
    return {
        "mcp_tools_invoked": list(tools_invoked),
        "payloads": payloads,
        "payload_sha256": hashes,
        "evidence_complete": payloads_present and all(bool(hashes.get(t)) for t in tools_invoked),
    }


def historical_err_evidence_from_phase1(phase1_freeze: Mapping[str, Any] | None) -> dict[str, Any]:
    """Sanitized W2A low-airflow counts from frozen research-long audit (not a re-run)."""
    if not phase1_freeze:
        return {"label": "HISTORICAL_PHASE1_FREEZE", "available": False}
    w2a = (
        (phase1_freeze.get("research_long_audit") or {}).get("w2a_low_airflow")
        or {}
    )
    agg = w2a.get("aggregate") or {}
    totals = agg.get("totals") or {}
    return {
        "label": "HISTORICAL_PHASE1_FREEZE",
        "available": bool(totals),
        "source": "phase1_evidence_freeze.research_long_audit.w2a_low_airflow",
        "aggregate_totals": {
            "warmup": totals.get("warmup"),
            "sizing": totals.get("sizing"),
            "scored_runtime": totals.get("scored_runtime"),
            "total_recurring_printed": totals.get("total_recurring_printed"),
        },
        "severe_fatal": agg.get("severe_fatal"),
        "runtime_airflow_fraction_below_0_25": "UNAVAILABLE_FROM_ERR_ONLY",
        "note": (
            "ERR recurring counts only; per-timestep actual/rated airflow requires EIO/CSV "
            "or live child-model confirmation."
        ),
    }


def assert_mcp_evidence_complete(mcp_block: Mapping[str, Any]) -> None:
    if not mcp_block.get("evidence_complete"):
        raise ValueError("MCP evidence incomplete — payload_sha256 empty or tools not invoked")
    hashes = mcp_block.get("payload_sha256") or {}
    if not all(hashes.get(t) for t in MCP_TOOLS_REQUIRED):
        raise ValueError("MCP payload_sha256 missing for required tools")
