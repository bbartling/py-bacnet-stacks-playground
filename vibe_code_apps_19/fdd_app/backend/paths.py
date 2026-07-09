"""Shared path constants for fdd_app backend / frontend / sidecar layout."""

from __future__ import annotations

from pathlib import Path

BACKEND = Path(__file__).resolve().parent
FDD_APP = BACKEND.parent
APP19 = FDD_APP.parent
FRONTEND = FDD_APP / "frontend"
SIDECAR = FDD_APP / "sidecar"
STATIC_DIR = FRONTEND / "static"
SITE_DIR = BACKEND / "site"
DATA_DIR = BACKEND / "data"
CACHE_DIR = BACKEND / ".cache"
