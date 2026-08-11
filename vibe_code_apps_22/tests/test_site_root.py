"""Local site-root pin (no personal path baked into lakeside.paths)."""
from __future__ import annotations

from pathlib import Path

import pytest

from lakeside import paths


def test_remember_and_read_pin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    site = tmp_path / "sp_creekside"
    (site / "reports").mkdir(parents=True)
    pin = tmp_path / ".site_root"
    monkeypatch.setattr(paths, "SITE_ROOT_PIN", pin)
    for key in (
        "LAKESIDE_SITE_ROOT",
        "VIBE22_SITE_ROOT",
        "VIBE22_CREEKSIDE_ROOT",
        "VIBE23_CREEKSIDE_ROOT",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(paths, "APP_ROOT", tmp_path / "app")
    remembered = paths.remember_site_root(site)
    assert remembered == site.resolve()
    assert pin.read_text(encoding="utf-8").strip() == str(site.resolve())
    monkeypatch.delenv("LAKESIDE_SITE_ROOT", raising=False)
    assert paths.site_root() == site.resolve()


def test_invalid_site_rejected(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="reports"):
        paths.remember_site_root(tmp_path)
