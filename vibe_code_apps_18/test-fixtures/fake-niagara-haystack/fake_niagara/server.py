"""HTTP server implementing the Haystack operations needed for FDD testing."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .auth import AuthManager
from .data import FakeBASData, HistoryLimitError
from .zinc import Column, Grid, Marker, Ref, decode_grid, encode_grid


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    base_path: str = "/api"
    username: str = "admin"
    password: str = "demo"
    quiet: bool = False
    max_history_days: int = 31
    max_history_samples: int = 10000
    max_batch_points: int = 32


class _Handler(BaseHTTPRequestHandler):
    server_version = "FakeNiagaraHaystack/1.0"
    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(15)

    @property
    def app(self) -> "FakeHaystackServer":
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        if not self.app.config.quiet:
            super().log_message(fmt, *args)

    def _send(self, status: int, body: str = "", headers: dict[str, str] | None = None) -> None:
        raw = body.encode("utf-8")
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def _api_path(self) -> str:
        path = urlparse(self.path).path.rstrip("/")
        prefix = self.app.config.base_path.rstrip("/")
        return path[len(prefix):].lstrip("/") if path.startswith(prefix) else ""

    def _bearer_user(self) -> str | None:
        return self.app.auth.authenticate_header(self.headers.get("Authorization"))

    def _require_bearer(self) -> str | None:
        user = self._bearer_user()
        if not user:
            self._send(401, headers={"WWW-Authenticate": "HELLO"})
        return user

    def do_GET(self) -> None:  # noqa: N802
        op = self._api_path()
        if op == "about":
            self._get_about()
            return
        if not self._require_bearer():
            return
        if op == "ops":
            self._respond(Grid({}, ["name"], [{"name": name} for name in self.app.operations]))
        elif op == "formats":
            self._respond(Grid({}, ["mime", "dis"], [{"mime": "text/zinc", "dis": "Zinc"}]))
        elif op == "libs":
            self._respond(Grid({}, ["name", "version"], [{"name": "fake-niagara", "version": "1.0"}]))
        else:
            self._send(404, encode_grid(self._error(f"unknown operation: {op}")), {"Content-Type": "text/zinc"})

    def _get_about(self) -> None:
        authorization = self.headers.get("Authorization", "")
        scheme, params = self.app.auth._params(authorization)
        if scheme == "HELLO":
            status, headers = self.app.auth.hello(params.get("username", ""), params.get("data"))
            self._send(status, headers=headers)
            return
        if scheme == "SCRAM":
            status, headers = self.app.auth.scram(params.get("handshakeToken", ""), params.get("data", ""))
            self._send(status, headers=headers)
            return
        if not self._require_bearer():
            return
        boot = self.app.boot_time
        now = dt.datetime.now(dt.timezone.utc)
        self._respond(Grid({}, ["haystackVersion", "tz", "serverName", "serverTime", "serverBootTime", "productName"], [{
            "haystackVersion": "3.0", "tz": self.app.data.timezone, "serverName": "Fake Niagara 4", "serverTime": now,
            "serverBootTime": boot, "productName": "Fake Niagara 4",
        }]))

    def do_POST(self) -> None:  # noqa: N802
        op = self._api_path()
        user = self._require_bearer()
        if not user:
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 2_000_000:
                raise ValueError("request too large")
            body = self.rfile.read(length).decode("utf-8")
            grid = self._decode_body(body)
            result = self._operation(op, grid)
            if op == "close":
                self._respond(result)
            else:
                self._respond(result)
        except Exception as exc:  # keep malformed test requests inside the protocol
            self._respond(self._error(str(exc)), status=400)

    def _decode_body(self, body: str) -> Grid:
        ctype = (self.headers.get("Content-Type") or "text/zinc").split(";", 1)[0].strip()
        if ctype in ("text/zinc", "application/zinc", "text/plain"):
            return decode_grid(body)
        raise ValueError(f"unsupported content type {ctype}")

    def _operation(self, op: str, grid: Grid) -> Grid:
        data = self.app.data
        if op == "read":
            filter_text = None
            limit = None
            ids: list[str] | None = None
            if grid.rows:
                if all(row.get("id") is not None for row in grid.rows):
                    ids = [_string(row.get("id")) for row in grid.rows]
                else:
                    row = grid.rows[0]
                    filter_text = _string(row.get("filter"))
                    limit = _integer(row.get("limit"))
                    raw_ids = row.get("ids")
                    if isinstance(raw_ids, str):
                        ids = [raw_ids]
            elif grid.meta:
                filter_text = _string(grid.meta.get("filter"))
            if ids is not None:
                return self._entity_grid(data.read_by_ids(ids))
            return self._entity_grid(data.read(filter_text, limit))
        if op in ("readByIds", "readByID"):
            ids = [_string(row.get("id")) for row in grid.rows if row.get("id") is not None]
            return self._entity_grid(data.read_by_ids(ids))
        if op == "hisRead":
            if not grid.rows:
                return self._error("hisRead requires id and range")
            if "range" in grid.meta:
                if len(grid.rows) > self.app.config.max_batch_points:
                    return self._error(f"hisRead batch exceeds maximum of {self.app.config.max_batch_points} points")
                try:
                    data.validate_range(_string(grid.meta.get("range")), _string(grid.meta.get("tz")) or None, self.app.config.max_history_days, self.app.config.max_history_samples)
                except (HistoryLimitError, ValueError) as exc:
                    return self._error(str(exc))
                return self._batch_his_read(grid)
            if len(grid.rows) == 1:
                row = grid.rows[0]
                try:
                    data.validate_range(_string(row.get("range")), _string(grid.meta.get("tz")) or None, self.app.config.max_history_days, self.app.config.max_history_samples)
                    items, start, end = data.history(_string(row.get("id")), _string(row.get("range")), _string(grid.meta.get("tz")) or None)
                except (HistoryLimitError, ValueError) as exc:
                    return self._error(str(exc))
                return Grid({"id": Ref(_string(row.get("id")).lstrip("@")), "hisStart": start, "hisEnd": end}, ["ts", "val"], items)
            request_range = _string(grid.rows[0].get("range"))
            if len(grid.rows) > self.app.config.max_batch_points:
                return self._error(f"hisRead batch exceeds maximum of {self.app.config.max_batch_points} points")
            try:
                data.validate_range(request_range, None, self.app.config.max_history_days, self.app.config.max_history_samples)
            except (HistoryLimitError, ValueError) as exc:
                return self._error(str(exc))
            batch = Grid({"range": request_range}, ["id"], [{"id": row.get("id")} for row in grid.rows])
            return self._batch_his_read(batch)
        if op == "close":
            token = self.app.auth._params(self.headers.get("Authorization", ""))[1].get("authToken")
            self.app.auth.close(token)
            return Grid({}, [], [])
        if op == "pointWrite":
            return self._error("pointWrite is intentionally read-only in the demo")
        if op in ("hisWrite", "watchSub", "watchPoll", "watchUnsub", "nav", "defs", "specs", "spec"):
            return self._error(f"{op} is not implemented by fake-niagara")
        return self._error(f"unknown operation: {op}")

    @staticmethod
    def _error(message: str) -> Grid:
        return Grid({"err": Marker(), "dis": message}, [], [])

    def _respond(self, grid: Grid, status: int = 200) -> None:
        self._send(status, encode_grid(grid), {"Content-Type": "text/zinc; charset=utf-8"})

    def _entity_grid(self, results: list[dict[str, Any] | None]) -> Grid:
        cols: list[str] = []
        for row in results:
            if row:
                for key in row:
                    if key not in cols:
                        cols.append(key)
        if not cols:
            for row in self.app.data.entities:
                for key in row:
                    if key not in cols:
                        cols.append(key)
        return Grid({}, cols, [row or {} for row in results])

    def _batch_his_read(self, grid: Grid) -> Grid:
        request_range = _string(grid.meta.get("range"))
        timezone = _string(grid.meta.get("tz")) or None
        series: list[tuple[str, list[dict[str, Any]], Any, Any]] = []
        for row in grid.rows:
            point_id = _string(row.get("id"))
            range_value = request_range or _string(row.get("range"))
            items, start, end = self.app.data.history(point_id, range_value, timezone)
            series.append((point_id, items, start, end))
        # ZoneInfo datetimes in the fall-back hour compare equal by wall-clock
        # value when they share a tzinfo object. Join on UTC instants instead
        # so the repeated hour remains two distinct samples.
        timestamps = sorted({item["ts"].astimezone(dt.timezone.utc) for _, items, _, _ in series for item in items})
        cols: list[str | Column] = ["ts"]
        for index, (point_id, _, _, _) in enumerate(series):
            cols.append(Column(f"v{index}", {"id": Ref(point_id.lstrip("@"))}))
        by_series = [{item["ts"].astimezone(dt.timezone.utc): item for item in items} for _, items, _, _ in series]
        rows = [{"ts": (by_series[0][timestamp]["ts"] if by_series and timestamp in by_series[0] else timestamp), **{f"v{index}": lookup.get(timestamp, {}).get("val") for index, lookup in enumerate(by_series)}} for timestamp in timestamps]
        starts = [start for _, _, start, _ in series]
        ends = [end for _, _, _, end in series]
        meta = {"hisStart": min(starts) if starts else None, "hisEnd": max(ends) if ends else None}
        return Grid(meta, cols, rows)


def _string(value: Any) -> str:
    if isinstance(value, Ref):
        return "@" + value.value
    return "" if value is None else str(value)


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class FakeHaystackServer:
    operations = ("about", "ops", "formats", "libs", "read", "readByIds", "hisRead", "close")

    def __init__(self, config: ServerConfig | None = None, data: FakeBASData | None = None) -> None:
        self.config = config or ServerConfig()
        self.data = data or FakeBASData()
        self.auth = AuthManager({self.config.username: self.config.password})
        self.httpd = ThreadingHTTPServer((self.config.host, self.config.port), _Handler)
        self.httpd.daemon_threads = True
        self.httpd.block_on_close = False
        self.httpd.app = self  # type: ignore[attr-defined]
        self.thread: threading.Thread | None = None
        self.boot_time = dt.datetime.now(dt.timezone.utc)

    @property
    def address(self) -> tuple[str, int]:
        return self.httpd.server_address[:2]

    def serve_forever(self) -> None:
        self.httpd.serve_forever()

    def start(self) -> None:
        self.thread = threading.Thread(target=self.serve_forever, name="fake-niagara", daemon=True)
        self.thread.start()

    def shutdown(self) -> None:
        if self.thread and self.thread.is_alive():
            self.httpd.shutdown()
        self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a fake Niagara/Haystack BAS server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--username", default=os.environ.get("FAKE_NIAGARA_USERNAME", "admin"))
    parser.add_argument("--password", default=os.environ.get("FAKE_NIAGARA_PASSWORD", "demo"), help="avoid putting this on a process list; prefer FAKE_NIAGARA_PASSWORD")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    server = FakeHaystackServer(ServerConfig(args.host, args.port, "/api", args.username, args.password, args.quiet))
    print(f"Fake Niagara Haystack server listening at http://{args.host}:{args.port}/api")
    print(f"Credentials: username={args.username}; set the password through FAKE_NIAGARA_PASSWORD or deployment configuration")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
