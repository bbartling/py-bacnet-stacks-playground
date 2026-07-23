"""Tests for energyplus-ensure / dial-loads docker route + geo CLI + answers discovery."""

from __future__ import annotations

import builtins
from pathlib import Path
from unittest.mock import patch

import pytest

from wattlab.energyplus.geo_idf import main as geo_main
from wattlab.energyplus.mcp_runtime import parse_version_pin


def test_parse_version_pin():
    pin = parse_version_pin()
    assert "LBNL-ETA/EnergyPlus-MCP" in pin["repo"]
    assert pin["commit"]
    assert pin["image"]


def test_geo_idf_requires_stories_wwr():
    with pytest.raises(SystemExit):
        geo_main(["--src", "x.idf", "--dst", "y.idf", "--target-area-ft2", "10000"])


def test_dial_loads_routes_via_docker_when_no_local_mcp(tmp_path: Path):
    from wattlab.energyplus import dial_loads as dl

    src = tmp_path / "in.idf"
    dst = tmp_path / "out.idf"
    src.write_text("Building,\n  X,\n", encoding="utf-8")
    fake_meta = {
        "via": "mcp-exec",
        "src": str(src),
        "dst": str(dst),
        "lights_w_per_m2": 4.5,
        "equip_w_per_m2": 4.2,
        "infil_mult": 1.4,
        "hint": "x",
    }

    real_import = builtins.__import__

    def _imp(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "energyplus_mcp_server" or name.startswith("energyplus_mcp_server."):
            raise ImportError("forced missing MCP")
        return real_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=_imp):
        with patch(
            "wattlab.energyplus.mcp_runtime.dial_loads_via_docker",
            return_value=fake_meta,
        ) as mock_docker:
            meta = dl.dial_loads_mcp(
                src, dst, lights_w_per_m2=4.5, equip_w_per_m2=4.2, infil_mult=1.4
            )
    assert meta["via"] == "mcp-exec"
    mock_docker.assert_called_once()


def test_answers_discovery_answers_json_wins(tmp_path: Path):
    from wattlab.studio.status import build_session_status

    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "answers_building_z.json").write_text('{"z": 1}', encoding="utf-8")
    (reports / "answers.json").write_text(
        '{"building_type": "office", "floor_area_ft2": 10000, "city": "x"}',
        encoding="utf-8",
    )
    out = build_session_status(workspace=tmp_path)
    assert str(out["paths"]["answers"]).endswith("answers.json")


def test_answers_discovery_glob_sorted_without_100_50_prefer(tmp_path: Path):
    from wattlab.studio.status import build_session_status

    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "answers_building_100.json").write_text('{"id": "100"}', encoding="utf-8")
    (reports / "answers_building_50.json").write_text('{"id": "50"}', encoding="utf-8")
    out = build_session_status(workspace=tmp_path)
    # Sorted: answers_building_100.json before answers_building_50.json
    assert str(out["paths"]["answers"]).endswith("answers_building_100.json")
