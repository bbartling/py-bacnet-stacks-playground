"""Batch motor runtime stats — avoids per-equipment load_history_wide loops."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import pandas as pd

from analytics_motors import compute_motor_runtime, discover_motors
from shared.data_config import get_config
from shared.occupancy import DEFAULT_SCHEDULE, is_occupied as occ_fn

_HERE = Path(__file__).resolve().parent
_CACHE_DIR = _HERE / ".cache" / "motors"
_LOCK = threading.Lock()


def _data_token() -> str:
    import cookbook_engine as ce
    return ce._data_token()


def _cache_path(token: str) -> Path:
    digest = hashlib.sha256(token.encode()).hexdigest()[:16]
    return _CACHE_DIR / f"{digest}.json"


def _load_cached(token: str) -> list[dict] | None:
    path = _cache_path(token)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("data_token") == token:
            return payload.get("motors")
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _save_cached(token: str, motors: list[dict]) -> None:
    path = _cache_path(token)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"data_token": token, "motors": motors}, default=str), encoding="utf-8")
    except OSError:
        pass


def _poll_seconds(df: pd.DataFrame, default: float = 300.0) -> float:
    if hasattr(df, "attrs") and "effective_poll_seconds" in df.attrs:
        return float(df.attrs["effective_poll_seconds"])
    return default


def compute_all_motor_stats(
    raw: dict,
    *,
    resolver=None,
    poll_seconds: float | None = None,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """Compute motor runtime for every discovered motor using already-loaded raw frames.

    Falls back to load_history_wide only when the equipment is not in ``raw``.
    Results are disk-cached keyed by data_token.
    """
    token = _data_token()
    if use_cache:
        with _LOCK:
            hit = _load_cached(token)
        if hit is not None:
            return hit

    if resolver is None:
        from haystack_rdf.resolver import get_resolver
        resolver = get_resolver()

    from haystack_rdf.data_loader import load_history_wide

    motor_rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for spec in discover_motors(resolver):
        key = (spec.equipment_id, spec.point_role)
        if key in seen:
            continue
        seen.add(key)

        df = None
        ahu_raw = raw.get("ahu_raw") or {}
        if spec.equipment_id in ahu_raw:
            df = ahu_raw[spec.equipment_id]
        elif spec.equipment_id == "AHU_1" and raw.get("ahu1_raw") is not None:
            df = raw["ahu1_raw"]
        elif spec.equipment_id == "AHU_2" and raw.get("ahu2_raw") is not None:
            df = raw["ahu2_raw"]
        elif spec.equipment_id == "CHILLER_1" and raw.get("ch1") is not None:
            df = raw["ch1"]
        elif spec.equipment_id == "CHILLER_2" and raw.get("ch2") is not None:
            df = raw["ch2"]
        elif "BOILER" in spec.equipment_id.upper() and raw.get("blr") is not None:
            df = raw["blr"]

        if df is None:
            try:
                df = load_history_wide(spec.equipment_id, resolver)
            except Exception:
                continue

        col = spec.column
        if not col or col not in df.columns:
            col = resolver.column_for_role(spec.equipment_id, spec.point_role)
        if not col or col not in df.columns:
            continue

        ts_col = "timestamp_utc" if "timestamp_utc" in df.columns else "timestamp"
        if ts_col not in df.columns:
            continue
        ts = df[ts_col]
        occ = occ_fn(ts, DEFAULT_SCHEDULE, get_config().site_timezone())
        poll = poll_seconds if poll_seconds is not None else _poll_seconds(df)
        stats = compute_motor_runtime(df, col, role=spec.point_role, occupied=occ, poll_seconds=poll)
        motor_rows.append({
            "equipment_id": spec.equipment_id,
            "label": spec.label,
            "point_role": spec.point_role,
            **stats,
        })

    with _LOCK:
        _save_cached(token, motor_rows)
    return motor_rows


def clear_motor_cache() -> None:
    with _LOCK:
        if _CACHE_DIR.is_dir():
            import shutil
            shutil.rmtree(_CACHE_DIR, ignore_errors=True)
