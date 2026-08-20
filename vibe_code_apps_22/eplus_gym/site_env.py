"""Fail-closed site-root resolution. Never treat an empty path as cwd."""
from __future__ import annotations

import os
from pathlib import Path


class SiteRootError(ValueError):
    """SITE_ROOT / --site-root missing or not a directory."""


def require_site_root(raw: str | Path | None = None, *, env: dict[str, str] | None = None) -> Path:
    """Return an existing site directory. Empty string must not become Path('.')."""
    text = "" if raw is None else str(raw).strip()
    if not text:
        environ = env if env is not None else os.environ
        text = str(environ.get("SITE_ROOT") or "").strip()
    if not text:
        raise SiteRootError("SITE_ROOT / --site-root is required")
    path = Path(text)
    if not path.is_dir():
        raise SiteRootError(f"site root is not a directory: {path}")
    return path.resolve()


def repo_rel(path: Path, app_root: Path) -> str:
    """Repository-relative POSIX path when possible; never a username home path."""
    path = Path(path)
    app_root = Path(app_root)
    try:
        return path.resolve().relative_to(app_root.resolve()).as_posix()
    except ValueError:
        return path.name
