"""
Open FDD Vibe Coder — Flask app for local dev and Docker deploy.

Modes (set env DASHBOARD_MODE):
  full   — local analyst workspace: tune params, refresh charts, export packages
  deploy — serve pre-built site/ (read-only charts + optional live notes)

Deploy analogy:
  site/                  = pre-baked charts
  app.py                 = Flask server
  build_docker_deploy.py = bake site/ for Dockerfile.deploy
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import threading
from datetime import datetime
from html import escape
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, request, send_from_directory

ROOT = Path(__file__).resolve().parent
APP19 = ROOT.parent
if str(APP19) not in sys.path:
    sys.path.insert(0, str(APP19))

from shared.env_loader import load_env_files  # noqa: E402

load_env_files()
SITE_DIR = ROOT / "site"
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
NOTES_FILE = DATA_DIR / "analyst_notes.json"
SESSION_FILE = ROOT / "analyst_session.json"

MODE = os.environ.get("DASHBOARD_MODE", "full").lower()
ANALYST_ENABLED = os.environ.get("ANALYST_ENABLED", "1" if MODE == "full" else "0") == "1"


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    STATIC_DIR.mkdir(exist_ok=True)


def load_live_notes() -> dict[str, str]:
    _ensure_dirs()
    if NOTES_FILE.is_file():
        try:
            data = json.loads(NOTES_FILE.read_text(encoding="utf-8"))
            return {k: str(v) for k, v in data.get("notes_by_page", data).items()}
        except json.JSONDecodeError:
            pass
    return {}


def save_live_notes(notes: dict[str, str], analyst_name: str = "") -> None:
    _ensure_dirs()
    payload = {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "analyst_name": analyst_name,
        "notes_by_page": notes,
    }
    NOTES_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _notes_banner_html(page_id: str, notes: str, *, editable: bool) -> str:
    note_display = ""
    if notes.strip():
        safe = escape(notes.strip()).replace("\n", "<br/>")
        note_display = f'<div class="analyst-notes-display"><h3>Analyst notes</h3><p>{safe}</p></div>'

    if not editable:
        if not note_display:
            return ""
        return f'<div class="analyst-delivered">{note_display}</div>'

    return f"""
<div class="analyst-panel notes-only" id="analyst-panel" data-page="{page_id}">
  <div class="analyst-panel-head">
    <strong>Analyst notes</strong>
    <span class="analyst-tag">Read-only charts · edit notes only (rebuild zip locally to update charts)</span>
    <div class="analyst-actions">
      <button type="button" class="btn primary" id="btn-save-notes">Save notes</button>
    </div>
  </div>
  <div class="notes-col">
    <label for="page-notes">Notes for this page</label>
    <textarea id="page-notes" rows="5" placeholder="Findings, caveats, recommended actions…">{escape(notes)}</textarea>
  </div>
  {note_display}
</div>
<script src="/static/dashboard_notes.js"></script>
<script>window.DASHBOARD_PAGE = "{page_id}";</script>
"""


def _inject_after_main_open(html: str, injection: str) -> str:
    if not injection:
        return html
    # Replace existing delivered notes block if present
    html = re.sub(r'<div class="analyst-delivered">.*?</div>\s*', "", html, count=1, flags=re.DOTALL)
    marker = "<main>"
    if marker in html:
        return html.replace(marker, marker + injection, 1)
    return injection + html


def _inject_notes_css(html: str) -> str:
    if "analyst-panel" in html and ".analyst-panel {" in html:
        return html
    css = """
