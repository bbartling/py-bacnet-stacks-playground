"""Tests for openfdd_package_v1 zip ingest."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from tests.package_fixtures import ensure_sidecar_files
from app.package_io import (
    DEFAULT_MAX_ENTRIES,
    DEFAULT_MAX_EQUIPMENT,
    DEFAULT_PACKAGE_MB,
    PackageError,
    PackageManifest,
    bytes_as_mb,
    dataset_size_caption,
    effective_package_caps,
    extract_package_zip,
    load_package_from_dir,
    load_package_zip,
    wipe_workdir,
)


def _make_zip(files: dict[str, str | bytes]) -> bytes:
    files = ensure_sidecar_files(files)
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


def test_effective_caps_local_defaults(monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)
    monkeypatch.delenv("OPENFDD_MAX_ZIP_MB", raising=False)
    monkeypatch.delenv("OPENFDD_MAX_UNCOMPRESSED_MB", raising=False)
    monkeypatch.delenv("OPENFDD_MAX_ENTRIES", raising=False)
    monkeypatch.delenv("OPENFDD_MAX_EQUIPMENT", raising=False)
    monkeypatch.setenv("APP_MODE", "local")
    caps = effective_package_caps()
    assert caps.max_zip_mb == DEFAULT_PACKAGE_MB
    assert caps.max_uncompressed_mb == DEFAULT_PACKAGE_MB
    assert caps.max_entries == DEFAULT_MAX_ENTRIES
    assert caps.max_equipment == DEFAULT_MAX_EQUIPMENT


def test_effective_caps_cloud_same_default(monkeypatch):
    """Cloud uses the same package defaults (raise/lower via env if needed)."""
    for key in (
        "OPENFDD_MAX_ZIP_MB",
        "OPENFDD_MAX_UNCOMPRESSED_MB",
        "OPENFDD_MAX_ENTRIES",
        "OPENFDD_MAX_EQUIPMENT",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_MODE", "cloud")
    caps = effective_package_caps()
    assert caps.max_zip_mb == DEFAULT_PACKAGE_MB
    assert caps.max_uncompressed_mb == DEFAULT_PACKAGE_MB
    assert caps.max_entries == DEFAULT_MAX_ENTRIES
    assert caps.max_equipment == DEFAULT_MAX_EQUIPMENT


def test_load_package_report_includes_size_mb():
    z = _make_zip(
        {
            "manifest.json": _manifest(),
            "AHU_1/history_wide.csv": _hist(),
        }
    )
    result = load_package_zip(z)
    try:
        assert result.report["source"] == "zip"
        assert result.report["zip_bytes"] == len(z)
        assert result.report["zip_mb"] == bytes_as_mb(len(z))
        assert result.report["uncompressed_bytes"] > 0
        assert result.report["uncompressed_mb"] == bytes_as_mb(result.report["uncompressed_bytes"])
        assert result.report["max_zip_mb"] == effective_package_caps().max_zip_mb
        caption = dataset_size_caption(result.report)
        assert "Dataset:" in caption
        assert "MB zip" in caption
        assert "limits" in caption
    finally:
        wipe_workdir(result.workdir)


def test_effective_caps_env_override(monkeypatch):
    monkeypatch.setenv("APP_MODE", "cloud")
    monkeypatch.setenv("OPENFDD_MAX_ZIP_MB", "512")
    monkeypatch.setenv("OPENFDD_MAX_ENTRIES", "77")
    monkeypatch.setenv("OPENFDD_MAX_EQUIPMENT", "33")
    caps = effective_package_caps()
    assert caps.max_zip_mb == 512
    assert caps.max_entries == 77
    assert caps.max_equipment == 33


def test_loads_above_legacy_entry_and_equipment_limits(monkeypatch):
    """Full-ish package: >200 zip entries and >20 equipment under default caps."""
    monkeypatch.delenv("OPENFDD_MAX_ENTRIES", raising=False)
    monkeypatch.delenv("OPENFDD_MAX_EQUIPMENT", raising=False)
    files: dict[str, str | bytes] = {"manifest.json": _manifest(building_id="BIG_DEMO")}
    # 25 equipment × history = above old 20 equip
    for i in range(25):
        files[f"AHU_{i}/history_wide.csv"] = _hist()
    # Pad past the old 200-entry hard stop (BUILDING_100-style packages hit ~250)
    for i in range(220):
        files[f"AHU_0/meta_{i}.txt"] = f"pad-{i}\n"
    z = _make_zip(files)
    with zipfile.ZipFile(io.BytesIO(z)) as zf:
        assert len(zf.infolist()) > 200
    result = load_package_zip(z)
    try:
        assert len(result.frames) == 25
        assert result.report["equipment_count"] == 25
    finally:
        wipe_workdir(result.workdir)


def test_browser_caps_load_tadco_building_100_zip():
    """Same path as Streamlit 'Load zip(s)' for the real TADCO BUILDING_100.zip."""
    zpath = Path(
        r"C:\Users\ben\OneDrive\Desktop\testing\tadco_openfdd_sidecar"
        r"\workspace\imports\hvac_systems_CLEANED\BUILDING_100.zip"
    )
    if not zpath.is_file():
        pytest.skip(f"TADCO zip not present: {zpath}")
    data = zpath.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        n = len(zf.infolist())
    assert n > 200, f"fixture should exceed legacy 200-entry cap, got {n}"
    caps = effective_package_caps(for_browser_upload=True)
    result = load_package_zip(data, caps=caps)
    try:
        assert result.manifest.building_id == "BUILDING_100"
        assert len(result.frames) >= 40
        assert result.weather is not None and not result.weather.empty
        assert result.session_config is not None
    finally:
        wipe_workdir(result.workdir)


def test_rejects_when_entries_cap_low(monkeypatch):
    monkeypatch.setenv("OPENFDD_MAX_ENTRIES", "3")
    z = _make_zip(
        {
            "manifest.json": _manifest(),
            "AHU_1/history_wide.csv": _hist(),
            "AHU_2/history_wide.csv": _hist(),
            "AHU_3/history_wide.csv": _hist(),
            "extra.txt": "x\n",
        }
    )
    with pytest.raises(PackageError, match=r"Too many zip entries \(.* > 3\)"):
        load_package_zip(z)


def test_rejects_when_equipment_cap_low(monkeypatch):
    monkeypatch.setenv("OPENFDD_MAX_EQUIPMENT", "2")
    monkeypatch.setenv("OPENFDD_MAX_ENTRIES", "50")
    files: dict[str, str | bytes] = {"manifest.json": _manifest()}
    for i in range(3):
        files[f"AHU_{i}/history_wide.csv"] = _hist()
    z = _make_zip(files)
    with pytest.raises(PackageError, match=r"Too many equipment folders \(3 > 2\)"):
        load_package_zip(z)
