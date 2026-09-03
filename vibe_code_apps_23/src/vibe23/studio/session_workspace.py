"""Per-browser session workspace for the Vibe 23 Streamlit studio.

Streamlit Community Cloud keeps each visitor's optional disk artifacts under
``{temp}/vibe23/{session_id}/``. Dataset frames and uploads live in
``st.session_state``; this module isolates any on-disk exports so one browser
cannot wipe another visitor's folder.

This is isolation on a shared process — not a cryptographic security boundary.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
import uuid
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

SESSION_PARENT_NAME = "vibe23"
HEARTBEAT_NAME = ".vibe23_session_heartbeat"
UPLOADS_DIRNAME = "uploads"
EXPORTS_DIRNAME = "exports"
SESSION_ID_KEY = "session_id"
_SAFE_SESSION_ID = re.compile(r"^[0-9a-f]{32}$")
DEFAULT_MAX_AGE_SEC = 6 * 3600


def ensure_session_id(session_state: MutableMapping[str, Any]) -> str:
    existing = session_state.get(SESSION_ID_KEY)
    if isinstance(existing, str) and _SAFE_SESSION_ID.match(existing):
        return existing
    sid = uuid.uuid4().hex
    session_state[SESSION_ID_KEY] = sid
    return sid


def workspace_parent(*, temp_dir: Path | str | None = None) -> Path:
    root = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
    return root / SESSION_PARENT_NAME


def _require_session_id(session_id: str) -> str:
    sid = str(session_id or "").strip().lower()
    if not _SAFE_SESSION_ID.match(sid):
        raise ValueError("session_id must be a 32-char hex uuid")
    return sid


def session_root(
    session_id: str,
    *,
    temp_dir: Path | str | None = None,
    create: bool = True,
) -> Path:
    sid = _require_session_id(session_id)
    root = workspace_parent(temp_dir=temp_dir) / sid
    if create:
        root.mkdir(parents=True, exist_ok=True)
        (root / UPLOADS_DIRNAME).mkdir(exist_ok=True)
        (root / EXPORTS_DIRNAME).mkdir(exist_ok=True)
        touch_heartbeat(root)
    return root


def uploads_dir(session_id: str, *, temp_dir: Path | str | None = None) -> Path:
    d = session_root(session_id, temp_dir=temp_dir) / UPLOADS_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def exports_dir(session_id: str, *, temp_dir: Path | str | None = None) -> Path:
    d = session_root(session_id, temp_dir=temp_dir) / EXPORTS_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def touch_heartbeat(root: Path | str) -> None:
    p = Path(root)
    if not p.is_dir():
        return
    hb = p / HEARTBEAT_NAME
    try:
        hb.write_text("1", encoding="utf-8")
    except OSError:
        pass
    try:
        p.touch()
    except OSError:
        try:
            now = time.time()
            os.utime(p, (now, now))
        except OSError:
            pass


def path_is_inside(parent: Path | str, child: Path | str) -> bool:
    try:
        parent_r = Path(parent).resolve()
        child_r = Path(child).resolve()
    except OSError:
        return False
    try:
        child_r.relative_to(parent_r)
        return True
    except ValueError:
        return False


def is_session_workspace(path: Path | str, *, temp_dir: Path | str | None = None) -> bool:
    p = Path(path)
    try:
        resolved = p.resolve()
    except OSError:
        return False
    parent = workspace_parent(temp_dir=temp_dir).resolve()
    try:
        rel = resolved.relative_to(parent)
    except ValueError:
        return False
    return bool(rel.parts) and bool(_SAFE_SESSION_ID.match(rel.parts[0]))


def wipe_session_root(session_id: str, *, temp_dir: Path | str | None = None) -> None:
    root = session_root(session_id, temp_dir=temp_dir, create=False)
    parent = workspace_parent(temp_dir=temp_dir)
    try:
        if root.resolve() == parent.resolve():
            return
    except OSError:
        return
    if not is_session_workspace(root, temp_dir=temp_dir):
        return
    shutil.rmtree(root, ignore_errors=True)


def rotate_session_id(
    session_state: MutableMapping[str, Any],
    *,
    temp_dir: Path | str | None = None,
) -> str:
    """Wipe the current workspace and mint a new session id."""
    old = session_state.get(SESSION_ID_KEY)
    if isinstance(old, str) and _SAFE_SESSION_ID.match(old):
        wipe_session_root(old, temp_dir=temp_dir)
    sid = uuid.uuid4().hex
    session_state[SESSION_ID_KEY] = sid
    session_root(sid, temp_dir=temp_dir)
    return sid


def _dir_age_sec(path: Path, now: float) -> float:
    hb = path / HEARTBEAT_NAME
    stamp = hb if hb.is_file() else path
    try:
        return now - stamp.stat().st_mtime
    except OSError:
        return 0.0


def sweep_stale_workspaces(
    *,
    protect: Path | str | None = None,
    max_age_sec: float = DEFAULT_MAX_AGE_SEC,
    temp_dir: Path | str | None = None,
) -> int:
    """Remove abandoned ``{temp}/vibe23/{uuid}`` dirs. Never deletes ``protect``."""
    removed = 0
    now = time.time()
    parent = workspace_parent(temp_dir=temp_dir)
    protect_r: Path | None = None
    if protect:
        try:
            protect_r = Path(protect).resolve()
        except OSError:
            protect_r = None

    def _protected(candidate: Path) -> bool:
        if protect_r is None:
            return False
        try:
            c = candidate.resolve()
        except OSError:
            return False
        return c == protect_r or path_is_inside(c, protect_r) or path_is_inside(protect_r, c)

    if not parent.is_dir():
        return 0
    for child in list(parent.iterdir()):
        if not child.is_dir() or not _SAFE_SESSION_ID.match(child.name):
            continue
        if _protected(child):
            continue
        if _dir_age_sec(child, now) > max_age_sec:
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    return removed
