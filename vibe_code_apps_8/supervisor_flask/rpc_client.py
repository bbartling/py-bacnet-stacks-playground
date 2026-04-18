"""JSON-RPC client for diy-bacnet-server (one POST per method).

See: https://github.com/bbartling/diy-bacnet-server/blob/master/docs/json-rpc.md
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import requests

DEFAULT_BASE = os.environ.get("DIY_BACNET_URL", "http://127.0.0.1:5000").rstrip("/")
API_KEY = os.environ.get("BACNET_RPC_API_KEY", "").strip()


def call_method(method: str, params: dict[str, Any] | None = None, *, base_url: str | None = None) -> dict[str, Any]:
    """POST JSON-RPC envelope to ``{base}/{method}``."""
    base = (base_url or DEFAULT_BASE).rstrip("/")
    url = f"{base}/{method}"
    body: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params if params is not None else {},
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    r = requests.post(url, json=body, headers=headers, timeout=float(os.environ.get("DIY_RPC_TIMEOUT", "15")))
    r.raise_for_status()
    out = r.json()
    if isinstance(out, dict) and out.get("error"):
        raise RuntimeError(str(out["error"]))
    return out if isinstance(out, dict) else {"result": out}


def server_hello(base_url: str | None = None) -> dict[str, Any]:
    return call_method("server_hello", {}, base_url=base_url)


def server_read_schedule(name: str, base_url: str | None = None) -> dict[str, Any]:
    return call_method("server_read_schedule", {"request": {"name": name}}, base_url=base_url)


def server_update_schedule(
    update: dict[str, Any],
    *,
    base_url: str | None = None,
) -> dict[str, Any]:
    return call_method("server_update_schedule", {"update": update}, base_url=base_url)


def server_read_all_values(base_url: str | None = None) -> dict[str, Any]:
    return call_method("server_read_all_values", {}, base_url=base_url)
