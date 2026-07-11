"""AppConfig APP_MODE / Docker path gating."""

from __future__ import annotations

from pathlib import Path

from app.config import AppConfig, running_in_docker


def test_cloud_mode_disallows_server_paths(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APP_MODE", "cloud")
    monkeypatch.setenv("HVAC_DATA_ROOT", str(tmp_path / "missing_tree"))
    monkeypatch.delenv("VIBE19_DOCKER", raising=False)
    cfg = AppConfig.load()
    assert cfg.is_cloud is True
    assert cfg.allow_server_paths is False


def test_local_mode_allows_paths_when_data_exists(monkeypatch, tmp_path: Path):
    data = tmp_path / "hvac"
    data.mkdir()
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("HVAC_DATA_ROOT", str(data))
    monkeypatch.delenv("VIBE19_DOCKER", raising=False)
    monkeypatch.setattr("app.config.running_in_docker", lambda: False)
    cfg = AppConfig.load()
    assert cfg.is_cloud is False
    assert cfg.allow_server_paths is True


def test_docker_local_without_data_is_zip_only(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("HVAC_DATA_ROOT", str(tmp_path / "nope"))
    monkeypatch.setenv("VIBE19_DOCKER", "1")
    cfg = AppConfig.load()
    assert running_in_docker() is True
    assert cfg.is_cloud is True
    assert cfg.allow_server_paths is False


def test_docker_local_with_mounted_data_allows_folder(monkeypatch, tmp_path: Path):
    data = tmp_path / "mounted"
    data.mkdir()
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("HVAC_DATA_ROOT", str(data))
    monkeypatch.setenv("VIBE19_DOCKER", "1")
    cfg = AppConfig.load()
    assert cfg.is_cloud is False
    assert cfg.allow_server_paths is True


def test_auto_missing_root_is_cloud(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APP_MODE", "auto")
    monkeypatch.setenv("HVAC_DATA_ROOT", str(tmp_path / "absent"))
    monkeypatch.delenv("VIBE19_DOCKER", raising=False)
    monkeypatch.setattr("app.config.running_in_docker", lambda: False)
    cfg = AppConfig.load()
    assert cfg.is_cloud is True
