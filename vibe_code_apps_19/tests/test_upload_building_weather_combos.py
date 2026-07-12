"""Synthetic + optional real-package multi-upload tests (building / weather / both / dupes).

Application code stays generic. Real BUILDING_100.zip / weather.zip are **test fixtures only**:
set ``VIBE19_TEST_PACKAGE_DIR`` to a folder containing those zips, or rely on the optional
local developer path (skipped when absent).
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

import pytest

from app.multi_zip import ZipPart, load_package_from_zip_parts
from app.package_io import (
    PackageError,
    effective_package_caps,
    load_package_zip,
    wipe_workdir,
)
from tests.package_fixtures import ensure_sidecar_files

ROOT = Path(__file__).resolve().parents[1]


def _optional_real_package_dir() -> Path | None:
    """Test-only fixture discovery — never used by the Streamlit app."""
    env = (os.environ.get("VIBE19_TEST_PACKAGE_DIR") or "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            return p
    # Optional local developer samples (CI skips if missing)
    candidates = [
        Path(
            r"C:\Users\ben\OneDrive\Desktop\testing\tadco_openfdd_sidecar"
            r"\workspace\imports\hvac_systems_CLEANED"
        ),
        ROOT / "data" / "hvac_systems_CLEANED",
    ]
    for c in candidates:
        if c.is_dir() and (c / "BUILDING_100.zip").is_file():
            return c
    return None


@pytest.fixture(scope="module")
def real_building_zip() -> Path:
    d = _optional_real_package_dir()
    if d is None:
        pytest.skip("No VIBE19_TEST_PACKAGE_DIR / local BUILDING_100.zip for optional real-zip tests")
    z = d / "BUILDING_100.zip"
    if not z.is_file():
        pytest.skip(f"missing {z}")
    return z


@pytest.fixture(scope="module")
def real_weather_zip() -> Path:
    d = _optional_real_package_dir()
    if d is None:
        pytest.skip("No test package dir for weather.zip")
    z = d / "weather.zip"
    if not z.is_file():
        pytest.skip(f"missing {z}")
    return z


def _zip_bytes(files: dict[str, str]) -> bytes:
    files = ensure_sidecar_files(files)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _hist() -> str:
    return (
        "timestamp_utc,fan_status,oa_t,sat\n"
        "2024-06-01T12:00:00Z,1,70,55\n"
        "2024-06-01T12:05:00Z,1,71,55\n"
    )


def _openfdd_manifest(building_id: str = "SITE_A") -> str:
    return json.dumps(
        {
            "schema_version": "openfdd_package_v1",
            "building_id": building_id,
            "grid_minutes": 5,
            "timezone": "UTC",
        }
    )


def _building_zip_with_nested_weather(*, building_id: str = "SITE_A") -> bytes:
    return _zip_bytes(
        {
            f"{building_id}/manifest.json": _openfdd_manifest(building_id),
            f"{building_id}/AHU_1/history_wide.csv": _hist(),
            f"{building_id}/AHU_1/columns.csv": "col,point_role\nfan_status,fan_status\noa_t,oa_t\nsat,sat\n",
            f"{building_id}/weather/history_wide.csv": (
                "timestamp_utc,dry_bulb_f\n2024-06-01T12:00:00Z,70\n2024-06-01T12:05:00Z,71\n"
            ),
            f"{building_id}/weather/columns.csv": "col,description\ntimestamp_utc,UTC\ndry_bulb_f,F\n",
        }
    )


def _weather_only_zip() -> bytes:
    return _zip_bytes(
        {
            "weather/manifest.json": json.dumps(
                {
                    "source": "external_weather_api",
                    "location_id": "WX_1",
                    "site_id": "SITE",
                }
            ),
            "weather/history_wide.csv": (
                "timestamp_utc,dry_bulb_f\n2024-06-01T12:00:00Z,72\n2024-06-01T12:05:00Z,73\n"
            ),
            "weather/columns.csv": "col,description\ntimestamp_utc,UTC\ndry_bulb_f,F\n",
        }
    )


def _building_zip_without_weather(*, building_id: str = "SITE_B") -> bytes:
    return _zip_bytes(
        {
            f"{building_id}/manifest.json": _openfdd_manifest(building_id),
            f"{building_id}/AHU_1/history_wide.csv": _hist(),
            f"{building_id}/AHU_1/columns.csv": "col,point_role\nfan_status,fan_status\noa_t,oa_t\nsat,sat\n",
        }
    )


def test_synthetic_building_alone_loads():
    caps = effective_package_caps(for_browser_upload=True)
    result = load_package_zip(_building_zip_with_nested_weather(), caps=caps)
    try:
        assert "AHU_1" in result.frames
        assert result.weather is not None
        assert result.manifest.building_id == "SITE_A"
    finally:
        wipe_workdir(result.workdir)


def test_synthetic_weather_alone_rejected():
    with pytest.raises(PackageError, match=r"weather-only|cannot be loaded by itself"):
        load_package_zip(_weather_only_zip())


def test_synthetic_building_plus_weather_multi_upload():
    """Same human mistake: select building zip + weather.zip together."""
    result = load_package_from_zip_parts(
        [
            ZipPart("SITE_A.zip", _building_zip_with_nested_weather()),
            ZipPart("weather.zip", _weather_only_zip()),
        ]
    )
    try:
        assert "AHU_1" in result.frames
        assert result.weather is not None
        assert result.manifest.building_id == "SITE_A"
        assert any(
            "Ignored extra" in w or "already includes weather" in w for w in result.warnings
        )
    finally:
        wipe_workdir(result.workdir)


def test_synthetic_building_without_weather_plus_weather_merges():
    result = load_package_from_zip_parts(
        [
            ZipPart("SITE_B.zip", _building_zip_without_weather()),
            ZipPart("weather.zip", _weather_only_zip()),
        ]
    )
    try:
        assert "AHU_1" in result.frames
        assert result.weather is not None and not result.weather.empty
        assert any("Merged sibling weather" in w for w in result.warnings)
    finally:
        wipe_workdir(result.workdir)


def test_synthetic_duplicate_building_uploads_deduped():
    data = _building_zip_with_nested_weather()
    result = load_package_from_zip_parts(
        [
            ZipPart("SITE_A.zip", data),
            ZipPart("SITE_A.zip", data),  # accidental double-select
        ]
    )
    try:
        assert "AHU_1" in result.frames
        assert any("duplicate" in w.lower() for w in result.warnings)
    finally:
        wipe_workdir(result.workdir)


def test_real_building_alone(real_building_zip: Path):
    caps = effective_package_caps(for_browser_upload=True)
    result = load_package_zip(real_building_zip.read_bytes(), caps=caps)
    try:
        assert len(result.frames) >= 40
        assert result.weather is not None
    finally:
        wipe_workdir(result.workdir)


def test_real_weather_alone_rejected(real_weather_zip: Path):
    with pytest.raises(PackageError, match=r"weather-only|cannot be loaded by itself"):
        load_package_zip(real_weather_zip.read_bytes())


def test_real_building_plus_weather(real_building_zip: Path, real_weather_zip: Path):
    result = load_package_from_zip_parts(
        [
            ZipPart(real_building_zip.name, real_building_zip.read_bytes()),
            ZipPart(real_weather_zip.name, real_weather_zip.read_bytes()),
        ]
    )
    try:
        assert len(result.frames) >= 40
        assert result.weather is not None
        assert result.manifest.building_id == "BUILDING_100"
    finally:
        wipe_workdir(result.workdir)


def test_real_duplicate_building(real_building_zip: Path):
    data = real_building_zip.read_bytes()
    result = load_package_from_zip_parts(
        [
            ZipPart(real_building_zip.name, data),
            ZipPart(real_building_zip.name, data),
        ]
    )
    try:
        assert len(result.frames) >= 40
        assert any("duplicate" in w.lower() for w in result.warnings)
    finally:
        wipe_workdir(result.workdir)
