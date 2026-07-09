"""Shared pytest fixtures for Haystack-backed dashboard tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

APP19 = Path(__file__).resolve().parent.parent
FDD_APP = Path(__file__).resolve().parent
BACKEND = FDD_APP / "backend"
SIDECAR = FDD_APP / "sidecar"
for _p in (APP19, BACKEND, SIDECAR):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from shared.env_loader import load_env_files  # noqa: E402

load_env_files()


@pytest.fixture(scope="session", autouse=True)
def _ensure_haystack_model_session() -> None:
    """Bootstrap SPARQL model from CSV when DATA_ROOT is configured (.env or env var)."""
    from shared.data_config import get_config

    cfg = get_config()
    if not cfg.building_dir.is_dir() and not os.environ.get("HVAC_DATA_ROOT"):
        return
    get_config.cache_clear()
    from haystack_rdf.auto_sync import ensure_model_synced

    ensure_model_synced(get_config(), force=True)


@pytest.fixture(autouse=True)
def _reset_data_config_cache() -> None:
    """Avoid cross-test pollution when a test monkeypatches HVAC_BUILDING / RDF paths."""
    from shared.data_config import get_config

    get_config.cache_clear()
    yield
    get_config.cache_clear()
