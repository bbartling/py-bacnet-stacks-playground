"""Load sql_rules/registry.yaml and rule_tuning profiles for the dashboard API."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_APP19 = Path(__file__).resolve().parent.parent.parent
_REGISTRY = _APP19 / "sql_rules" / "registry.yaml"
_TUNING_DIR = _APP19 / "rule_tuning"


def _yaml_load(text: str) -> Any:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML required for SQL rule registry") from exc
    return yaml.safe_load(text) or {}


@lru_cache(maxsize=1)
def load_registry() -> list[dict[str, Any]]:
    if not _REGISTRY.is_file():
        return []
    data = _yaml_load(_REGISTRY.read_text(encoding="utf-8"))
    return list(data.get("rules") or [])


def rust_cache_enabled() -> bool:
    return os.environ.get("VIBE19_RUST_CACHE", "").strip().lower() in ("1", "true", "yes")


def _load_tuning_file(name: str) -> dict[str, Any]:
    path = _TUNING_DIR / name
    if not path.is_file():
        return {}
    return _yaml_load(path.read_text(encoding="utf-8")) or {}


def _merge_rule_params(
    rule: dict[str, Any],
    *,
    building_id: str | None = None,
    equipment_id: str | None = None,
) -> dict[str, float]:
    """Merge tuning layers; clamp to registry min/max."""
    defs: dict[str, dict[str, Any]] = dict(rule.get("parameters") or {})
    values: dict[str, float] = {k: float(v.get("default", 0)) for k, v in defs.items()}

    global_rules = (_load_tuning_file("defaults.yaml").get("rules") or {})
    if rule["rule_id"] in global_rules:
        for k, v in global_rules[rule["rule_id"]].items():
            if k in defs:
                values[k] = float(v)

    if building_id:
        bmap = _load_tuning_file("building_overrides.yaml")
        br = (bmap.get(building_id) or {}).get(rule["rule_id"]) or {}
        for k, v in br.items():
            if k in defs:
                values[k] = float(v)

    if equipment_id:
        emap = _load_tuning_file("equipment_overrides.yaml")
        er = (emap.get(equipment_id) or {}).get(rule["rule_id"]) or {}
        for k, v in er.items():
            if k in defs:
                values[k] = float(v)

    for k, v in values.items():
        d = defs.get(k) or {}
        lo, hi = float(d.get("min", v)), float(d.get("max", v))
        values[k] = max(lo, min(hi, v))
    return values


def rule_catalog(
    *,
    building_id: str | None = None,
    equipment_id: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rule in load_registry():
        params_meta = []
        for key, meta in (rule.get("parameters") or {}).items():
            params_meta.append({
                "key": key,
                "label": meta.get("label", key),
                "default": meta.get("default"),
                "min": meta.get("min"),
                "max": meta.get("max"),
                "step": meta.get("step"),
                "unit": meta.get("unit", ""),
                "control": meta.get("frontend_control", "slider"),
                "sql_placeholder": meta.get("sql_placeholder", key.upper()),
            })
        effective = _merge_rule_params(
            rule, building_id=building_id, equipment_id=equipment_id,
        ) if params_meta else {}
        out.append({
            "rule_id": rule.get("rule_id"),
            "description": rule.get("description", ""),
            "required_roles": rule.get("required_roles") or [],
            "parity_status": rule.get("parity_status", "unknown"),
            "dashboard_wired": bool(rule.get("dashboard_wired")),
            "confirm_seconds": rule.get("confirm_seconds", 0),
            "parameters": params_meta,
            "effective_values": effective,
            "engine": "sql_datafusion",
            "rust_cache_required": True,
        })
    return out


def validate_session_params(rule_id: str, params: dict[str, Any]) -> dict[str, float]:
    rule = next((r for r in load_registry() if r.get("rule_id") == rule_id), None)
    if rule is None:
        raise ValueError(f"unknown rule_id: {rule_id}")
    defs: dict[str, dict[str, Any]] = dict(rule.get("parameters") or {})
    out: dict[str, float] = {}
    for key, raw in (params or {}).items():
        if key not in defs:
            raise ValueError(f"unknown parameter `{key}` for rule {rule_id}")
        lo = float(defs[key].get("min", raw))
        hi = float(defs[key].get("max", raw))
        val = float(raw)
        out[key] = max(lo, min(hi, val))
    return out


def save_tuning_profile(
    *,
    rule_id: str,
    scope: str,
    params: dict[str, float],
    building_id: str | None = None,
    equipment_id: str | None = None,
) -> Path:
    rule = next((r for r in load_registry() if r.get("rule_id") == rule_id), None)
    if rule is None:
        raise ValueError(f"unknown rule_id: {rule_id}")
    cleaned = validate_session_params(rule_id, params)
    _TUNING_DIR.mkdir(parents=True, exist_ok=True)

    if scope == "global":
        path = _TUNING_DIR / "defaults.yaml"
        root = _load_tuning_file("defaults.yaml")
        rules = root.setdefault("rules", {})
        rules.setdefault(rule_id, {}).update(cleaned)
    elif scope == "building":
        if not building_id:
            raise ValueError("building_id required for building scope")
        path = _TUNING_DIR / "building_overrides.yaml"
        root = _load_tuning_file("building_overrides.yaml")
        root.setdefault(building_id, {}).setdefault(rule_id, {}).update(cleaned)
    elif scope == "equipment":
        if not equipment_id:
            raise ValueError("equipment_id required for equipment scope")
        path = _TUNING_DIR / "equipment_overrides.yaml"
        root = _load_tuning_file("equipment_overrides.yaml")
        root.setdefault(equipment_id, {}).setdefault(rule_id, {}).update(cleaned)
    else:
        raise ValueError(f"invalid scope: {scope}")

    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML required to save tuning profiles") from exc
    path.write_text(yaml.safe_dump(root, sort_keys=False), encoding="utf-8")
    load_registry.cache_clear()
    return path


def preview_rule_result(
    rule_id: str,
    equipment_id: str,
    params: dict[str, float] | None = None,
    *,
    use_rust_cache: bool = True,
) -> dict[str, Any]:
    """Return cached Rust rule row for one equipment, if available."""
    if not use_rust_cache or not rust_cache_enabled():
        return {
            "ok": False,
            "available": False,
            "reason": "Rust cache disabled (set VIBE19_RUST_CACHE=1)",
        }
    cache_path = _APP19 / ".cache" / "rule_results" / f"{rule_id}.json"
    if not cache_path.is_file():
        return {
            "ok": False,
            "available": False,
            "reason": "Run Rust cache warmup (ingest + run-rules) first",
        }
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "available": False, "reason": "corrupt rule cache"}
    rows = payload.get("rows") or []
    match = next((r for r in rows if r.get("equipment_id") == equipment_id), None)
    if match is None:
        return {
            "ok": True,
            "available": True,
            "rule_id": rule_id,
            "equipment_id": equipment_id,
            "row": None,
            "note": "No row for equipment (missing roles or no fault samples)",
            "params_requested": params or {},
        }
    return {
        "ok": True,
        "available": True,
        "rule_id": rule_id,
        "equipment_id": equipment_id,
        "row": match,
        "params_requested": params or {},
        "note": "Preview from last batch run-rules cache; per-request param injection pending",
    }
