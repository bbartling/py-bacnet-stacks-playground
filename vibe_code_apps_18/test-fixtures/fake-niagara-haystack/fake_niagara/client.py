"""Small stdlib Haystack client and SQLite history backfill utility."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import hmac
import os
import sqlite3
import secrets
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .zinc import Grid, Quantity, Ref, decode_grid, encode_grid


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _decode(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"), validate=True)


def _decode_outer(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.b64decode(padded.encode("ascii"), validate=True)
    except (ValueError, base64.binascii.Error):
        return base64.urlsafe_b64decode(padded.encode("ascii"))


def _hmac(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


@dataclass
class HaystackClient:
    base_url: str
    username: str
    password: str
    timeout: float = 10.0
    token: str | None = None

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    def authenticate(self) -> str:
        nonce = _b64(secrets.token_bytes(18))
        first_bare = f"n={self.username.replace('=', '=3D').replace(',', '=2C')},r={nonce}"
        first = _b64(f"n,,{first_bare}".encode())
        username_b64 = _b64(self.username.encode())
        req = urllib.request.Request(self.base_url + "/about", headers={"Authorization": f"HELLO username={username_b64}, data={first}"})
        try:
            urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            if exc.code != 401:
                raise RuntimeError(f"HELLO failed: HTTP {exc.code}") from exc
            challenge = exc.headers.get("WWW-Authenticate", "")
        else:
            raise RuntimeError("HELLO unexpectedly succeeded")
        scheme, params = _parse_header(challenge)
        if scheme != "SCRAM" or "data" not in params or "handshakeToken" not in params:
            raise RuntimeError(f"server did not offer SCRAM: {challenge}")
        server_first = _decode_outer(params["data"]).decode()
        fields = dict(part.split("=", 1) for part in server_first.split(","))
        combined, salt, iterations = fields["r"], _decode(fields["s"]), int(fields["i"])
        if not combined.startswith(nonce):
            raise RuntimeError("server nonce does not include client nonce")
        salted = hashlib.pbkdf2_hmac("sha256", self.password.encode(), salt, iterations)
        client_key = _hmac(salted, b"Client Key")
        stored_key = hashlib.sha256(client_key).digest()
        server_key = _hmac(salted, b"Server Key")
        final_no_proof = f"c=biws,r={combined}"
        auth_message = f"{first_bare},{server_first},{final_no_proof}"
        signature = _hmac(stored_key, auth_message.encode())
        proof = bytes(a ^ b for a, b in zip(client_key, signature))
        final = _b64(f"{final_no_proof},p={_b64(proof)}".encode())
        req = urllib.request.Request(self.base_url + "/about", headers={"Authorization": f"SCRAM handshakeToken={params['handshakeToken']}, data={final}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                info = response.headers.get("Authentication-Info", "")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"SCRAM failed: HTTP {exc.code}") from exc
        _, info_params = _parse_header("AUTH " + info)
        token = info_params.get("authToken")
        server_final = info_params.get("data")
        if not token or not server_final:
            raise RuntimeError("SCRAM response missing authToken/data")
        server_final_msg = _decode(server_final).decode()
        if not hmac.compare_digest(server_final_msg, "v=" + _b64(_hmac(server_key, auth_message.encode()))):
            raise RuntimeError("server SCRAM signature mismatch")
        self.token = token
        return token

    def _request(self, op: str, grid: Grid | None = None, *, method: str | None = None) -> Grid:
        if not self.token:
            self.authenticate()
        method = method or ("GET" if op in {"about", "ops", "formats", "libs"} else "POST")
        headers = {"Authorization": f"BEARER authToken={self.token}", "Accept": "text/zinc"}
        data = None
        if method == "POST":
            headers["Content-Type"] = "text/zinc"
            data = encode_grid(grid or Grid({}, [], [])).encode()
        req = urllib.request.Request(f"{self.base_url}/{op}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = decode_grid(response.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise RuntimeError(f"Haystack {op} failed: HTTP {exc.code} {body[:200]}") from exc
        if "err" in result.meta:
            raise RuntimeError(str(result.meta.get("dis", "Haystack error")))
        return result

    def about(self) -> Grid:
        return self._request("about", method="GET")

    def ops(self) -> Grid:
        return self._request("ops", method="GET")

    def formats(self) -> Grid:
        return self._request("formats", method="GET")

    def read(self, filter_text: str, limit: int | None = None) -> Grid:
        row: dict[str, Any] = {"filter": filter_text}
        if limit is not None:
            row["limit"] = limit
        return self._request("read", Grid({}, list(row), [row]))

    def read_by_ids(self, ids: list[str]) -> Grid:
        rows = [{"id": Ref(item.lstrip("@"))} for item in ids]
        return self._request("read", Grid({}, ["id"], rows))

    def his_read(self, point_id: str, range_text: str) -> Grid:
        return self._request("hisRead", Grid({}, ["id", "range"], [{"id": Ref(point_id.lstrip("@")), "range": range_text}]))

    def his_read_batch(self, requests: list[tuple[str, str]]) -> Grid:
        if not requests:
            return Grid({}, ["ts"], [])
        ranges = {rng for _, rng in requests}
        if len(ranges) != 1:
            raise ValueError("standard Haystack batch hisRead requires one shared range")
        rows = [{"id": Ref(pid.lstrip("@"))} for pid, _ in requests]
        return self._request("hisRead", Grid({"range": next(iter(ranges))}, ["id"], rows))

    def close(self) -> None:
        if self.token:
            try:
                self._request("close", Grid({}, [], []))
            finally:
                self.token = None


def _parse_header(header: str) -> tuple[str, dict[str, str]]:
    bits = header.strip().split(None, 1)
    scheme = bits[0].upper() if bits else ""
    params: dict[str, str] = {}
    for part in bits[1].split(",") if len(bits) > 1 else []:
        if "=" in part:
            key, val = part.strip().split("=", 1)
            params[key] = val.strip()
    return scheme, params


def ensure_schema(connection: sqlite3.Connection) -> None:
    existing = {row[1] for row in connection.execute("PRAGMA table_info(haystack_history)")}
    if existing and "value_type" not in existing:
        connection.execute("ALTER TABLE haystack_history RENAME TO haystack_history_legacy")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS haystack_history (
            point_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            value REAL,
            value_num REAL,
            value_text TEXT,
            value_type TEXT NOT NULL,
            unit TEXT,
            source TEXT NOT NULL,
            PRIMARY KEY (point_id, ts, source)
        )
    """)
    if existing and "value_type" not in existing:
        connection.execute("""
            INSERT OR IGNORE INTO haystack_history(point_id, ts, value, value_num, value_text, value_type, unit, source)
            SELECT point_id, ts, value, value, NULL, 'number', NULL, source
            FROM haystack_history_legacy
        """)
        connection.execute("DROP TABLE haystack_history_legacy")
    connection.commit()


