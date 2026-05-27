#!/usr/bin/env python3
"""Bensserver dial-in dashboard — proxy edge discover jobs + local Codex wake."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
APP_ROOT = ROOT.parent
STATIC_DIR = ROOT / "static"
GATEWAYS_FILE = Path(
    os.environ.get("VIBE12_GATEWAYS_FILE", str(ROOT / "gateways.local.json"))
)
TOKEN = os.environ.get("VIBE12_COMMISSION_TOKEN", "").strip()
BIND_HOST = os.environ.get("VIBE12_DASHBOARD_BIND", "0.0.0.0")
BIND_PORT = int(os.environ.get("VIBE12_DASHBOARD_PORT", "8766"))
WAKE_SCRIPT = APP_ROOT / "vibe12_agent_spec" / "cron_codex" / "bin" / "vibe12_wake.sh"
WAKE_EXPORT = APP_ROOT / "vibe12_agent_spec" / "cron_codex" / "bin" / "vibe12_wake_context_export.py"
JOBS_DIR = ROOT / "jobs"

from codex_runner import run_codex_prompt


def _lan_urls(port: int) -> list[str]:
    urls = [f"http://127.0.0.1:{port}"]
    try:
        import socket

        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM):
            ip = info[4][0]
            if not ip.startswith("127."):
                urls.append(f"http://{ip}:{port}")
    except OSError:
        pass
    try:
        import subprocess

        out = subprocess.check_output(["hostname", "-I"], text=True, timeout=2).strip()
        for ip in out.split():
            if ip and not ip.startswith("127."):
                url = f"http://{ip}:{port}"
                if url not in urls:
                    urls.append(url)
    except (OSError, subprocess.SubprocessError):
        pass
    return urls


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_gateways() -> list[dict[str, Any]]:
    path = GATEWAYS_FILE
    if not path.is_file():
        example = ROOT / "gateways.example.json"
        if example.is_file():
            path = example
        else:
            return []
    return json.loads(path.read_text(encoding="utf-8"))


def _gateway(gateway_id: str) -> dict[str, Any] | None:
    for gw in _load_gateways():
        if gw.get("id") == gateway_id:
            return gw
    return None


def _edge_request(
    gateway: dict[str, Any],
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    base = gateway["edge_url"].rstrip("/")
    url = f"{base}{path}"
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["X-Commission-Token"] = TOKEN
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw else {}
    except HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"error": body or err.reason}
        return err.code, parsed
    except URLError as err:
        return 502, {"error": str(err.reason)}


def _agent_job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _agent_log_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.log"


def _agent_prompt_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.prompt.txt"


def _run_wake(job_id: str, mini_count: int) -> None:
    meta = {
        "id": job_id,
        "kind": "codex_wake",
        "status": "running",
        "started_at": _utc_now(),
        "mini_count": mini_count,
    }
    _agent_job_path(job_id).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log_path = _agent_log_path(job_id)
    env = os.environ.copy()
    env["MINI_INVOCATIONS_PER_WAKE"] = str(mini_count)
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"# codex wake started {_utc_now()}\n\n")
        log.flush()
        if not WAKE_SCRIPT.is_file():
            log.write(f"missing wake script: {WAKE_SCRIPT}\n")
            rc = 127
        else:
            proc = subprocess.run(
                ["/bin/bash", str(WAKE_SCRIPT)],
                cwd=str(APP_ROOT),
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            rc = proc.returncode
    meta["status"] = "ok" if rc == 0 else "failed"
    meta["finished_at"] = _utc_now()
    meta["exit_code"] = rc
    _agent_job_path(job_id).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _export_wake_context() -> None:
    if not WAKE_EXPORT.is_file():
        return
    epoch = APP_ROOT / "vibe12_agent_spec" / "cron_codex" / "logs" / "last_wake_epoch"
    operator = APP_ROOT / "vibe12_agent_spec" / "cron_codex" / "state" / "operator_notes.md"
    notepad = APP_ROOT / "vibe12_agent_spec" / "memory" / "commissioning" / "PHASE_NOTEPAD.md"
    context = APP_ROOT / "vibe12_agent_spec" / "cron_codex" / "state" / "context_since_last_wake.md"
    meta = APP_ROOT / "vibe12_agent_spec" / "cron_codex" / "state" / "context_since_last_wake.meta.json"
    subprocess.run(
        [
            sys.executable,
            str(WAKE_EXPORT),
            str(epoch),
            str(operator),
            str(notepad),
            str(context),
            str(meta),
        ],
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _run_codex_prompt_job(job_id: str, prompt: str) -> None:
    preview = prompt.strip().split("\n", 1)[0][:120]
    _agent_prompt_path(job_id).write_text(prompt, encoding="utf-8")
    meta: dict[str, Any] = {
        "id": job_id,
        "kind": "codex_prompt",
        "status": "running",
        "started_at": _utc_now(),
        "prompt_preview": preview,
        "prompt_chars": len(prompt),
        "has_prompt_file": True,
    }
    _agent_job_path(job_id).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log_path = _agent_log_path(job_id)

    _export_wake_context()

    try:
        result = run_codex_prompt(prompt, log_path=log_path)
        meta["exit_code"] = result.get("exit_code")
        meta["final_reply"] = result.get("final_reply", "")
        meta["sandbox"] = result.get("sandbox", "")
        if result.get("error"):
            meta["error"] = result.get("error")
        meta["status"] = "ok" if result.get("exit_code") == 0 else "failed"
    except Exception as exc:
        meta["status"] = "failed"
        meta["exit_code"] = -1
        meta["error"] = str(exc)
        meta["final_reply"] = ""
        log_path.write_text(f"exception: {exc}\n", encoding="utf-8")

    meta["finished_at"] = _utc_now()
    _agent_job_path(job_id).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _list_agent_jobs(limit: int = 20) -> list[dict[str, Any]]:
    if not JOBS_DIR.is_dir():
        return []
    jobs: list[dict[str, Any]] = []
    for path in sorted(JOBS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            jobs.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
        if len(jobs) >= limit:
            break
    return jobs


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _unauthorized(handler: BaseHTTPRequestHandler) -> None:
    _json_response(handler, 401, {"error": "missing or invalid X-Commission-Token"})


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "Vibe12CommissionDashboard/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _authorized(self) -> bool:
        if not TOKEN:
            return True
        return self.headers.get("X-Commission-Token", "").strip() == TOKEN

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Commission-Token")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/" or path == "/index.html":
            index = STATIC_DIR / "index.html"
            body = index.read_bytes() if index.is_file() else b"<h1>missing static/index.html</h1>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if not self._authorized():
            return _unauthorized(self)

        if path == "/api/health":
            return _json_response(
                self,
                200,
                {"ok": True, "time": _utc_now(), "gateways_file": str(GATEWAYS_FILE)},
            )

        if path == "/api/info":
            return _json_response(
                self,
                200,
                {
                    "bind": f"{BIND_HOST}:{BIND_PORT}",
                    "lan_urls": _lan_urls(BIND_PORT),
                    "auth": bool(TOKEN),
                },
            )

        if path == "/api/gateways":
            gateways = _load_gateways()
            enriched: list[dict[str, Any]] = []
            for gw in gateways:
                status_code, status_body = _edge_request(gw, "GET", "/api/status")
                enriched.append(
                    {
                        **gw,
                        "edge_reachable": status_code == 200,
                        "edge_status": status_body if status_code == 200 else status_body,
                    }
                )
            return _json_response(self, 200, {"gateways": enriched})

        if path.startswith("/api/gateways/") and path.endswith("/status"):
            gw_id = path.split("/")[3]
            gw = _gateway(gw_id)
            if not gw:
                return _json_response(self, 404, {"error": "gateway not found"})
            code, body = _edge_request(gw, "GET", "/api/status")
            return _json_response(self, code, body)

        if path.startswith("/api/gateways/") and "/jobs/" in path:
            parts = path.split("/")
            gw_id = parts[3]
            job_id = parts[5]
            gw = _gateway(gw_id)
            if not gw:
                return _json_response(self, 404, {"error": "gateway not found"})
            code, body = _edge_request(gw, "GET", f"/api/jobs/{job_id}")
            return _json_response(self, code, body)

        if path.startswith("/api/gateways/") and path.endswith("/discovered.csv"):
            gw_id = path.split("/")[3]
            gw = _gateway(gw_id)
            if not gw:
                return _json_response(self, 404, {"error": "gateway not found"})
            base = gw["edge_url"].rstrip("/")
            req = Request(f"{base}/api/files/points_discovered.csv", method="GET")
            if TOKEN:
                req.add_header("X-Commission-Token", TOKEN)
            try:
                with urlopen(req, timeout=60) as resp:
                    body = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (HTTPError, URLError) as err:
                msg = getattr(err, "reason", str(err))
                return _json_response(self, 502, {"error": str(msg)})
            return

        if path == "/api/agent/jobs":
            jobs = _list_agent_jobs()
            for job in jobs:
                log_path = _agent_log_path(job["id"])
                if log_path.is_file():
                    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                    job["log_tail"] = "\n".join(lines[-40:])
            return _json_response(self, 200, {"jobs": jobs})

        if path.startswith("/api/agent/jobs/") and path.endswith("/prompt"):
            job_id = path.split("/")[3]
            prompt_path = _agent_prompt_path(job_id)
            if not prompt_path.is_file():
                return _json_response(self, 404, {"error": "prompt not found"})
            body = prompt_path.read_text(encoding="utf-8", errors="replace").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path.startswith("/api/agent/jobs/"):
            job_id = path.split("/")[-1]
            meta_path = _agent_job_path(job_id)
            if not meta_path.is_file():
                return _json_response(self, 404, {"error": "job not found"})
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            log_path = _agent_log_path(job_id)
            if log_path.is_file():
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                meta["log_tail"] = "\n".join(lines[-80:])
            if meta.get("kind") == "codex_prompt" and meta.get("final_reply"):
                meta["log_tail"] = (meta.get("final_reply") or "")[-4000:]
            return _json_response(self, 200, meta)

        return _json_response(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._authorized():
            return _unauthorized(self)
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_json()

        if path.startswith("/api/gateways/") and path.endswith("/discover"):
            gw_id = path.split("/")[3]
            gw = _gateway(gw_id)
            if not gw:
                return _json_response(self, 404, {"error": "gateway not found"})
            payload: dict[str, str] = {}
            if body.get("range_low"):
                payload["range_low"] = str(body["range_low"])
            if body.get("range_high"):
                payload["range_high"] = str(body["range_high"])
            code, resp = _edge_request(gw, "POST", "/api/jobs/discover", payload or None)
            return _json_response(self, code, resp)

        if path == "/api/agent/wake":
            mini_count = int(body.get("mini_count", 1))
            job_id = uuid.uuid4().hex[:12]
            JOBS_DIR.mkdir(parents=True, exist_ok=True)
            thread = threading.Thread(target=_run_wake, args=(job_id, mini_count), daemon=True)
            thread.start()
            return _json_response(
                self,
                202,
                {"job_id": job_id, "kind": "codex_wake", "mini_count": mini_count},
            )

        if path == "/api/agent/codex":
            prompt = (body.get("prompt") or "").strip()
            if not prompt:
                return _json_response(self, 400, {"error": "prompt required"})
            job_id = uuid.uuid4().hex[:12]
            JOBS_DIR.mkdir(parents=True, exist_ok=True)
            thread = threading.Thread(target=_run_codex_prompt_job, args=(job_id, prompt), daemon=True)
            thread.start()
            preview = prompt.split("\n", 1)[0][:80]
            return _json_response(
                self,
                202,
                {
                    "job_id": job_id,
                    "kind": "codex_prompt",
                    "prompt_chars": len(prompt),
                    "prompt_preview": preview,
                },
            )

        return _json_response(self, 404, {"error": "not found"})


def main() -> int:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((BIND_HOST, BIND_PORT), DashboardHandler)
    urls = _lan_urls(BIND_PORT)
    print(
        f"vibe12 chat on :{BIND_PORT} (auth={'on' if TOKEN else 'off'})",
        flush=True,
    )
    if TOKEN:
        print(f"  login token: {TOKEN}", flush=True)
    for url in urls:
        print(f"  → {url}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
