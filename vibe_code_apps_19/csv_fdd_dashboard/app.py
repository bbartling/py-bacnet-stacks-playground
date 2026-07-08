"""
Open FDD Vibe Coder — FastAPI app for local dev and Docker deploy.

Why FastAPI: the analyst/ML surface (custom rule plugins, Pydantic manifests) is
API-first and forkable. FastAPI gives typed request validation + free OpenAPI docs
at /docs, matching the open-fdd bridge architecture. CPU-bound pandas work is
unaffected — sync endpoints run in Starlette's threadpool and results stay cached.

Modes (set env DASHBOARD_MODE):
  full   — local analyst workspace: tune params, refresh charts, export packages (default)
  api    — JSON API only (Flavor A): same /api/* contract, no HTML page shells; /docs for OpenAPI
  deploy — serve pre-built site/ (read-only charts + optional live notes)

Run:
  python app.py                         # local dev (uvicorn, port 5000)
  uvicorn asgi:app --host 0.0.0.0 --port 5000
  gunicorn -k uvicorn.workers.UvicornWorker --timeout 300 asgi:app
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import sys
import threading
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

ROOT = Path(__file__).resolve().parent
APP19 = ROOT.parent
if str(APP19) not in sys.path:
    sys.path.insert(0, str(APP19))

from shared.env_loader import load_env_files  # noqa: E402

# Imported at module scope so FastAPI can resolve these request-body types when
# building route signatures / the OpenAPI schema (Py 3.14 + `from __future__`
# annotations resolve forward refs against module globals, not closure locals).
from api_models import ConfigBody, LoginBody, NoteActionBody, RefreshBody, RunRuleBody  # noqa: E402

load_env_files()
SITE_DIR = ROOT / "site"
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
NOTES_FILE = DATA_DIR / "analyst_notes.json"
SESSION_FILE = ROOT / "analyst_session.json"

MODE = os.environ.get("DASHBOARD_MODE", "full").lower()
ANALYST_ENABLED = os.environ.get("ANALYST_ENABLED", "1" if MODE == "full" else "0") == "1"
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-vibe-coder-change-me")


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    STATIC_DIR.mkdir(exist_ok=True)


def load_live_notes() -> dict[str, list[dict[str, str]]]:
    from notes_store import migrate_notes

    _ensure_dirs()
    if NOTES_FILE.is_file():
        try:
            data = json.loads(NOTES_FILE.read_text(encoding="utf-8"))
            raw = data.get("notes_by_page", data)
            return migrate_notes(raw)
        except json.JSONDecodeError:
            pass
    return {}


def save_live_notes(notes: dict[str, Any], analyst_name: str = "") -> None:
    from notes_store import migrate_notes

    _ensure_dirs()
    payload = {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "analyst_name": analyst_name,
        "notes_by_page": migrate_notes(notes),
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


def create_app(mode: str | None = None) -> FastAPI:
    global MODE
    if mode:
        MODE = mode.lower()

    app = FastAPI(
        title="Open FDD Vibe Coder",
        description="Local analyst workspace + custom-rule/ML lab for CSV → pandas FDD.",
        version="1.0.0",
    )
    app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie="vibe_fdd_session")
    _ensure_dirs()

    from haystack_rdf.auto_sync import ensure_model_synced
    from haystack_rdf.fastapi_routes import router as rdf_router
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

    app.include_router(rdf_router)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    if MODE == "deploy":
        _register_deploy_routes(app)
    elif MODE == "api":
        _register_full_routes(app, html_shell=False)
    else:
        _register_full_routes(app, html_shell=True)

    return app


def _register_deploy_routes(app: FastAPI) -> None:
    """Serve pre-built site/ — deploy mode (Docker / static hosting)."""

    @app.get("/")
    def home() -> RedirectResponse:
        return RedirectResponse("/index.html")

    @app.get("/api/notes")
    def api_notes_get(page: str = "index") -> JSONResponse:
        from notes_store import posts_for_page

        notes = load_live_notes()
        posts = posts_for_page(notes, page)
        return JSONResponse({
            "page": page,
            "posts": posts,
            "notes": notes,
            "analyst_enabled": ANALYST_ENABLED,
        })

    @app.post("/api/notes")
    def api_notes_post(payload: dict = Body(default={})) -> JSONResponse:
        from notes_store import add_post, migrate_notes, posts_for_page

        if not ANALYST_ENABLED:
            return JSONResponse({"error": "Analyst notes editing is disabled"}, status_code=403)
        page = str(payload.get("page", "index"))
        text = str(payload.get("note", ""))
        notes = load_live_notes()
        notes = migrate_notes(notes)
        if text.strip():
            add_post(notes, page, text, analyst_name=str(payload.get("analyst_name", "")))
        save_live_notes(notes, str(payload.get("analyst_name", "")))
        return JSONResponse({"ok": True, "page": page, "posts": posts_for_page(notes, page)})

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse({"ok": True, "mode": "deploy", "site": SITE_DIR.is_dir()})

    @app.get("/{filename:path}")
    def serve_deploy(filename: str) -> Response:
        if filename.startswith("api/"):
            return JSONResponse({"error": "not found"}, status_code=404)

        if filename.endswith(".html"):
            page_id = filename[:-5]
            path = SITE_DIR / filename
            if not path.is_file():
                return JSONResponse(
                    {"error": f"Missing page {filename}. Run build_docker_deploy.py locally."},
                    status_code=404,
                )
            from notes_store import posts_for_page

            notes = load_live_notes()
            posts = posts_for_page(notes, page_id)
            note_text = "\n\n".join(p["text"] for p in posts)
            html = path.read_text(encoding="utf-8")
            banner = _notes_banner_html(page_id, note_text, editable=ANALYST_ENABLED)
            html = _inject_notes_css(html)
            html = _inject_after_main_open(html, banner)
            return HTMLResponse(html)

        path = SITE_DIR / filename
        if path.is_file():
            return Response(path.read_bytes(), media_type=_guess_media_type(path))
        return JSONResponse({"error": "not found"}, status_code=404)


def _guess_media_type(path: Path) -> str:
    import mimetypes

    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def _register_full_routes(app: FastAPI, *, html_shell: bool = True) -> None:
    """Local analyst mode — tune, refresh, export. Set html_shell=False for headless api mode."""
    import generate_dashboard as gd
    from dashboard_cache import get_body, get_context, get_raw_data as cache_get_raw, prewarm, should_rebuild_economizer_diagnostics
    from dashboard_params import (
        PARAM_DEFS,
        apply_to_generate_dashboard,
        canonicalize_params,
        default_params,
        display_params,
        load_session,
        params_by_rule,
        params_for_page,
        refresh_page_registry,
        save_session,
        validate_params,
    )
    from engineer_auth import can_edit, lock_package, login as engineer_login, logout as engineer_logout, session_flags
    from page_registry import is_valid_page, nav_tree, page_ids

    refresh_page_registry()

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

    def auth_session(request: Request) -> dict:
        data = load_session()
        data["engineer_logged_in"] = bool(request.session.get("engineer_logged_in"))
        return data

    def recompute(params: dict | None = None, page_id: str | None = None, *, units: str | None = None) -> dict:
        from units import set_display_units

        file_sess = load_session()
        unit_mode = units or file_sess.get("units", "imperial")
        set_display_units(unit_mode)
        p = validate_params(params or file_sess["params"])
        apply_to_generate_dashboard(gd, p, file_sess.get("site_settings"))
        gd.meta["created"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        return get_context(gd.compute_context, get_raw_data(), p, page_id=page_id)

    def _maybe_build_econ_diag(page_id: str, params: dict) -> None:
        if page_id != "economizer_diagnostics":
            return
        if not should_rebuild_economizer_diagnostics(params):
            return
        from economizer_diagnostics_page import build_page

        build_page(gd.meta["created"], params=params)

    mode_label = "api" if not html_shell else "full"

    @app.get("/data_model.html")
    def data_model_page() -> Response:
        if not html_shell:
            return JSONResponse(
                {"error": "HTML disabled in api mode", "hint": "Use GET /api/rdf/* for the data model API"},
                status_code=404,
            )
        path = STATIC_DIR / "data_model.html"
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.get("/")
    def home() -> Response:
        if not html_shell:
            from shared.branding import APP_TITLE

            return JSONResponse({
                "app": APP_TITLE,
                "mode": "api",
                "docs": "/docs",
                "openapi": "/openapi.json",
                "hint": "GET /api/pages → POST /api/refresh/{page_id} returns { content: html, analytics, params }",
                "endpoints": {
                    "pages": "GET /api/pages",
                    "session": "GET /api/session",
                    "config": "GET|POST /api/config",
                    "refresh": "POST /api/refresh/{page_id}",
                    "rules": "GET /api/rules",
                    "rules_run": "POST /api/rules/run",
                    "rdf": "GET /api/rdf/*",
                },
            })
        return RedirectResponse("/index.html")

    @app.get("/api/pages")
    def api_pages() -> JSONResponse:
        return JSONResponse({"pages": nav_tree(interactive=True)})

    @app.get("/api/session")
    def api_session(request: Request) -> JSONResponse:
        sess = auth_session(request)
        return JSONResponse({**session_flags(sess), "site_settings": sess.get("site_settings", {})})

    @app.post("/api/login")
    def api_login(request: Request, body: LoginBody) -> JSONResponse:
        if engineer_login(request.session, body.pin):
            return JSONResponse({"ok": True})
        return JSONResponse({"ok": False, "error": "Invalid PIN"}, status_code=401)

    @app.post("/api/logout")
    def api_logout(request: Request) -> JSONResponse:
        engineer_logout(request.session)
        return JSONResponse({"ok": True})

    @app.get("/api/config")
    def api_config_get(request: Request, page: str = "index") -> JSONResponse:
        from notes_store import migrate_notes, posts_for_page
        from units import set_display_units

        session = load_session()
        session["notes"] = migrate_notes(session.get("notes", {}))
        units = session.get("units", "imperial")
        set_display_units(units)
        flags = session_flags({**session, "engineer_logged_in": request.session.get("engineer_logged_in")})
        return JSONResponse({
            "params": display_params(session["params"]),
            "notes": session.get("notes", {}),
            "page_notes": posts_for_page(session.get("notes", {}), page),
            "analyst_name": session.get("analyst_name", ""),
            "package_title": session.get("package_title", "Open FDD Vibe Coder"),
            "page_params": params_for_page(page),
            "params_by_rule": params_by_rule(page),
            "param_defs": PARAM_DEFS,
            "site_settings": session.get("site_settings", {}),
            "units": units,
            "header_meta": gd.header_meta_html(),
            **flags,
        })

    @app.post("/api/config")
    def api_config_post(request: Request, body: ConfigBody) -> JSONResponse:
        if not can_edit(auth_session(request)):
            return JSONResponse({"error": "Read-only — engineer login required"}, status_code=403)
        session = load_session()
        units = session.get("units", "imperial")
        if body.units is not None:
            session["units"] = "metric" if str(body.units).lower() == "metric" else "imperial"
            units = session["units"]
        if body.params is not None:
            session["params"] = canonicalize_params({**session["params"], **body.params}, units)
        if body.notes is not None:
            from notes_store import migrate_notes

            session["notes"] = migrate_notes({**session.get("notes", {}), **body.notes})
        if body.analyst_name is not None:
            session["analyst_name"] = str(body.analyst_name)
        if body.package_title is not None:
            session["package_title"] = str(body.package_title)
        if body.site_settings is not None and isinstance(body.site_settings, dict):
            from shared.occupancy import merge_site_settings
            from shared.data_config import get_config

            session["site_settings"] = merge_site_settings(
                body.site_settings,
                timezone=get_config().site_timezone(),
            )
            if "comfort_setpoint_f" in body.site_settings:
                session["params"]["comfort_setpoint_f"] = float(body.site_settings["comfort_setpoint_f"])
            if "comfort_band_f" in body.site_settings:
                session["params"]["comfort_band_f"] = float(body.site_settings["comfort_band_f"])
            session["params"] = validate_params(session["params"])
        save_session(session)
        return JSONResponse({"ok": True, "session": session, "units": session.get("units", "imperial")})

    @app.post("/api/notes/action")
    def api_notes_action(request: Request, body: NoteActionBody) -> JSONResponse:
        from notes_store import add_post, delete_post, migrate_notes, posts_for_page

        if not can_edit(auth_session(request)):
            return JSONResponse({"error": "Read-only — engineer login required"}, status_code=403)
        session = load_session()
        session["notes"] = migrate_notes(session.get("notes", {}))
        page = body.page or "index"
        if body.action == "delete":
            if not delete_post(session["notes"], page, body.post_id):
                return JSONResponse({"error": "Note not found"}, status_code=404)
        else:
            text = body.text.strip()
            if not text:
                return JSONResponse({"error": "Note text required"}, status_code=400)
            author = body.analyst_name or session.get("analyst_name", "")
            add_post(session["notes"], page, text, author=author)
        if body.analyst_name:
            session["analyst_name"] = body.analyst_name
        save_session(session)
        return JSONResponse({
            "ok": True,
            "page": page,
            "posts": posts_for_page(session["notes"], page),
        })

    @app.post("/api/refresh/{page_id}")
    def api_refresh(request: Request, page_id: str, body: RefreshBody) -> JSONResponse:
        from notes_store import migrate_notes

        if not is_valid_page(page_id):
            return JSONResponse({"error": f"Unknown page {page_id}"}, status_code=404)

        session = load_session()
        auth = auth_session(request)
        units = body.units or session.get("units", "imperial")
        session["units"] = "metric" if str(units).lower() == "metric" else "imperial"
        if can_edit(auth) and body.params:
            params = canonicalize_params({**session["params"], **body.params}, session["units"])
        else:
            params = validate_params(session["params"])
        session["notes"] = migrate_notes({**session.get("notes", {}), **body.notes})
        session["params"] = params
        save_session(session)

        ctx = recompute(params, page_id=page_id, units=session["units"])
        _maybe_build_econ_diag(page_id, params)
        if page_id == "economizer":
            _maybe_build_econ_diag("economizer_diagnostics", params)

        body_html = get_body(gd.body_for_page, ctx, params, page_id)
        analytics = {"ecms": []}
        try:
            from analytics_rollups import rollup_ahu

            if "ahu1" in ctx:
                occ = gd.is_occupied(ctx["ahu1"]["timestamp"])
                analytics["ecms"] = rollup_ahu(ctx["ahu1"], poll_seconds=gd.POLL_SECONDS, occupied=occ)
            elif "ahu_df" in ctx:
                occ = gd.is_occupied(ctx["ahu_df"]["timestamp"])
                analytics["ecms"] = rollup_ahu(ctx["ahu_df"], poll_seconds=gd.POLL_SECONDS, occupied=occ)
        except Exception:
            pass
        return JSONResponse({
            "ok": True,
            "page_id": page_id,
            "content": body_html,
            "params": display_params(params),
            "analytics": analytics,
            "units": session["units"],
            "header_meta": gd.header_meta_html(),
        })

    @app.get("/api/rules")
    def api_rules(reload: str = "") -> JSONResponse:
        from rules import get_registry

        reg = get_registry(force=(reload == "1"))
        return JSONResponse({
            "rules": reg.catalog(),
            "errors": reg.errors,
            "equipment": gd.rule_equipment_ids(),
        })

    @app.post("/api/rules/run")
    def api_rules_run(body: RunRuleBody) -> JSONResponse:
        from rules import RuleContext, get_registry

        rule_id = str(body.rule_id)
        equipment_id = str(body.equipment_id or (gd.rule_equipment_ids() or [""])[0])
        params = body.params or {}

        reg = get_registry()
        if reg.get(rule_id) is None:
            return JSONResponse({"ok": False, "error": f"Unknown rule {rule_id}"}, status_code=404)

        file_sess = load_session()
        p = validate_params(file_sess["params"])
        apply_to_generate_dashboard(gd, p, file_sess.get("site_settings"))
        try:
            frame = gd.rule_ahu_frame(get_raw_data(), equipment_id)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"Could not load {equipment_id}: {exc}"}, status_code=400)

        poll = float(frame.attrs.get("effective_poll_seconds", gd.POLL_SECONDS))
        ctx = RuleContext(
            equipment_id=equipment_id,
            df=frame,
            poll_seconds=poll,
            tz=gd.TZ,
            params={k: v for k, v in params.items() if v is not None},
        )
        try:
            result = reg.run(rule_id, ctx)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"Rule failed: {type(exc).__name__}: {exc}"}, status_code=500)

        chart = ""
        if result.fault_series is not None or result.plot_series:
            title = f"{rule_id} · {equipment_id}"
            chart = gd.rule_result_chart(result.plot_series, result.fault_series, title)

        return JSONResponse({
            "ok": True,
            "rule_id": rule_id,
            "equipment_id": equipment_id,
            "summary": {
                "total_hours": result.total_hours,
                "fault_hours": result.fault_hours,
                "fault_pct": result.fault_pct,
                "message": result.message,
                "extra": result.extra,
            },
            "chart": chart,
            "params": ctx.params,
        })

    @app.get("/api/cookbook/catalog")
    def api_cookbook_catalog() -> JSONResponse:
        import cookbook_rules as cb

        return JSONResponse({"rules": cb.catalog()})

    @app.get("/api/cookbook/{page_id}")
    def api_cookbook_get(page_id: str, vav_limit: int = 12) -> JSONResponse:
        import cookbook_engine as ce

        try:
            data = ce.run_page(page_id, vav_limit=vav_limit)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)
        return JSONResponse({"ok": True, **data})

    @app.post("/api/cookbook/{page_id}")
    def api_cookbook_post(page_id: str, body: dict = Body(default={})) -> JSONResponse:
        import cookbook_engine as ce

        params_by_rule = body.get("params_by_rule") or {}
        vav_limit = int(body.get("vav_limit", 12) or 12)
        try:
            data = ce.run_page(page_id, params_by_rule=params_by_rule, vav_limit=vav_limit)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)
        return JSONResponse({"ok": True, **data})

    def _export_records(page_list: list[str]) -> list[dict]:
        from analytics_rollups import rollup_ahu

        file_sess = load_session()
        params = validate_params(file_sess["params"])
        apply_to_generate_dashboard(gd, params, file_sess.get("site_settings"))
        records: list[dict] = []
        raw = get_raw_data()
        for pid in page_list:
            try:
                ctx = get_context(gd.compute_context, raw, params, page_id=pid)
                if "ahu1" in ctx:
                    occ = gd.is_occupied(ctx["ahu1"]["timestamp"])
                    for row in rollup_ahu(ctx["ahu1"], poll_seconds=gd.POLL_SECONDS, occupied=occ):
                        records.append({"page_id": pid, **row})
            except Exception:
                continue
        return records

    def _export_response(records: list[dict], fmt: str) -> Response:
        if fmt == "csv":
            buf = io.StringIO()
            if records:
                writer = csv.DictWriter(buf, fieldnames=sorted({k for r in records for k in r.keys()}))
                writer.writeheader()
                for row in records:
                    writer.writerow(row)
            return Response(
                buf.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=analytics_export.csv"},
            )
        return JSONResponse({"records": records})

    @app.get("/api/analytics/export")
    def api_analytics_export_get(page_id: str = "index", format: str = "json") -> Response:
        page_list = [page_id] if is_valid_page(page_id) else []
        return _export_response(_export_records(page_list), format.lower())

    @app.post("/api/analytics/export")
    def api_analytics_export_post(format: str = "json") -> Response:
        return _export_response(_export_records(page_ids()), format.lower())

    @app.post("/api/export")
    def api_export(request: Request) -> JSONResponse:
        if not can_edit(auth_session(request)):
            return JSONResponse({"error": "Read-only — engineer login required"}, status_code=403)
        result = build_readonly_package(from_session=True)
        file_sess = load_session()
        lock_package(file_sess)
        save_session(file_sess)
        result["locked"] = True
        return JSONResponse(result)

    @app.get("/health")
    def health() -> JSONResponse:
        from shared.branding import APP_TITLE
        from shared.data_config import get_config

        cfg = get_config()
        data_ok = cfg.building_dir.is_dir()
        try:
            paths = gd.raw_data_source_paths()
            hist_count = sum(1 for p in paths if p.is_file())
        except Exception as exc:
            return JSONResponse({
                "ok": False,
                "app": APP_TITLE,
                "mode": mode_label,
                "building": cfg.building,
                "data_root": str(cfg.data_root),
                "error": str(exc),
            }, status_code=503)
        return JSONResponse({
            "ok": data_ok and hist_count > 0,
            "app": APP_TITLE,
            "mode": mode_label,
            "building": cfg.building,
            "data_root": str(cfg.data_root),
            "historian_files": hist_count,
        })

    @app.get("/{filename:path}")
    def serve_full(filename: str) -> Response:
        if filename.startswith("api/"):
            return JSONResponse({"error": "not found"}, status_code=404)

        if filename.endswith(".html"):
            if not html_shell:
                return JSONResponse({
                    "error": "HTML page shells disabled in api mode",
                    "hint": "GET /api/pages then POST /api/refresh/{page_id}",
                    "docs": "/docs",
                }, status_code=404)
            page_id = filename[:-5]
            if not is_valid_page(page_id):
                path = ROOT / filename
                if path.is_file():
                    return HTMLResponse(path.read_text(encoding="utf-8"))
                return JSONResponse({"error": "not found"}, status_code=404)

            session = load_session()
            params = validate_params(session["params"])
            gd.meta.setdefault("created", datetime.now().strftime("%Y-%m-%d %H:%M"))
            html = gd.render_page_html(
                page_id,
                {},
                body_html=LOADING_BODY,
                params=params,
                notes="",
                analyst_name=session.get("analyst_name", ""),
                interactive=True,
            )
            return HTMLResponse(html)

        path = ROOT / filename
        if path.is_file():
            return Response(path.read_bytes(), media_type=_guess_media_type(path))
        return JSONResponse({"error": "not found"}, status_code=404)

    def _startup_warmup() -> None:
        if getattr(app.state, "warmup_started", False):
            return
        app.state.warmup_started = True
        ensure_assets()

        def _bg() -> None:
            import time

            time.sleep(1.5)
            try:
                raw = get_raw_data()
                p = validate_params(load_session().get("params", default_params()))
                file_sess = load_session()
                apply_to_generate_dashboard(gd, p, file_sess.get("site_settings"))
                prewarm(gd.compute_context, raw, p, ["index", "ahu_1", "ahu_2", "economizer", "motor_runtime"])
                print("[dashboard] startup warmup complete")
            except Exception as exc:
                print(f"[dashboard] startup warmup failed: {exc}")

        threading.Thread(target=_bg, daemon=True).start()

    _startup_warmup()


# ASGI entry (see asgi.py / wsgi.py)
application = create_app()
app = application


def main() -> None:
    import uvicorn

    from shared.branding import APP_TITLE

    mode_label = "deploy (read-only site/)" if MODE == "deploy" else (
        "api (JSON only — /docs)" if MODE == "api" else "full (local analyst)"
    )
    print(f"{APP_TITLE} — {mode_label}")
    print("Open http://127.0.0.1:5000/index.html   ·   API docs: http://127.0.0.1:5000/docs")
    uvicorn.run(application, host="127.0.0.1", port=5000, log_level="info")


if __name__ == "__main__":
    main()
