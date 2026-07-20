"""DinD host-path map, ReadVars (-r), root/artifacts, city provenance."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_artifacts_root_under_studio_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from wattlab import config as cfg

    ws = tmp_path / "data"
    ws.mkdir()
    monkeypatch.delenv("WATTLAB_ARTIFACTS", raising=False)
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(ws))
    root = cfg.artifacts_root()
    assert root == (ws / ".artifacts").resolve()
    assert root.is_dir()


def test_host_path_for_docker_maps_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from wattlab.config import host_path_for_docker

    cont = tmp_path / "data"
    host = tmp_path / "home_ws"
    cont.mkdir()
    host.mkdir()
    nested = cont / ".artifacts" / "run1" / "file.idf"
    nested.parent.mkdir(parents=True)
    nested.write_text("x", encoding="utf-8")

    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(cont))
    monkeypatch.setenv("WATTLAB_HOST_WORKSPACE", str(host))
    mapped = host_path_for_docker(nested)
    assert mapped == (host / ".artifacts" / "run1" / "file.idf").resolve()


def test_host_path_for_docker_noop_without_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from wattlab.config import host_path_for_docker

    monkeypatch.delenv("WATTLAB_HOST_WORKSPACE", raising=False)
    monkeypatch.delenv("WATTLAB_STUDIO_WORKSPACE", raising=False)
    p = tmp_path / "a.idf"
    p.write_text("x", encoding="utf-8")
    assert host_path_for_docker(p) == p.resolve()


def test_detect_root_prefers_wattlab_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from wattlab import config as cfg

    fake = tmp_path / "app"
    (fake / "examples" / "prototypes").mkdir(parents=True)
    monkeypatch.setenv("WATTLAB_ROOT", str(fake))
    assert cfg._detect_root() == fake.resolve()


def test_troy_resolves_detroit_not_madison() -> None:
    from wattlab.defaults import resolve_city, resolve_profile

    cid, meta = resolve_city("troy")
    assert cid == "detroit"
    assert meta["climate_zone"] == "5A"
    assert "Madison" not in (meta.get("label") or "")

    profile = resolve_profile(
        {"building_type": "office", "city": "troy", "floor_area_ft2": 140_000}
    )
    assert profile["field_sources"]["city"]["value"] == "detroit"
    note = profile["field_sources"]["city"].get("note") or ""
    assert "troy" in note.lower()
    assert "madison" not in (profile.get("climate_city") or "").lower()


def test_unknown_city_keeps_label_not_madison() -> None:
    from wattlab.defaults import resolve_city, resolve_profile

    cid, meta = resolve_city("Springfield_IL_Custom")
    assert cid == "springfield_il_custom"
    assert meta.get("user_supplied") is True
    assert "Madison" not in (meta.get("label") or "")
    assert "conceptual" in (meta.get("epw_note") or "").lower()

    profile = resolve_profile({"building_type": "office", "city": "Springfield_IL_Custom"})
    assert profile["field_sources"]["city"]["value"] == "springfield_il_custom"
    assert profile["field_sources"]["city"]["source"] == "user"


def test_run_energyplus_passes_readvars_and_host_mounts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from wattlab.energyplus import docker as dmod

    data = tmp_path / "data"
    host = tmp_path / "host"
    data.mkdir()
    host.mkdir()
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(data))
    monkeypatch.setenv("WATTLAB_HOST_WORKSPACE", str(host))

    idf = data / "baseline.idf"
    epw = data / "weather.epw"
    out = data / "out"
    idf.write_text("Building,\n;", encoding="utf-8")
    epw.write_text("EPW", encoding="utf-8")
    out.mkdir()

    captured: list[list[str]] = []

    def fake_run(args, **kwargs):  # noqa: ANN003, ANN201
        captured.append(list(args))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(dmod, "docker_bin", lambda: "docker")
    monkeypatch.setattr(dmod, "ensure_image", lambda build=False: "energyplus-mcp-dev")
    with patch("wattlab.energyplus.docker.subprocess.run", side_effect=fake_run):
        dmod.run_energyplus(idf, epw, out, readvars=True)

    assert captured, "docker run was not invoked"
    args = captured[0]
    assert "-r" in args
    host_ws = str(host.resolve()).replace("\\", "/")
    vol_flags = [args[i + 1] for i, a in enumerate(args) if a == "-v"]
    assert vol_flags
    # Windows mounts look like C:/host/...:/work/in — match host workspace substring.
    for v in vol_flags:
        assert host_ws in v.replace("\\", "/"), (v, host_ws)


def test_run_energyplus_can_disable_readvars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from wattlab.energyplus import docker as dmod

    idf = tmp_path / "a.idf"
    epw = tmp_path / "b.epw"
    out = tmp_path / "out"
    idf.write_text("x", encoding="utf-8")
    epw.write_text("y", encoding="utf-8")
    out.mkdir()
    captured: list[list[str]] = []

    def fake_run(args, **kwargs):  # noqa: ANN003, ANN201
        captured.append(list(args))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(dmod, "docker_bin", lambda: "docker")
    monkeypatch.setattr(dmod, "ensure_image", lambda build=False: "energyplus-mcp-dev")
    with patch("wattlab.energyplus.docker.subprocess.run", side_effect=fake_run):
        dmod.run_energyplus(idf, epw, out, readvars=False)

    assert "-r" not in captured[0]
