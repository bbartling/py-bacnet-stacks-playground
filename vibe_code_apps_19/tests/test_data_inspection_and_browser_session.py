"""Data inspection chart + browser session pointer persistence."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.browser_session import (
    BROWSER_SESSION_SCHEMA,
    clear_browser_session_pointer,
    pointer_paths_exist,
    read_browser_session_pointer,
    touch_path,
    write_browser_session_pointer,
)
from app.charts import equipment_inspection_chart


def test_equipment_inspection_chart_stacks_numeric_and_status() -> None:
    idx = pd.date_range("2024-01-01", periods=40, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "discharge-air-temp": [55.0 + (i % 5) for i in range(40)],
            "fan-status": [0, 1] * 20,
            "notes": ["x"] * 40,  # non-numeric — skipped
        },
        index=idx,
    )
    fig = equipment_inspection_chart(df, equipment_id="AHU_1")
    assert fig is not None
    # two plottable columns → two rows (two y-axis domains / two traces)
    assert len(fig.data) == 2
    assert fig.layout.height >= 700


def test_equipment_inspection_chart_respects_column_filter() -> None:
    idx = pd.date_range("2024-01-01", periods=12, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {"a": range(12), "b": range(12, 24), "c": range(24, 36)},
        index=idx,
    )
    fig = equipment_inspection_chart(df, equipment_id="X", columns=["b"])
    assert fig is not None
    assert len(fig.data) == 1
    assert fig.data[0].name == "b"


def test_equipment_inspection_chart_empty_returns_none() -> None:
    assert equipment_inspection_chart(pd.DataFrame()) is None


def test_browser_session_pointer_round_trip(tmp_path: Path) -> None:
    workdir = tmp_path / "vibe19_wd"
    building = workdir / "BUILDING_T"
    workdir.mkdir()
    building.mkdir()
    (building / "manifest.json").write_text(
        '{"schema_version":"openfdd_package_v1","building_id":"BUILDING_T","grid_minutes":5}',
        encoding="utf-8",
    )
    ptr = tmp_path / ".last_browser_session.json"
    write_browser_session_pointer(
        workdir=workdir,
        building_root=building,
        building_id="BUILDING_T",
        source="zip:BUILDING_T",
        path=ptr,
    )
    data = read_browser_session_pointer(ptr)
    assert data is not None
    assert data["schema_version"] == BROWSER_SESSION_SCHEMA
    assert data["building_id"] == "BUILDING_T"
    assert pointer_paths_exist(data)
    touch_path(workdir)
    clear_browser_session_pointer(ptr)
    assert read_browser_session_pointer(ptr) is None


def test_pointer_paths_missing_when_workdir_gone(tmp_path: Path) -> None:
    ptr_data = {
        "schema_version": BROWSER_SESSION_SCHEMA,
        "workdir": str(tmp_path / "missing_wd"),
        "building_root": str(tmp_path / "missing_bldg"),
        "building_id": "X",
    }
    assert pointer_paths_exist(ptr_data) is False
