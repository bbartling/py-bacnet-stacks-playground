"""Data model API handlers for web Lambda."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from assistant_import import extract_import_shape_from_llm_output
from brick_fdd_runner import run_brick_scoped_rules
from brick_model import graph_from_point_registry
from data_model_prompt import SYSTEM_PROMPT, build_openclaw_user_message, get_data_model_redesign_prompt
from model_schema import ModelImportBody, ModelValidateBody, normalize_model_payload, validate_model
from model_store import ModelStore
from ttl_service import TtlService

TTL_SYNC_INTERVAL_SECONDS = int(os.environ.get("VIBE12_TTL_SYNC_INTERVAL_SECONDS", "300"))


def _parse_data_model_path(path: str) -> tuple[str, str, str] | None:
    """Return (site_id, building_id, action) from /api/data-model/{site}/{building}/..."""
    parts = [p for p in path.split("/") if p]
    # api, data-model, site, building, [action...]
    if len(parts) < 4 or parts[0] != "api" or parts[1] != "data-model":
        return None
    site_id, building_id = parts[2], parts[3]
    action = "/".join(parts[4:]) if len(parts) > 4 else "export"
    return site_id, building_id, action


def _registry_series_ids(ts_store, site_id: str, building_id: str) -> set[str]:
    return {
        str(p.get("series_id"))
        for p in ts_store.list_points(site_id, building_id)
        if p.get("series_id")
    }


def handle_data_model(
    path: str,
    method: str,
    body: dict[str, Any],
    query: dict[str, Any],
    ts_store,
    load_rules_fn,
) -> tuple[int, Any, str]:
    """Returns (status, body, content_type). content_type application/json unless text/plain."""
    parsed = _parse_data_model_path(path)
    if parsed is None:
        return 400, {"error": "use /api/data-model/{site_id}/{building_id}/..."}, "application/json"
    site_id, building_id, action = parsed
    store = ModelStore(ts_store)
    ttl_svc = TtlService()

    if action == "export" and method == "GET":
        model = store.load_or_bootstrap(site_id, building_id)
        return 200, model, "application/json"

    if action == "validate" and method == "POST":
        payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
        reg = _registry_series_ids(ts_store, site_id, building_id)
        result = validate_model(payload or {}, registry_series_ids=reg)
        return 200, result, "application/json"

    if action == "import" and method == "POST":
        try:
            imp = ModelImportBody.model_validate(body)
        except Exception as exc:  # noqa: BLE001
            return 400, {"error": f"invalid import body: {exc}"}, "application/json"
        payload = normalize_model_payload(imp.payload.model_dump(mode="python"))
        if imp.replace:
            store.save(site_id, building_id, payload)
        else:
            cur = store.load(site_id, building_id, bootstrap=False)
            merged = {
                "sites": list(cur.get("sites", [])) + list(payload.get("sites", [])),
                "equipment": list(cur.get("equipment", [])) + list(payload.get("equipment", [])),
                "points": list(cur.get("points", [])) + list(payload.get("points", [])),
                "relationships": list(cur.get("relationships", [])) + list(payload.get("relationships", [])),
            }
            store.save(site_id, building_id, merged)
            payload = merged
        try:
            ttl_svc.sync_to_store(ts_store, site_id, building_id, payload)
        except Exception as exc:  # noqa: BLE001
            ts_store.put_ttl(site_id, building_id, "", sync_error=str(exc))
        graph = graph_from_point_registry(site_id, building_id, ts_store.list_points(site_id, building_id))
        ts_store.put_brick_graph(site_id, building_id, graph)
        return 200, {
            "sites": len(payload.get("sites", [])),
            "equipment": len(payload.get("equipment", [])),
            "points": len(payload.get("points", [])),
        }, "application/json"

    if action == "ttl" and method == "GET":
        sync = str(query.get("sync", "")).lower() in ("true", "1", "yes")
        if sync:
            model = store.load_or_bootstrap(site_id, building_id)
            ttl = ttl_svc.sync_to_store(ts_store, site_id, building_id, model)
        else:
            ttl = ts_store.get_ttl(site_id, building_id)
            if ttl is None:
                model = store.load_or_bootstrap(site_id, building_id)
                ttl = ttl_svc.build_ttl(model)
        return 200, ttl, "text/plain; charset=utf-8"

    if action == "ttl/status" and method == "GET":
        status = ts_store.get_ttl_status(site_id, building_id)
        status["sync_interval_seconds"] = TTL_SYNC_INTERVAL_SECONDS
        return 200, status, "application/json"

    if action == "ttl/sync" and method == "POST":
        model = store.load_or_bootstrap(site_id, building_id)
        try:
            ttl = ttl_svc.sync_to_store(ts_store, site_id, building_id, model)
            return 200, {"ok": True, "bytes": len(ttl)}, "application/json"
        except Exception as exc:  # noqa: BLE001
            ts_store.put_ttl(site_id, building_id, "", sync_error=str(exc))
            return 500, {"error": str(exc)}, "application/json"

    if action == "health" and method == "GET":
        model = store.load_or_bootstrap(site_id, building_id)
        reg = _registry_series_ids(ts_store, site_id, building_id)
        return 200, validate_model(model, registry_series_ids=reg), "application/json"

    if action == "assistant/openclaw" and method == "POST":
        token = os.environ.get("VIBE12_OPENCLAW_GATEWAY_TOKEN", "").strip()
        gateway_url = os.environ.get(
            "VIBE12_OPENCLAW_GATEWAY_URL", "http://127.0.0.1:18789"
        ).rstrip("/")
        if not token:
            return 503, {
                "error": "OpenClaw not configured",
                "hint": "Set VIBE12_OPENCLAW_GATEWAY_TOKEN on WebFunction",
            }, "application/json"
        model = store.load_or_bootstrap(site_id, building_id)
        rules, _, _ = load_rules_fn()
        user_msg = build_openclaw_user_message(model, rules)
        chat_body = json.dumps(
            {
                "model": os.environ.get("VIBE12_OPENCLAW_MODEL", "openclaw"),
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{gateway_url}/v1/chat/completions",
            data=chat_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return 502, {"error": f"OpenClaw HTTP {exc.code}", "detail": exc.read().decode()[:500]}, "application/json"
        except Exception as exc:  # noqa: BLE001
            return 502, {"error": str(exc)}, "application/json"
        content = ""
        choices = raw.get("choices") or []
        if choices:
            content = (choices[0].get("message") or {}).get("content") or ""
        import_ready = extract_import_shape_from_llm_output(content)
        wrapper: dict[str, Any] = {}
        try:
            wrapper = json.loads(content) if content.strip().startswith("{") else {}
        except json.JSONDecodeError:
            wrapper = {}
        return 200, {
            "import_ready": import_ready,
            "import_ready_parse_ok": import_ready is not None,
            "validation_notes": wrapper.get("validation_notes", ""),
            "relationship_summary": wrapper.get("relationship_summary", ""),
            "rule_compatibility_notes": wrapper.get("rule_compatibility_notes", ""),
            "raw_content": content[:8000],
        }, "application/json"

    if action == "prompt" and method == "GET":
        return 200, {"prompt": get_data_model_redesign_prompt(human_mode=True)}, "application/json"

    return 404, {"error": f"unknown data-model action: {action}"}, "application/json"


def sync_all_ttl(ts_store) -> dict[str, Any]:
    """Sync TTL for all buildings with canonical models (EventBridge / FDD Lambda)."""
    ttl_svc = TtlService()
    store = ModelStore(ts_store)
    synced: list[str] = []
    errors: list[str] = []
    for b in ts_store.list_buildings_with_model():
        sid, bid = b["site_id"], b["building_id"]
        try:
            model = store.load(sid, bid, bootstrap=False)
            ttl_svc.sync_to_store(ts_store, sid, bid, model)
            synced.append(f"{sid}/{bid}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{sid}/{bid}: {exc}")
            ts_store.put_ttl(sid, bid, "", sync_error=str(exc))
    return {"synced": synced, "errors": errors, "count": len(synced)}
