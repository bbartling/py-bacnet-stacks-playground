"""Disk-backed cache for cookbook fault results — survives server restarts.

Stores JSON payloads keyed by (data_token, cache_key). Invalidated when the RDF
model or historian Feather mtimes change (via data_token from cookbook_engine).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_CACHE_DIR = _HERE / ".cache" / "faults"
_LOCK = threading.Lock()
_RULE_SET_VERSION = "1"  # bump when cookbook rule catalog changes materially


def rule_set_version() -> str:
    return _RULE_SET_VERSION


def _path(data_token: str, cache_key: str) -> Path:
    safe = cache_key.replace("/", "_").replace("|", "_").replace("\\", "_")[:64]
    return _CACHE_DIR / data_token[:32] / f"{safe}.json"


def get(data_token: str, cache_key: str) -> dict[str, Any] | None:
    path = _path(data_token, cache_key)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("rule_set_version") != _RULE_SET_VERSION:
            return None
        if payload.get("data_token") != data_token:
            return None
        return payload.get("data")
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def put(data_token: str, cache_key: str, data: dict[str, Any]) -> None:
    path = _path(data_token, cache_key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "data_token": data_token,
                "cache_key": cache_key,
                "rule_set_version": _RULE_SET_VERSION,
                "data": data,
            }, default=str),
            encoding="utf-8",
        )
    except OSError:
        pass


def clear() -> None:
    with _LOCK:
        if _CACHE_DIR.is_dir():
            import shutil
            shutil.rmtree(_CACHE_DIR, ignore_errors=True)