def backfill_yesterday(client: HaystackClient, database: str | Path, *, date: dt.date | None = None) -> int:
    day = date or (dt.datetime.now(ZoneInfo("America/Chicago")).date() - dt.timedelta(days=1))
    range_text = day.isoformat()
    points = client.read("point and his")
    conn = sqlite3.connect(str(database))
    try:
        ensure_schema(conn)
        inserted = 0
        for entity in points.rows:
            pid = entity.get("id")
            if not isinstance(pid, Ref):
                continue
            history = client.his_read(pid.value, range_text)
            for item in history.rows:
                ts = item.get("ts")
                if hasattr(ts, "astimezone"):
                    ts_text = ts.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
                elif hasattr(ts, "isoformat"):
                    ts_text = ts.isoformat()
                else:
                    ts_text = str(ts)
                raw = item.get("val")
                if isinstance(raw, Quantity):
                    value_num, value_text, value_type, unit, legacy_value = raw.value, None, "number", raw.unit, raw.value
                elif isinstance(raw, bool):
                    value_num, value_text, value_type, unit, legacy_value = None, str(raw).lower(), "bool", None, None
                elif isinstance(raw, (int, float)):
                    value_num, value_text, value_type, unit, legacy_value = float(raw), None, "number", None, float(raw)
                elif raw is None:
                    value_num, value_text, value_type, unit, legacy_value = None, None, "null", None, None
                else:
                    value_num, value_text, value_type, unit, legacy_value = None, str(raw), "str", None, None
                existing = conn.execute("SELECT value, value_num, value_text, value_type, unit FROM haystack_history WHERE point_id=? AND ts=? AND source=?", (pid.value, ts_text, client.base_url)).fetchone()
                values = (legacy_value, value_num, value_text, value_type, unit)
                conn.execute("""
                    INSERT INTO haystack_history(point_id, ts, value, value_num, value_text, value_type, unit, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(point_id, ts, source) DO UPDATE SET
                      value=excluded.value, value_num=excluded.value_num,
                      value_text=excluded.value_text, value_type=excluded.value_type,
                      unit=excluded.unit
                """, (pid.value, ts_text, *values, client.base_url))
                if existing is None or tuple(existing) != values:
                    inserted += 1
        conn.commit()
        return inserted
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Query fake Niagara Haystack or backfill history to SQLite")
    parser.add_argument("--url", default="http://127.0.0.1:8080/api")
    parser.add_argument("--username", default=os.environ.get("FAKE_NIAGARA_USERNAME", "admin"))
    parser.add_argument("--password", default=os.environ.get("FAKE_NIAGARA_PASSWORD", "demo"), help="prefer FAKE_NIAGARA_PASSWORD so it is not in shell history")
    parser.add_argument("--database", default="history.sqlite3")
    parser.add_argument("--date", help="UTC date to backfill (default: yesterday)")
    parser.add_argument("--point", help="Read one point instead of running backfill")
    parser.add_argument("--range", dest="range_text", default="yesterday")
    parser.add_argument("--discover", action="store_true")
    args = parser.parse_args()
    client = HaystackClient(args.url, args.username, args.password)
    try:
        if args.discover:
            for row in client.read("point and his").rows:
                print(row)
        elif args.point:
            result = client.his_read(args.point, args.range_text)
            print(encode_grid(result), end="")
        else:
            selected = dt.date.fromisoformat(args.date) if args.date else None
            print(f"inserted={backfill_yesterday(client, args.database, date=selected)}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
