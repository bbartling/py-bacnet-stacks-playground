"""Tests for agent → Streamlit bootstrap bridge."""

from __future__ import annotations

import json
from pathlib import Path

from app.bootstrap import (
    BOOTSTRAP_SCHEMA,
    agent_bootstrap_allowed,
    build_bootstrap_payload,
    default_bootstrap_path,
    read_bootstrap,
    write_bootstrap,
)


def test_build_and_write_bootstrap(tmp_path: Path, monkeypatch):
    pkg = tmp_path / "b.zip"
    pkg.write_bytes(b"PK\x03\x04")
    fs = tmp_path / "fault_settings.json"
    fs.write_text("{}", encoding="utf-8")
    payload = build_bootstrap_payload(
        package_path=pkg,
        session_config={"schema_version": "openfdd_session_v1", "params": {"VAV-1": {"confirm_min": 5}}},
        fault_settings_path=fs,
        out_dir=tmp_path,
        auto_run_rules=True,
    )
    assert payload["schema_version"] == BOOTSTRAP_SCHEMA
    assert payload["auto_run_rules"] is True

    out_boot = tmp_path / "streamlit_bootstrap.json"
    # Point default bootstrap into tmp
    monkeypatch.setattr("app.bootstrap.app_root", lambda: tmp_path)
    written = write_bootstrap(payload, path=out_boot, also_default=True)
    assert out_boot.is_file()
    assert (tmp_path / ".last_agent_session.json").is_file()
    loaded = read_bootstrap(out_boot)
    assert loaded is not None
    assert loaded["package_path"] == str(pkg.resolve())
    assert loaded["session_config"]["params"]["VAV-1"]["confirm_min"] == 5


def test_resolve_env_bootstrap(tmp_path: Path, monkeypatch):
    boot = tmp_path / "custom.json"
    boot.write_text(
        json.dumps(
            {
                "schema_version": BOOTSTRAP_SCHEMA,
                "package_path": str(tmp_path / "x.zip"),
                "auto_run_rules": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VIBE19_BOOTSTRAP", str(boot))
    loaded = read_bootstrap()
    assert loaded is not None
    assert loaded["auto_run_rules"] is False


def test_agent_bootstrap_allowed_cloud_vs_local(monkeypatch):
    monkeypatch.delenv("VIBE19_BOOTSTRAP", raising=False)
    assert agent_bootstrap_allowed(is_cloud=False) is True
    assert agent_bootstrap_allowed(is_cloud=True) is False
    monkeypatch.setenv("VIBE19_BOOTSTRAP", "/tmp/explicit.json")
    assert agent_bootstrap_allowed(is_cloud=True) is True
