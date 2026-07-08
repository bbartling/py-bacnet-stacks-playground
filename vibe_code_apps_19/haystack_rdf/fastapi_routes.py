"""FastAPI router for Haystack RDF / SPARQL data model API (mirrors legacy blueprint)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Response
from fastapi.responses import JSONResponse

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from haystack_rdf.auto_sync import ensure_model_synced
from haystack_rdf.commissioning_bundle import (
    apply_commissioning_import,
    build_commissioning_export,
    build_llm_bundle,
)
from haystack_rdf.csv_bootstrap import build_model_from_csv
from haystack_rdf.model_service import ModelService
from haystack_rdf.model_sparql import query_model_summary
from haystack_rdf.sparql_queries import (
    execute_model_sparql,
    predefined_catalog,
    validate_all_predefined,
)
from haystack_rdf.ttl_graph import TtlGraphError
from shared.data_config import get_config

router = APIRouter(prefix="/api/rdf", tags=["rdf"])


def _svc() -> ModelService:
    return ModelService()


@router.get("/health")
def rdf_health() -> Any:
    try:
        cfg = get_config()
        ensure_model_synced(cfg)
        summary = query_model_summary()
        from haystack_rdf.csv_discovery import discover_historian_bundles

        bundles = []
        if cfg.building_dir.is_dir():
            bundles.extend(discover_historian_bundles(cfg.building_dir, building_dir=cfg.building_dir))
        if cfg.weather_dir.is_dir():
            bundles.extend(discover_historian_bundles(cfg.weather_dir))
        return {
            "ok": True,
            "building": cfg.building,
            "data_root": str(cfg.data_root),
            "csv_bundles": len(bundles),
            "summary": summary,
        }
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)


@router.post("/bootstrap")
def rdf_bootstrap(payload: dict = Body(default={})) -> Any:
    force = bool((payload or {}).get("force"))
    path = ensure_model_synced(get_config(), force=force)
    summary = query_model_summary()
    return {"ok": True, "ttl_path": str(path), "summary": summary}


@router.get("/model")
def rdf_model() -> Any:
    return _svc().load()


@router.get("/export")
def rdf_export() -> Any:
    return _svc().load()


@router.get("/commissioning-export")
def rdf_commissioning_export() -> Any:
    return build_commissioning_export(_svc().load())


@router.post("/commissioning-import")
def rdf_commissioning_import(payload: dict = Body(default={})) -> Any:
    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    model = apply_commissioning_import(body)
    counts = _svc().import_json(model, replace=True)
    return {"ok": True, "counts": counts}


@router.get("/llm-bundle")
def rdf_llm_bundle() -> Response:
    return Response(build_llm_bundle(_svc().load()), media_type="text/plain; charset=utf-8")


@router.post("/import")
def rdf_import(payload: dict = Body(default={})) -> Any:
    counts = _svc().import_json(payload, replace=bool(payload.get("replace", True)))
    return {"ok": True, "counts": counts}


@router.post("/sync-ttl")
def rdf_sync_ttl() -> Any:
    path = _svc().sync_ttl()
    return {"ok": True, "ttl_path": path}


@router.get("/ttl")
def rdf_ttl() -> Response:
    return Response(_svc().get_ttl_text(), media_type="text/turtle")


@router.get("/sparql/predefined")
def rdf_sparql_predefined() -> Any:
    return predefined_catalog()


@router.post("/sparql/validate")
def rdf_sparql_validate_all() -> Any:
    try:
        result = validate_all_predefined()
        ok = len(result["failed"]) == 0
        return {"ok": ok, **result}
    except TtlGraphError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@router.post("/sparql")
def rdf_sparql(payload: dict = Body(default={})) -> Any:
    query = str(payload.get("query") or "")
    try:
        result = execute_model_sparql(query)
        return {"ok": True, **result}
    except (ValueError, TtlGraphError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@router.get("/summary")
def rdf_summary() -> Any:
    try:
        return query_model_summary()
    except TtlGraphError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.get("/preview-bootstrap")
def rdf_preview_bootstrap() -> Any:
    return build_model_from_csv(get_config())
