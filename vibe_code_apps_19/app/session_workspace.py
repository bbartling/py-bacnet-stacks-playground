"""Per-browser-session temporary workspace for Vibe 19 uploads.

Hosted Streamlit (Community Cloud / GHCR ``APP_MODE=cloud``) keeps each
visitor's extracted packages under ``{temp}/vibe19/{session_id}/``.
Clearing or replacing a dataset must not touch another session's directory.
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

SESSION_PARENT_NAME = "vibe19"
HEARTBEAT_NAME = ".vibe19_session_heartbeat"
PACKAGE_DIRNAME = "package"
EXPORTS_DIRNAME = "exports"
SESSION_ID_KEY = "session_id"
# uuid4.hex is 32 lowercase hex chars. Tests may use a 32-char hex stand-in.
_SAFE_SESSION_ID = re.compile(r"^[0-9a-f]{32}$")
LEGACY_TEMP_PREFIX = "vibe19_"
DEFAULT_MAX_AGE_SEC = 6 * 3600


def ensure_session_id(session_state: MutableMapping[str, Any]) -> str:
    """Return a high-entropy session id, creating one if missing."""
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
        (root / PACKAGE_DIRNAME).mkdir(exist_ok=True)
        (root / EXPORTS_DIRNAME).mkdir(exist_ok=True)
    return root


def package_dir(session_id: str, *, temp_dir: Path | str | None = None) -> Path:
    d = session_root(session_id, temp_dir=temp_dir) / PACKAGE_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def exports_dir(session_id: str, *, temp_dir: Path | str | None = None) -> Path:
    d = session_root(session_id, temp_dir=temp_dir) / EXPORTS_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def touch_heartbeat(root: Path | str) -> None:
    p = Path(root)
    if not p.exists():
        return
    hb = p / HEARTBEAT_NAME if p.is_dir() else p
    if p.is_dir():
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
    else:
        try:
            p.touch()
        except OSError:
            pass


def path_is_inside(parent: Path | str, child: Path | str) -> bool:
    """True when ``child`` resolves strictly inside or equal to ``parent``."""
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


def is_legacy_temp_dir(path: Path) -> bool:
    return path.is_dir() and path.name.startswith(LEGACY_TEMP_PREFIX) and path.name != SESSION_PARENT_NAME


def is_session_workspace(path: Path | str, *, temp_dir: Path | str | None = None) -> bool:
    """True if path is a UUID session root (or a file/dir inside one)."""
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
    parts = rel.parts
    if not parts:
        return False  # the parent itself
    return bool(_SAFE_SESSION_ID.match(parts[0]))


def wipe_workspace(
    path: Path | str | None,
    *,
    session_id: str | None = None,
    temp_dir: Path | str | None = None,
) -> None:
    """Delete a session workspace or legacy vibe19_* dir. Never the parent."""
    if not path:
        return
    p = Path(path)
    if not p.exists():
        return
    parent = workspace_parent(temp_dir=temp_dir)
    try:
        if p.resolve() == parent.resolve():
            return
    except OSError:
        return
    if session_id:
        allowed = session_root(session_id, temp_dir=temp_dir, create=False)
        if not path_is_inside(allowed, p) and p.resolve() != allowed.resolve():
            return
    if is_session_workspace(p, temp_dir=temp_dir):
        # UUID session root → wipe the whole session. Nested package/exports →
        # that directory only (failed extract / re-upload must not drop exports).
        try:
            rel = p.resolve().relative_to(parent.resolve())
        except (ValueError, OSError):
            return
        if len(rel.parts) == 1:
            shutil.rmtree(parent / rel.parts[0], ignore_errors=True)
        else:
            shutil.rmtree(p, ignore_errors=True)
        return
    if is_legacy_temp_dir(p):
        shutil.rmtree(p, ignore_errors=True)


def wipe_session_root(session_id: str, *, temp_dir: Path | str | None = None) -> None:
    """Delete one session's UUID directory. Never the shared parent."""
    root = session_root(session_id, temp_dir=temp_dir, create=False)
    wipe_workspace(root, session_id=session_id, temp_dir=temp_dir)


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
    """Remove abandoned session dirs and legacy vibe19_* temps.

    Never deletes ``{temp}/vibe19`` itself. Never deletes ``protect`` (current
    session) even if another user triggered the sweep.
    """
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

    if parent.is_dir():
        for child in list(parent.iterdir()):
            if not child.is_dir():
                continue
            if not _SAFE_SESSION_ID.match(child.name):
                continue
            if _protected(child):
                continue
            if _dir_age_sec(child, now) > max_age_sec:
                shutil.rmtree(child, ignore_errors=True)
                removed += 1

    # Legacy mkdtemp(prefix="vibe19_") siblings next to the parent, not inside it.
    scan_root = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
    try:
        for p in scan_root.glob(f"{LEGACY_TEMP_PREFIX}*"):
            if not p.is_dir():
                continue
            if p.name == SESSION_PARENT_NAME:
                continue
            if _protected(p):
                continue
            try:
                age = now - p.stat().st_mtime
            except OSError:
                continue
            if age > max_age_sec:
                shutil.rmtree(p, ignore_errors=True)
                removed += 1
    except OSError:
        pass
    return removed
