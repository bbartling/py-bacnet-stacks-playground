"""Unit tests for required per-CSV Haystack sidecar maps."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from app.package_io import PackageError, load_package_from_dir, load_package_zip, wipe_workdir
from app.sidecar_maps import (
    _points_from_payload,
    resolve_sidecar_map_path,
    sidecar_candidates,
)


def _hist() -> str:
    return "timestamp_utc,fan_status,oa_t\n2024-06-01T12:00:00Z,1,70\n"


def _manifest() -> str:
    return json.dumps(
        {
            "schema_version": "openfdd_package_v1",
            "building_id": "SIDE_B1",
            "grid_minutes": 5,
            "timezone": "UTC",
        }
    )


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_rejects_package_without_sidecar(tmp_path: Path):
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "manifest.json").write_text(_manifest(), encoding="utf-8")
    eq = root / "AHU_1"
    eq.mkdir()
    (eq / "history_wide.csv").write_text(_hist(), encoding="utf-8")
    with pytest.raises(PackageError, match="missing Haystack map"):
        load_package_from_dir(root)


def test_accepts_session_role_map_without_sidecars(tmp_path: Path):
    """BUG-014: practice packages with session_config.role_map load without per-equip JSON."""
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "manifest.json").write_text(_manifest(), encoding="utf-8")
    (root / "session_config.json").write_text(
        json.dumps(
            {
                "schema_version": "openfdd_session_v1",
                "role_map": {
                    "AHU_1": {
                        "supply-fan-status": "fan_status",
                        "outside-air-temp": "oa_t",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    eq = root / "AHU_1"
    eq.mkdir()
    (eq / "history_wide.csv").write_text(_hist(), encoding="utf-8")
    result = load_package_from_dir(root)
    assert "AHU_1" in result.frames
    assert result.column_map is not None
    assert any("role_map" in w.lower() or "sidecar" in w.lower() for w in result.warnings)


def test_accepts_history_wide_json_and_column_map_json(tmp_path: Path):
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "manifest.json").write_text(_manifest(), encoding="utf-8")
    a = root / "AHU_1"
    a.mkdir()
    (a / "history_wide.csv").write_text(_hist(), encoding="utf-8")
    (a / "history_wide.json").write_text(
        json.dumps({"equipType": "ahu", "points": {"fan-status": "fan-status"}}),
        encoding="utf-8",
    )
    b = root / "AHU_2"
    b.mkdir()
    (b / "history_wide.csv").write_text(_hist(), encoding="utf-8")
    (b / "column_map.json").write_text(
        json.dumps({"equipType": "ahu", "points": {"fan-status": "fan-status"}}),
        encoding="utf-8",
    )
    result = load_package_from_dir(root)
    assert set(result.frames) == {"AHU_1", "AHU_2"}
    assert result.column_map is not None
    assert "AHU_1" in result.column_map["equipment"]
    assert "AHU_2" in result.column_map["equipment"]


def test_accepts_stem_column_map_json_name(tmp_path: Path):
    root = tmp_path / "pkg"
    (root / "AHU_1").mkdir(parents=True)
    (root / "manifest.json").write_text(_manifest(), encoding="utf-8")
    hist = root / "AHU_1" / "history_wide.csv"
    hist.write_text(_hist(), encoding="utf-8")
    (root / "AHU_1" / "history_wide.column_map.json").write_text(
        json.dumps({"points": {"fan-status": "fan-status"}}),
        encoding="utf-8",
    )
    assert resolve_sidecar_map_path(hist) == root / "AHU_1" / "history_wide.column_map.json"
    result = load_package_from_dir(root)
    assert "AHU_1" in result.frames


def test_nested_zip_expanded_and_requires_sidecar():
    inner = _zip(
        {
            "history_wide.csv": _hist(),
            "column_map.json": json.dumps(
                {"equipType": "ahu", "points": {"fan-status": "fan-status"}}
            ),
        }
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", _manifest())
        zf.writestr("AHU_NEST.zip", inner)
    result = load_package_zip(buf.getvalue())
    try:
        # Nested zip expands to AHU_NEST/…
        assert "AHU_NEST" in result.frames
        assert result.column_map is not None
    finally:
        wipe_workdir(result.workdir)


def test_string_equip_is_device_id_not_package_map():
    raw = {
        "equipType": "ahu",
        "equipment_type": "AHU",
        "device": "AHU_1",
        "equip": "AHU_1",
        "points": {
            "fan-status": "fan_s",
            "discharge-air-temp": "sat_f",
        },
    }
    roles, etype = _points_from_payload(raw, "AHU_1")
    assert roles["fan-status"] == "fan_s"
    assert roles["discharge-air-temp"] == "sat_f"
    assert etype in {"AHU", "ahu"}


def test_sidecar_candidates_order():
    hist = Path("AHU_1/history_wide.csv")
    c = sidecar_candidates(hist)
    assert c[0].name == "history_wide.json"
    assert c[1].name == "history_wide.column_map.json"
    assert c[2].name == "column_map.json"
