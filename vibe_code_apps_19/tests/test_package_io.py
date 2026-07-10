"""Tests for openfdd_package_v1 zip ingest."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from app.package_io import (
    PackageError,
    PackageManifest,
    extract_package_zip,
    load_package_from_dir,
    load_package_zip,
    wipe_workdir,
)


def _make_zip(files: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            data = content.encode("utf-8") if isinstance(content, str) else content
            zf.writestr(name, data)
    return buf.getvalue()


def _hist(n: int = 3) -> str:
    rows = ["timestamp_utc,fan_status,oa_t"]
    for i in range(n):
        rows.append(f"2024-06-01T12:{i:02d}:00Z,1,70")
    return "\n".join(rows)


def _manifest(**kw) -> str:
    base = {
        "schema_version": "openfdd_package_v1",
        "building_id": "DEMO_1",
        "grid_minutes": 5,
        "timezone": "UTC",
    }
    base.update(kw)
    return json.dumps(base)


def test_happy_path_zip_with_weather_and_session_config():
    z = _make_zip(
        {
            "manifest.json": _manifest(),
            "session_config.json": json.dumps(
                {
                    "schema_version": "openfdd_session_v1",
                    "unit_system": "metric",
                    "chw_leave_max_f": 46.0,
                    "role_map": {"AHU_1": {"fan_status": "fan_status"}},
                }
            ),
            "weather/history_wide.csv": "timestamp_utc,oa_t\n2024-06-01T12:00:00Z,71\n",
            "AHU_1/history_wide.csv": _hist(),
            "AHU_1/columns.csv": "col,point_role\nfan_status,fan_status\noa_t,oa_t\n",
        }
    )
    result = load_package_zip(z)
    try:
        assert "AHU_1" in result.frames
        assert "weather" not in result.frames  # weather excluded from equipment
        assert result.weather is not None
        assert result.session_config is not None
        assert result.session_config.unit_system == "metric"
        assert result.report["equipment_count"] == 1
    finally:
        wipe_workdir(result.workdir)


def test_wrapped_top_level_folder():
    z = _make_zip(
        {
            "BUILDING_X/manifest.json": _manifest(building_id="BUILDING_X"),
            "BUILDING_X/AHU_1/history_wide.csv": _hist(),
        }
    )
    result = load_package_zip(z)
    try:
        assert result.manifest.building_id == "BUILDING_X"
        assert "AHU_1" in result.frames
    finally:
        wipe_workdir(result.workdir)


def test_zip_slip_rejected():
    z = _make_zip({"../evil.csv": "a,b\n1,2\n", "manifest.json": _manifest()})
    with pytest.raises(PackageError, match="traversal|Absolute|rejected"):
        load_package_zip(z)


def test_missing_timestamp_utc():
    z = _make_zip(
        {
            "manifest.json": _manifest(),
            "AHU_1/history_wide.csv": "time,fan_status\n2024-01-01,1\n",
        }
    )
    with pytest.raises(PackageError, match="timestamp_utc"):
        load_package_zip(z)


def test_bad_manifest_schema():
    z = _make_zip(
        {
            "manifest.json": json.dumps(
                {"schema_version": "nope", "building_id": "X", "grid_minutes": 5}
            ),
            "AHU_1/history_wide.csv": _hist(),
        }
    )
    with pytest.raises(PackageError, match="schema_version|manifest"):
        load_package_zip(z)


def test_malformed_timestamp():
    z = _make_zip(
        {
            "manifest.json": _manifest(),
            "AHU_1/history_wide.csv": "timestamp_utc,fan_status\nnot-a-date,1\n",
        }
    )
    with pytest.raises(PackageError, match="timestamp"):
        load_package_zip(z)


def test_manifest_model():
    m = PackageManifest.model_validate(
        {
            "schema_version": "openfdd_package_v1",
            "building_id": "B1",
            "grid_minutes": 5,
            "timezone": "America/Chicago",
        }
    )
    assert m.building_id == "B1"


def test_extract_then_load_dir(tmp_path: Path):
    z = _make_zip(
        {
            "manifest.json": _manifest(),
            "AHU_1/history_wide.csv": _hist(),
        }
    )
    work = extract_package_zip(z, dest=tmp_path / "w")
    result = load_package_from_dir(work, workdir=work)
    assert "AHU_1" in result.frames
