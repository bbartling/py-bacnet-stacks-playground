"""Shared pytest fixtures for vibe19 tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_browser_autoload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent leftover ``.last_browser_session.json`` from restoring frames into AppTests."""
    monkeypatch.setenv("VIBE19_BROWSER_AUTOLOAD", "0")
