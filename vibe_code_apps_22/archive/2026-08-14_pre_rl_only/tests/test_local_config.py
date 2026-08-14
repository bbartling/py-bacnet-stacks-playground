"""Local config.py site root resolution."""
from __future__ import annotations

from pathlib import Path

import lakeside.paths as paths


def test_config_site_root_used_when_env_cleared(monkeypatch, tmp_path: Path):
    site = tmp_path / "mysite"
    (site / "reports").mkdir(parents=True)
    cfg = paths.APP_ROOT / "config.py"
    # Point resolver at a temp config without touching the real one permanently.
    monkeypatch.setattr(paths, "_LOCAL_CONFIG", tmp_path / "config.py")
    (tmp_path / "config.py").write_text(
        "from pathlib import Path\n"
        f"SITE_ROOT = Path(r'{site}')\n",
        encoding="utf-8",
    )
    for key in (
        "SITE_ROOT",
        "LAKESIDE_SITE_ROOT",
        "VIBE22_SITE_ROOT",
        "VIBE22_CREEKSIDE_ROOT",
        "VIBE23_CREEKSIDE_ROOT",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(paths, "SITE_ROOT_PIN", tmp_path / "no_pin")
    assert paths.site_root() == site.resolve() or paths.site_root() == site


def test_env_overrides_config(monkeypatch, tmp_path: Path):
    site_env = tmp_path / "env_site"
    (site_env / "reports").mkdir(parents=True)
    site_cfg = tmp_path / "cfg_site"
    (site_cfg / "reports").mkdir(parents=True)
    monkeypatch.setattr(paths, "_LOCAL_CONFIG", tmp_path / "config.py")
    (tmp_path / "config.py").write_text(
        "from pathlib import Path\n"
        f"SITE_ROOT = Path(r'{site_cfg}')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SITE_ROOT", str(site_env))
    assert paths.site_root() == site_env
