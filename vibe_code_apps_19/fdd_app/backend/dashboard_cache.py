"""In-memory cache for CSV raw frames and computed dashboard context."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Callable

# params_key -> full context dict
_full_context: dict[str, dict[str, Any]] = {}
# params_key -> page_id -> context dict (partial or full)
_page_context: dict[str, dict[str, dict[str, Any]]] = {}
# (params_key, page_id) -> rendered HTML body
_body_cache: dict[tuple[str, str], str] = {}
# (mtime_token, raw dict)
_raw_entry: tuple[str, dict[str, Any]] | None = None
_econ_diag_key: str | None = None
_lock = threading.Lock()
_raw_load_lock = threading.Lock()
# In-flight compute: waiters share one result instead of duplicating work
_inflight: dict[tuple[str, str], threading.Event] = {}
_inflight_ctx: dict[tuple[str, str], dict[str, Any]] = {}


def params_key(params: dict[str, Any]) -> str:
    payload = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def _cache_key(params: dict[str, Any], page_id: str | None) -> tuple[str, str]:
    return params_key(params), page_id or "__full__"


def _mtime_token(paths: list) -> str:
    parts: list[str] = []
    for path in paths:
        try:
            parts.append(f"{path}:{path.stat().st_mtime_ns}")
        except OSError:
            parts.append(f"{path}:missing")
    return "|".join(parts)


def clear_all() -> None:
    global _raw_entry, _econ_diag_key
    with _lock:
        _full_context.clear()
        _page_context.clear()
        _body_cache.clear()
        _inflight.clear()
        _inflight_ctx.clear()
        _raw_entry = None
        _econ_diag_key = None


def get_raw_data(loader: Callable[[], dict[str, Any]], source_paths: list) -> dict[str, Any]:
    """Load CSV tree once; invalidate when any source file mtime changes."""
    global _raw_entry
    token = _mtime_token(source_paths)
    with _lock:
        if _raw_entry is not None and _raw_entry[0] == token:
            return _raw_entry[1]
    with _raw_load_lock:
        with _lock:
            if _raw_entry is not None and _raw_entry[0] == token:
                return _raw_entry[1]
        t0 = time.perf_counter()
        raw = loader()
        elapsed = time.perf_counter() - t0
        pending: list[threading.Event] = []
        with _lock:
            if _raw_entry is None or _raw_entry[0] != token:
                _full_context.clear()
                _page_context.clear()
                _body_cache.clear()
                pending = list(_inflight.values())
                _inflight.clear()
                _inflight_ctx.clear()
                _econ_diag_key = None
            _raw_entry = (token, raw)
        for ev in pending:
            ev.set()
        print(f"[dashboard] CSV load {elapsed:.2f}s ({len(raw.get('ahu1_raw', []))} AHU rows)")
        return raw


def _store_context(pk: str, pid: str, ctx: dict[str, Any]) -> None:
    if pid == "__full__":
        _full_context[pk] = ctx
        _page_context.setdefault(pk, {})["__full__"] = ctx
    else:
        _page_context.setdefault(pk, {})[pid] = ctx


def get_context(
    compute_fn: Callable[..., dict[str, Any]],
    raw: dict[str, Any],
    params: dict[str, Any],
    page_id: str | None = None,
) -> dict[str, Any]:
    """Return cached context; compute once per (params, page) combination."""
    pk, pid = _cache_key(params, page_id)
    key = (pk, pid)

    with _lock:
        if pk in _full_context:
            return _full_context[pk]
        bucket = _page_context.get(pk)
        if bucket and pid in bucket:
            return bucket[pid]
        if key in _inflight:
            wait_event = _inflight[key]
            leader = False
        else:
            wait_event = threading.Event()
            _inflight[key] = wait_event
            leader = True

    if not leader:
        if not wait_event.wait(timeout=600):
            raise TimeoutError(f"Timed out waiting for dashboard compute {page_id or 'full'}")
        with _lock:
            if pk in _full_context:
                return _full_context[pk]
            bucket = _page_context.get(pk)
            if bucket and pid in bucket:
                return bucket[pid]
            cached = _inflight_ctx.get(key)
            if cached is not None:
                return cached
        # Cache was cleared while waiting — recompute.
        return get_context(compute_fn, raw, params, page_id=page_id)

    t0 = time.perf_counter()
    try:
        ctx = compute_fn(raw, page_id=page_id)
    except Exception:
        with _lock:
            _inflight.pop(key, None)
            _inflight_ctx.pop(key, None)
        wait_event.set()
        raise

    elapsed = time.perf_counter() - t0
    label = page_id or "full"
    print(f"[dashboard] compute {label} {elapsed:.2f}s (cache miss)")

    with _lock:
        _store_context(pk, pid, ctx)
        _inflight_ctx[key] = ctx
        _inflight.pop(key, None)
    wait_event.set()
    return ctx


def get_body(
    render_fn: Callable[[str, dict[str, Any]], str],
    ctx: dict[str, Any],
    params: dict[str, Any],
    page_id: str,
    variant: str = "",
) -> str:
    """Cache rendered page HTML per (params, page, variant).

    ``variant`` captures render-only options that change the HTML but not the
    computed context — e.g. display units and chart theme (light/dark). Without it,
    a light-mode refresh would return the cached dark-mode charts.
    """
    pk, pid = _cache_key(params, page_id)
    key = (pk, f"{pid}::{variant}" if variant else pid)
    with _lock:
        cached = _body_cache.get(key)
        if cached is not None:
            return cached

    t0 = time.perf_counter()
    body = render_fn(page_id, ctx)
    elapsed = time.perf_counter() - t0
    if elapsed > 0.5:
        print(f"[dashboard] render {page_id} {elapsed:.2f}s")

    with _lock:
        _body_cache[key] = body
    return body


def should_rebuild_economizer_diagnostics(params: dict[str, Any]) -> bool:
    global _econ_diag_key
    pk = params_key(params)
    with _lock:
        if _econ_diag_key == pk:
            return False
        _econ_diag_key = pk
        return True


def prewarm(
    compute_fn: Callable[..., dict[str, Any]],
    raw: dict[str, Any],
    params: dict[str, Any],
    page_ids: list[str] | None = None,
) -> None:
    """Background pre-compute for faster first navigation."""
    ids = page_ids or ["index", "ahu_1", "ahu_2", "economizer", "central_plant"]
    for page_id in ids:
        try:
            get_context(compute_fn, raw, params, page_id=page_id)
        except Exception as exc:
            print(f"[dashboard] prewarm {page_id} failed: {exc}")
