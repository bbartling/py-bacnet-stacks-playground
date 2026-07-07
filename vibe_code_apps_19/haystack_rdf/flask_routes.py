"""Flask blueprint for Haystack RDF / SPARQL data model API."""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Blueprint, Response, jsonify, request

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
from haystack_rdf.model_store import ModelStore
from haystack_rdf.sparql_queries import (
    execute_model_sparql,
    predefined_catalog,
    validate_all_predefined,
)
from haystack_rdf.ttl_graph import TtlGraphError
from shared.data_config import get_config

rdf_bp = Blueprint("rdf", __name__, url_prefix="/api/rdf")


def _svc() -> ModelService:
    return ModelService()


@rdf_bp.route("/health")
def rdf_health():
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
        return jsonify({
            "ok": True,
            "building": cfg.building,
            "data_root": str(cfg.data_root),
            "csv_bundles": len(bundles),
            "summary": summary,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


@rdf_bp.route("/bootstrap", methods=["POST"])
def rdf_bootstrap():
    force = bool((request.get_json(silent=True) or {}).get("force"))
    path = ensure_model_synced(get_config(), force=force)
    summary = query_model_summary()
    return jsonify({"ok": True, "ttl_path": str(path), "summary": summary})


@rdf_bp.route("/model")
def rdf_model():
    return jsonify(_svc().load())


@rdf_bp.route("/export")
def rdf_export():
    return jsonify(_svc().load())


@rdf_bp.route("/commissioning-export")
def rdf_commissioning_export():
    return jsonify(build_commissioning_export(_svc().load()))


@rdf_bp.route("/commissioning-import", methods=["POST"])
def rdf_commissioning_import():
    payload = request.get_json(force=True, silent=True) or {}
    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    model = apply_commissioning_import(body)
    counts = _svc().import_json(model, replace=True)
    return jsonify({"ok": True, "counts": counts})


@rdf_bp.route("/llm-bundle")
def rdf_llm_bundle():
    return Response(build_llm_bundle(_svc().load()), mimetype="text/plain; charset=utf-8")


@rdf_bp.route("/import", methods=["POST"])
def rdf_import():
    payload = request.get_json(force=True, silent=True) or {}
    counts = _svc().import_json(payload, replace=bool(payload.get("replace", True)))
    return jsonify({"ok": True, "counts": counts})


@rdf_bp.route("/sync-ttl", methods=["POST"])
def rdf_sync_ttl():
    path = _svc().sync_ttl()
    return jsonify({"ok": True, "ttl_path": path})


@rdf_bp.route("/ttl")
def rdf_ttl():
    return Response(_svc().get_ttl_text(), mimetype="text/turtle")


@rdf_bp.route("/sparql/predefined")
def rdf_sparql_predefined():
    return jsonify(predefined_catalog())


@rdf_bp.route("/sparql/validate", methods=["POST"])
def rdf_sparql_validate_all():
    """Run every predefined SPARQL query against synced TTL."""
    try:
        result = validate_all_predefined()
        ok = len(result["failed"]) == 0
        return jsonify({"ok": ok, **result})
    except TtlGraphError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@rdf_bp.route("/sparql", methods=["POST"])
def rdf_sparql():
    payload = request.get_json(force=True, silent=True) or {}
    query = str(payload.get("query") or "")
    try:
        result = execute_model_sparql(query)
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except TtlGraphError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@rdf_bp.route("/summary")
def rdf_summary():
    try:
        return jsonify(query_model_summary())
    except TtlGraphError as exc:
        return jsonify({"error": str(exc)}), 400


@rdf_bp.route("/preview-bootstrap")
def rdf_preview_bootstrap():
    return jsonify(build_model_from_csv(get_config()))
