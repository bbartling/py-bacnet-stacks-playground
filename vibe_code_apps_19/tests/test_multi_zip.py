"""Multi-zip merge + agent prerun helpers."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from tests.package_fixtures import ensure_sidecar_files
from app.multi_zip import ZipPart, load_package_from_zip_parts
from app.package_io import wipe_workdir


def _zip_bytes(files: dict[str, str]) -> bytes:
    files = ensure_sidecar_files(files)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _hist(eq: str = "x") -> str:
    return (
        "timestamp_utc,fan_status,oa_t\n"
        "2024-06-01T12:00:00Z,1,70\n"
        "2024-06-01T12:05:00Z,1,71\n"
    )


def test_merge_two_parts_loads_both_equipment():
    part1 = _zip_bytes(
        {
            "manifest.json": json.dumps(
                {
                    "schema_version": "openfdd_package_v1",
                    "building_id": "MULTI_1",
                    "grid_minutes": 5,
                    "timezone": "UTC",
                }
            ),
            "AHU_1/history_wide.csv": _hist(),
            "AHU_1/columns.csv": "col,point_role\nfan_status,fan_status\noa_t,oa_t\n",
        }
    )
    part2 = _zip_bytes(
        {
            "AHU_2/history_wide.csv": _hist(),
            "AHU_2/columns.csv": "col,point_role\nfan_status,fan_status\noa_t,oa_t\n",
        }
    )
    result = load_package_from_zip_parts(
        [
            ZipPart("MULTI_1_part01.zip", part1),
            ZipPart("MULTI_1_part02.zip", part2),
        ]
    )
    try:
        assert set(result.frames) == {"AHU_1", "AHU_2"}
        assert result.report["source"] == "multi_zip"
        assert result.report["zip_part_count"] == 2
        assert result.manifest.building_id == "MULTI_1"
    finally:
        wipe_workdir(result.workdir)


def test_ensure_column_map_builds_when_missing():
    import pandas as pd

    from app.agent_prerun import ensure_column_map

    idx = pd.date_range("2024-01-01", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame({"discharge-air-temp": [55.0, 56.0, 57.0], "fan-status": [1, 1, 1]}, index=idx)
    df.attrs["equipment_id"] = "AHU_1"
    cmap, built, warns = ensure_column_map(
        {"AHU_1": df}, existing_map=None, building_id="B1"
    )
    assert built
    assert cmap is not None
    assert "equipment" in cmap or "points" in cmap
