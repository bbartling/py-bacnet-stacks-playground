"""Lightweight HTTP agent on the BACnet edge — run discover/read jobs without SSH."""

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
from urllib.parse import urlparse

APP_DIR = Path(os.environ.get("VIBE12_APP_DIR", Path.home() / "vibe_code_apps_12")).resolve()
JOBS_DIR = APP_DIR / "jobs"
ENV_FILE = APP_DIR / "commissioning_agent.env"
TOKEN = os.environ.get("VIBE12_COMMISSION_TOKEN", "").strip()
BIND_HOST = os.environ.get("VIBE12_COMMISSION_BIND", "0.0.0.0")
BIND_PORT = int(os.environ.get("VIBE12_COMMISSION_PORT", "8765"))
PYTHON = APP_DIR / ".venv" / "bin" / "python"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env_file() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV_FILE.is_file():
        return out
    for raw in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def _cfg() -> dict[str, str]:
    merged = _load_env_file()
    for key in (
        "SITE_ID",
        "BUILDING_ID",
        "BACNET_BIND",
        "BACNET_NAME",
        "BACNET_INSTANCE",
        "DISCOVER_LOW",
        "DISCOVER_HIGH",
        "ROUTER_IP",
        "MSTP_NET",
        "BACNET_NETWORK",
        "DISCOVER_TIMEOUT",
    ):
        env_val = os.environ.get(key, "").strip()
        if env_val:
            merged[key] = env_val
    return merged


def _discover_cmd(cfg: dict[str, str], output: Path) -> list[str]:
    py = str(PYTHON if PYTHON.is_file() else sys.executable)
    low = cfg.get("DISCOVER_LOW", "1")
    high = cfg.get("DISCOVER_HIGH", "3456799")
    cmd = [
        py,
        "-m",
        "edge_bacnet.discover",
        str(low),
        str(high),
        "-o",
        str(output),
        "--site-id",
        cfg.get("SITE_ID", "demo"),
        "--building-id",
        cfg.get("BUILDING_ID", "pi"),
        "--name",
        cfg.get("BACNET_NAME", "Gateway"),
        "--instance",
        cfg.get("BACNET_INSTANCE", "3456788"),
        "--address",
        cfg.get("BACNET_BIND", "0.0.0.0/24:47809"),
    ]
    router = cfg.get("ROUTER_IP", "").strip()
    if router:
        cmd.extend(
            [
                "--route-aware",
                "--network",
                cfg.get("BACNET_NETWORK", "1"),
                "--router-ip",
                router,
                "--mstp-net",
                cfg.get("MSTP_NET", "2000"),
                "--timeout",
                cfg.get("DISCOVER_TIMEOUT", "20"),
            ]
        )
    return cmd


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _log_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.log"


def _list_jobs(limit: int = 20) -> list[dict[str, Any]]:
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


def _read_tail(path: Path, max_lines: int = 80) -> str:
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


def _run_job(job_id: str, kind: str, cmd: list[str]) -> None:
    log_file = _log_path(job_id)
    meta = {
        "id": job_id,
        "kind": kind,
        "status": "running",
        "cmd": cmd,
        "started_at": _utc_now(),
        "finished_at": "",
        "exit_code": None,
    }
    _job_path(job_id).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(APP_DIR)
    with log_file.open("w", encoding="utf-8") as log:
        log.write(f"# started {_utc_now()}\n# cmd: {' '.join(cmd)}\n\n")
        log.flush()
        proc = subprocess.run(
            cmd,
            cwd=str(APP_DIR),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    meta["status"] = "ok" if proc.returncode == 0 else "failed"
    meta["finished_at"] = _utc_now()
    meta["exit_code"] = proc.returncode
    _job_path(job_id).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _start_discover(range_low: str | None, range_high: str | None) -> dict[str, Any]:
    cfg = _cfg()
    if range_low:
        cfg["DISCOVER_LOW"] = range_low
    if range_high:
        cfg["DISCOVER_HIGH"] = range_high
    job_id = uuid.uuid4().hex[:12]
    output = APP_DIR / "points_discovered.csv"
    cmd = _discover_cmd(cfg, output)
    thread = threading.Thread(target=_run_job, args=(job_id, "discover", cmd), daemon=True)
    thread.start()
    return {"job_id": job_id, "kind": "discover", "output": str(output)}


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _unauthorized(handler: BaseHTTPRequestHandler) -> None:
    _json_response(handler, 401, {"error": "missing or invalid X-Commission-Token"})


class CommissionAgentHandler(BaseHTTPRequestHandler):
    server_version = "Vibe12CommissionAgent/1.0"

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

    def do_GET(self) -> None:
        if not self._authorized():
            return _unauthorized(self)
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/health":
            return _json_response(
                self,
                200,
                {
                    "ok": True,
                    "app_dir": str(APP_DIR),
                    "time": _utc_now(),
                    "auth": bool(TOKEN),
                },
            )

        if path == "/api/status":
            cfg = _cfg()
            points_discovered = APP_DIR / "points_discovered.csv"
            points = APP_DIR / "points.csv"
            running = [j for j in _list_jobs(50) if j.get("status") == "running"]
            return _json_response(
                self,
                200,
                {
                    "site_id": cfg.get("SITE_ID"),
                    "building_id": cfg.get("BUILDING_ID"),
                    "bacnet_bind": cfg.get("BACNET_BIND"),
                    "discover_range": [
                        cfg.get("DISCOVER_LOW", "1"),
                        cfg.get("DISCOVER_HIGH", "3456799"),
                    ],
                    "files": {
                        "points_discovered": points_discovered.is_file(),
                        "points_discovered_bytes": points_discovered.stat().st_size
                        if points_discovered.is_file()
                        else 0,
                        "points_csv": points.is_file(),
                    },
                    "jobs_running": len(running),
                    "last_jobs": _list_jobs(5),
                },
            )

        if path == "/api/jobs":
            return _json_response(self, 200, {"jobs": _list_jobs(30)})

        if path.startswith("/api/jobs/"):
            job_id = path.split("/")[-1]
            meta_path = _job_path(job_id)
            if not meta_path.is_file():
                return _json_response(self, 404, {"error": "job not found"})
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["log_tail"] = _read_tail(_log_path(job_id))
            return _json_response(self, 200, meta)

        if path == "/api/files/points_discovered.csv":
            target = APP_DIR / "points_discovered.csv"
            if not target.is_file():
                return _json_response(self, 404, {"error": "file missing"})
            body = target.read_text(encoding="utf-8", errors="replace").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/files/points.csv":
            target = APP_DIR / "points.csv"
            if not target.is_file():
                return _json_response(self, 404, {"error": "file missing"})
            body = target.read_text(encoding="utf-8", errors="replace").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        return _json_response(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._authorized():
            return _unauthorized(self)
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_json()

        if path == "/api/jobs/discover":
            started = _start_discover(body.get("range_low"), body.get("range_high"))
            return _json_response(self, 202, started)

        return _json_response(self, 404, {"error": "not found"})


def main() -> int:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((BIND_HOST, BIND_PORT), CommissionAgentHandler)
    print(
        f"Vibe12 edge commissioning agent on http://{BIND_HOST}:{BIND_PORT} "
        f"(app_dir={APP_DIR}, auth={'on' if TOKEN else 'off'})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
