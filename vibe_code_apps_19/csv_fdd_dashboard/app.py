"""
Building 100 dashboard — Flask app for local dev and PythonAnywhere deploy.

Modes (set env DASHBOARD_MODE):
  full   — local analyst workspace: tune params, refresh charts, export packages
  deploy — PythonAnywhere: serve pre-built site/ (read-only charts + optional live notes)

Unity WebGL analogy:
  site/     = WebGL Build folder (pre-baked charts)
  app.py    = thin Flask server
  build_pa_deploy.py = zip for upload
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from html import escape
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, request, send_from_directory

ROOT = Path(__file__).resolve().parent
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

    if MODE == "deploy":
        _register_deploy_routes(app)
    else:
        _register_full_routes(app)

    return app


def _register_deploy_routes(app: Flask) -> None:
    """Serve pre-built site/ — PythonAnywhere production mode."""

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
                return jsonify({"error": f"Missing page {filename}. Run build_pa_deploy.py locally."}), 404

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
    from dashboard_params import (
        PAGE_IDS,
        PARAM_DEFS,
        apply_to_generate_dashboard,
        load_session,
        params_for_page,
        save_session,
        validate_params,
    )
    from package_dashboard import build_readonly_package

    _raw_data: dict | None = None

    def ensure_assets() -> None:
        js = ROOT / "plotly.min.js"
        if not js.exists():
            import plotly

            src = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
            shutil.copy(src, js)

    def get_raw_data() -> dict:
        nonlocal _raw_data
        if _raw_data is None:
            _raw_data = gd.load_raw_data()
        return _raw_data

    def recompute(params: dict | None = None) -> dict:
        p = validate_params(params or load_session()["params"])
        apply_to_generate_dashboard(gd, p)
        gd.meta["created"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        return gd.compute_context(get_raw_data())

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
                "package_title": session.get("package_title", "Building 100 RCx Dashboard"),
                "page_params": params_for_page(page),
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

        ctx = recompute(params)
        if page_id == "economizer_diagnostics":
            from economizer_diagnostics_page import build_page

            gd.meta["created"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            build_page(gd.meta["created"])

        body = gd.body_for_page(page_id, ctx)
        return jsonify({"ok": True, "page_id": page_id, "content": body, "params": params})

    @app.route("/api/export", methods=["POST"])
    def api_export():
        result = build_readonly_package(from_session=True)
        return jsonify(result)

    @app.route("/health")
    def health():
        return jsonify({"ok": True, "mode": "full"})

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
            ctx = recompute(params)
            if page_id == "economizer_diagnostics":
                from economizer_diagnostics_page import build_page

                gd.meta.setdefault("created", datetime.now().strftime("%Y-%m-%d %H:%M"))
                build_page(gd.meta["created"])

            html = gd.render_page_html(
                page_id,
                ctx,
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

    @app.before_request
    def _warmup():
        if not hasattr(app, "_warmed"):
            ensure_assets()
            get_raw_data()
            app._warmed = True  # type: ignore[attr-defined]


# PythonAnywhere WSGI entry
application = create_app()


def main() -> None:
    mode_label = "deploy (read-only site/)" if MODE == "deploy" else "full (local analyst)"
    print(f"Building 100 dashboard — {mode_label}")
    print("Open http://127.0.0.1:5000/index.html")
    application.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