.analyst-panel { background: #111827; border: 1px solid #334155; border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 1rem; }
.analyst-panel-head { display: flex; flex-wrap: wrap; align-items: center; gap: .75rem; margin-bottom: .75rem; }
.analyst-actions { margin-left: auto; }
.notes-col label { display: block; font-size: .8rem; color: var(--muted); margin-bottom: .35rem; }
.notes-col textarea { width: 100%; background: #0f1419; color: var(--text); border: 1px solid #334155; border-radius: 8px; padding: .6rem; font-family: inherit; resize: vertical; }
.btn { background: #243044; color: var(--text); border: 1px solid #334155; border-radius: 6px; padding: .4rem .75rem; cursor: pointer; font-size: .8rem; }
.btn.primary { background: #3b82f6; border-color: #3b82f6; color: #fff; }
.analyst-notes-display { margin-top: .75rem; padding: .75rem; background: #0f1419; border-radius: 8px; border-left: 3px solid #3b82f6; }
.analyst-notes-display h3 { margin: 0 0 .35rem; font-size: .9rem; }
.analyst-tag { font-size: .75rem; color: #8b9cb3; }
.analyst-delivered { margin-bottom: 1rem; }
"""
    return html.replace("</style>", css + "\n</style>", 1)


def create_app(mode: str | None = None) -> Flask:
    global MODE
    if mode:
        MODE = mode.lower()

    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    _ensure_dirs()

    from haystack_rdf.auto_sync import ensure_model_synced
    from haystack_rdf.flask_routes import rdf_bp
    from shared.data_config import get_config

    try:
        cfg = get_config()
        if cfg.building_dir.is_dir() or cfg.weather_dir.is_dir():
            def _haystack_bg() -> None:
                try:
                    ensure_model_synced(cfg)
                except Exception as exc:
                    print(f"[haystack] auto-sync failed: {exc}")

            threading.Thread(target=_haystack_bg, daemon=True).start()
    except Exception as exc:
        print(f"[haystack] auto-sync skipped: {exc}")

    app.register_blueprint(rdf_bp)

    if MODE == "deploy":
        _register_deploy_routes(app)
    else:
        _register_full_routes(app)

    return app


def _register_deploy_routes(app: Flask) -> None:
    """Serve pre-built site/ — deploy mode (Docker / static hosting)."""

    @app.route("/")
    def home():
        return redirect("/index.html")

    @app.route("/api/notes", methods=["GET", "POST"])
    def api_notes():
        if request.method == "GET":
            page = request.args.get("page", "index")
            notes = load_live_notes()
            return jsonify({
                "page": page,
                "note": notes.get(page, ""),
                "notes": notes,
                "analyst_enabled": ANALYST_ENABLED,
            })

        if not ANALYST_ENABLED:
            return jsonify({"error": "Analyst notes editing is disabled"}), 403

        payload = request.get_json(force=True, silent=True) or {}
        page = str(payload.get("page", "index"))
        text = str(payload.get("note", ""))
        notes = load_live_notes()
        notes[page] = text
        save_live_notes(notes, str(payload.get("analyst_name", "")))
        return jsonify({"ok": True, "page": page, "note": text})

    @app.route("/health")
    def health():
        return jsonify({"ok": True, "mode": "deploy", "site": SITE_DIR.is_dir()})

    @app.route("/<path:filename>")
    def serve_deploy(filename: str):
        if filename.startswith("api/"):
            return jsonify({"error": "not found"}), 404

        if filename.endswith(".html"):
            page_id = filename[:-5]
            path = SITE_DIR / filename
            if not path.is_file():
                return jsonify({"error": f"Missing page {filename}. Run build_docker_deploy.py locally."}), 404

            notes = load_live_notes()
            note_text = notes.get(page_id, "")
            html = path.read_text(encoding="utf-8")
            banner = _notes_banner_html(page_id, note_text, editable=ANALYST_ENABLED)
            html = _inject_notes_css(html)
            html = _inject_after_main_open(html, banner)
            return Response(html, mimetype="text/html")

        # Static assets live under site/ (plotly, csv, etc.)
        path = SITE_DIR / filename
        if path.is_file():
            return send_from_directory(SITE_DIR, filename)
        return jsonify({"error": "not found"}), 404


def _register_full_routes(app: Flask) -> None:
    """Local analyst mode — tune, refresh, export."""
    import generate_dashboard as gd
    from dashboard_cache import get_body, get_context, get_raw_data as cache_get_raw, prewarm, should_rebuild_economizer_diagnostics
    from dashboard_params import (
        PAGE_IDS,
        PARAM_DEFS,
        apply_to_generate_dashboard,
        default_params,
        load_session,
        params_by_rule,
        params_for_page,
        save_session,
        validate_params,
    )
    from package_dashboard import build_readonly_package

    LOADING_BODY = (
        '<div class="card loading-card"><h2>Loading charts…</h2>'
        '<p class="note">Pulling CSV data and computing FDD metrics. '
        "First load can take 30–90 seconds; later loads use cache.</p></div>"
    )

    def ensure_assets() -> None:
        js = ROOT / "plotly.min.js"
        if not js.exists():
            import plotly

            src = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
            shutil.copy(src, js)

    def get_raw_data() -> dict:
        return cache_get_raw(gd.load_raw_data, gd.raw_data_source_paths())

    def recompute(params: dict | None = None, page_id: str | None = None) -> dict:
        p = validate_params(params or load_session()["params"])
        apply_to_generate_dashboard(gd, p)
        gd.meta["created"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        return get_context(gd.compute_context, get_raw_data(), p, page_id=page_id)

    def _maybe_build_econ_diag(page_id: str, params: dict) -> None:
        if page_id != "economizer_diagnostics":
            return
        if not should_rebuild_economizer_diagnostics(params):
            return
        from economizer_diagnostics_page import build_page

        build_page(gd.meta["created"], params=params)

    @app.route("/data_model.html")
    def data_model_page():
        return send_from_directory(STATIC_DIR, "data_model.html")

    @app.route("/")
    def home():
        return redirect("/index.html")

    @app.route("/api/config", methods=["GET", "POST"])
    def api_config():
        if request.method == "GET":
            session = load_session()
            page = request.args.get("page", "index")
            return jsonify({
                "params": session["params"],
                "notes": session.get("notes", {}),
                "analyst_name": session.get("analyst_name", ""),
                "package_title": session.get("package_title", "Open FDD Vibe Coder"),
                "page_params": params_for_page(page),
                "params_by_rule": params_by_rule(page),
                "param_defs": PARAM_DEFS,
            })

        payload = request.get_json(force=True, silent=True) or {}
        session = load_session()
        if "params" in payload:
            session["params"] = validate_params({**session["params"], **payload["params"]})
        if "notes" in payload:
            session["notes"] = {**session.get("notes", {}), **payload["notes"]}
        if "analyst_name" in payload:
            session["analyst_name"] = str(payload["analyst_name"])
        if "package_title" in payload:
            session["package_title"] = str(payload["package_title"])
        save_session(session)
        return jsonify({"ok": True, "session": session})

    @app.route("/api/refresh/<page_id>", methods=["POST"])
    def api_refresh(page_id: str):
        if page_id not in PAGE_IDS:
            return jsonify({"error": f"Unknown page {page_id}"}), 404

        payload = request.get_json(force=True, silent=True) or {}
        session = load_session()
        params = validate_params({**session["params"], **payload.get("params", {})})
        notes = {**session.get("notes", {}), **payload.get("notes", {})}
        if payload.get("note") is not None:
            notes[page_id] = str(payload["note"])
        session["params"] = params
        session["notes"] = notes
        save_session(session)

        ctx = recompute(params, page_id=page_id)
        _maybe_build_econ_diag(page_id, params)

        body = get_body(gd.body_for_page, ctx, params, page_id)
        return jsonify({"ok": True, "page_id": page_id, "content": body, "params": params})

    @app.route("/api/export", methods=["POST"])
    def api_export():
        result = build_readonly_package(from_session=True)
        return jsonify(result)

    @app.route("/health")
    def health():
        from shared.branding import APP_TITLE
        from shared.data_config import get_config

        cfg = get_config()
        data_ok = cfg.building_dir.is_dir()
        try:
            paths = gd.raw_data_source_paths()
            hist_count = sum(1 for p in paths if p.is_file())
        except Exception as exc:
            return jsonify({
                "ok": False,
                "app": APP_TITLE,
                "mode": "full",
                "building": cfg.building,
                "data_root": str(cfg.data_root),
                "error": str(exc),
            }), 503
        return jsonify({
            "ok": data_ok and hist_count > 0,
            "app": APP_TITLE,
            "mode": "full",
            "building": cfg.building,
            "data_root": str(cfg.data_root),
            "historian_files": hist_count,
        })

    @app.route("/<path:filename>")
    def serve_full(filename: str):
        if filename.startswith("api/"):
            return jsonify({"error": "not found"}), 404

        if filename.endswith(".html"):
            page_id = filename[:-5]
            if page_id not in PAGE_IDS:
                return send_from_directory(ROOT, filename)

            session = load_session()
            params = validate_params(session["params"])
            gd.meta.setdefault("created", datetime.now().strftime("%Y-%m-%d %H:%M"))
            # Shell loads instantly; dashboard_tune.js fetches chart body via /api/refresh.
            html = gd.render_page_html(
                page_id,
                {},
                body_html=LOADING_BODY,
                params=params,
                notes=session.get("notes", {}).get(page_id, ""),
                analyst_name=session.get("analyst_name", ""),
                interactive=True,
            )
            return Response(html, mimetype="text/html")

        path = ROOT / filename
        if path.is_file():
            return send_from_directory(ROOT, filename)
        return jsonify({"error": "not found"}), 404

    # Kick warmup as soon as routes register (don't wait for first browser hit).
    def _startup_warmup() -> None:
        if hasattr(app, "_warmup_started"):
            return
        app._warmup_started = True  # type: ignore[attr-defined]
        ensure_assets()

        def _bg() -> None:
            import time

            time.sleep(1.5)
            try:
                raw = get_raw_data()
                p = validate_params(load_session().get("params", default_params()))
                apply_to_generate_dashboard(gd, p)
                prewarm(gd.compute_context, raw, p, ["index", "ahu_1", "ahu_2", "economizer"])
                print("[dashboard] startup warmup complete")
            except Exception as exc:
                print(f"[dashboard] startup warmup failed: {exc}")

        threading.Thread(target=_bg, daemon=True).start()

    _startup_warmup()


# WSGI / Gunicorn entry (see wsgi.py)
application = create_app()


def main() -> None:
    mode_label = "deploy (read-only site/)" if MODE == "deploy" else "full (local analyst)"
    from shared.branding import APP_TITLE

    print(f"{APP_TITLE} — {mode_label}")
    print("Open http://127.0.0.1:5000/index.html")
    application.run(host="127.0.0.1", port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()
