"""Flask WSGI app for Vibe 21 DM twin inference + optional WebGL static serve."""

from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS

from .model_loader import load_bundle
from .predict import STRATEGIES, predict_kw

_VIBE21 = Path(__file__).resolve().parents[1]
_TWIN = _VIBE21 / "assets" / "twin_b100_ops11"
# WebGL build lives next to the package (or override with VIBE21_WEBGL_DIR)
_WEBGL = Path(os.environ.get("VIBE21_WEBGL_DIR", str(_VIBE21 / "flask_app" / "webgl"))).resolve()
_STATIC = Path(__file__).resolve().parent / "static"
_NOTEBOOK_HTML = _STATIC / "notebooks" / "demand_hourly_training_walkthrough.html"

mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("application/octet-stream", ".data")
mimetypes.add_type("text/javascript", ".js")


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    @app.after_request
    def add_unity_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/api/v1/health")
    def health():
        ok = True
        detail: dict = {"service": "vibe21-dm-twin", "status": "ok"}
        try:
            b = load_bundle()
            detail["model_id"] = b["card"].get("model_id")
            detail["model_status"] = b["card"].get("status")
            detail["artifact_sha256"] = b["artifact_sha256"]
            detail["artifact_path"] = b.get("artifact_path")
        except Exception as exc:  # noqa: BLE001 — surface load errors in health
            ok = False
            detail["status"] = "degraded"
            detail["model_error"] = str(exc)
        return jsonify(detail), (200 if ok else 503)

    @app.get("/api/v1/twin/manifest")
    def twin_manifest():
        path = _TWIN / "unity_twin_manifest.json"
        if not path.is_file():
            return jsonify({"error": "twin manifest missing", "path": str(path)}), 404
        data = json.loads(path.read_text(encoding="utf-8"))
        data["geometry_url"] = "/api/v1/twin/geometry"
        data["predict_url"] = "/api/v1/predict/demand_hourly"
        data["honesty"] = (
            "Floor×AHU lumped zones only. Roof AHU / zone sensors in Unity are DEMO proxies. "
            "ML is ENERGYPLUS_SIMULATED CANDIDATE until BAS-validated."
        )
        return jsonify(data)

    @app.get("/api/v1/twin/geometry")
    def twin_geometry():
        path = _TWIN / "unity_geometry.json"
        if not path.is_file():
            return jsonify({"error": "geometry missing"}), 404
        return jsonify(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/api/v1/models")
    def models():
        try:
            b = load_bundle()
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": str(exc), "models": []}), 503
        card = b["card"]
        return jsonify(
            {
                "models": [
                    {
                        "model_id": card.get("model_id"),
                        "status": card.get("status"),
                        "family": card.get("family"),
                        "champion": card.get("champion"),
                        "targets": card.get("targets"),
                        "cv_metrics": card.get("cv_metrics"),
                        "artifact_sha256": b["artifact_sha256"],
                        "honesty": card.get("honesty"),
                        "strategies": list(STRATEGIES),
                    }
                ]
            }
        )

    @app.post("/api/v1/predict/demand_hourly")
    def predict_demand_hourly():
        body = request.get_json(silent=True) or {}
        try:
            b = load_bundle()
            out = predict_kw(b["model"], body, b["feature_cols"])
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 503
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"predict failed: {exc}"}), 500
        card = b["card"]
        out["model_id"] = card.get("model_id")
        out["model_status"] = card.get("status")
        out["provenance"] = {
            "source": card.get("training_source", "ENERGYPLUS_SIMULATED"),
            "engine": card.get("engine"),
            "artifact_sha256": b["artifact_sha256"],
            "honesty": card.get("honesty"),
        }
        return jsonify(out)

    @app.get("/notebooks/demand_hourly")
    def notebook_demand_hourly():
        """Read-only HTML export of the training notebook (GitHub-like)."""
        if not _NOTEBOOK_HTML.is_file():
            return jsonify(
                {
                    "error": "notebook HTML missing",
                    "hint": "Run jupyter nbconvert on notebooks/demand_hourly_training_walkthrough.ipynb",
                    "expected": str(_NOTEBOOK_HTML),
                }
            ), 404
        return send_from_directory(_NOTEBOOK_HTML.parent, _NOTEBOOK_HTML.name)

    def _webgl_ready() -> bool:
        return (_WEBGL / "index.html").is_file()

    @app.get("/")
    def index():
        if not _webgl_ready():
            return jsonify(
                {
                    "service": "vibe21-dm-twin",
                    "message": "API up. Drop a Unity WebGL build into flask_app/webgl/ (index.html + Build/).",
                    "health": "/api/v1/health",
                    "predict": "/api/v1/predict/demand_hourly",
                    "notebook": "/notebooks/demand_hourly",
                    "webgl_dir": str(_WEBGL),
                }
            )
        return send_from_directory(_WEBGL, "index.html")

    @app.get("/<path:filename>")
    def webgl_file(filename: str):
        if filename.startswith("api/") or filename.startswith("notebooks/"):
            abort(404)
        if not _webgl_ready():
            abort(404)
        requested = (_WEBGL / filename).resolve()
        try:
            requested.relative_to(_WEBGL)
        except ValueError:
            abort(404)
        if not requested.is_file():
            abort(404)
        return send_from_directory(_WEBGL, filename)

    return app


def main() -> None:
    port = int(os.environ.get("VIBE21_PORT", "5050"))
    app = create_app()
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
