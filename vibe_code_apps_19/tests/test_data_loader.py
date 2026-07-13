"""Tests for data_loader."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from app.data_loader import (
    detect_timestamp_column,
    infer_poll_seconds,
    load_building_tree,
    load_duckdb_query,
    load_equipment_csv,
    load_sqlite_table,
    load_uploaded_csv,
    normalize_timestamp,
    validate_dataframe,
)


def _write_bundle(root: Path, sub: str, cols: list[str], n: int = 5) -> None:
    d = root / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / "columns.csv").write_text(
        "column,point_role\n" + "\n".join(f"{c},{c}" for c in cols),
        encoding="utf-8",
    )
    rows = ["timestamp_utc," + ",".join(cols)]
    for i in range(n):
        rows.append(f"2024-06-01T12:{i:02d}:00Z," + ",".join(str(70 + i) for _ in cols))
    (d / "history_wide.csv").write_text("\n".join(rows), encoding="utf-8")


def test_detect_timestamp_column():
    df = pd.DataFrame({"timestamp_utc": ["2024-01-01"], "x": [1]})
    assert detect_timestamp_column(df) == "timestamp_utc"


def test_normalize_and_poll(tmp_path: Path):
    p = tmp_path / "h.csv"
    p.write_text("timestamp_utc,val\n2024-01-01T00:00:00Z,1\n2024-01-01T00:05:00Z,2\n", encoding="utf-8")
    df = load_equipment_csv(p)
    assert isinstance(df.index, pd.DatetimeIndex)
    assert infer_poll_seconds(df) == pytest.approx(300.0)


def test_validate_dataframe():
    df = pd.DataFrame({"x": [1]})
    assert validate_dataframe(df)


def test_load_building_tree(tmp_path: Path):
    b = tmp_path / "B1"
    b.mkdir()
    (b / "manifest.json").write_text('{"grid_minutes": 5}', encoding="utf-8")
    _write_bundle(b, "AHU_1", ["fan-cmd", "outside-air-temp"])
    tree = load_building_tree(tmp_path, "B1")
    assert "AHU_1" in tree
    assert len(tree["AHU_1"]) == 5


def test_uploaded_csv():
    raw = b"timestamp_utc,zone_t\n2024-01-01T00:00:00Z,72\n2024-01-01T00:05:00Z,73\n"
    df = load_uploaded_csv(BytesIO(raw))
    assert len(df) == 2


def test_sqlite_readonly(tmp_path: Path):
    import sqlite3

    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE hist (timestamp_utc TEXT, zone_t REAL)")
    con.executemany("INSERT INTO hist VALUES (?, ?)", [("2024-01-01T00:00:00Z", 72.0), ("2024-01-01T00:05:00Z", 73.0)])
    con.commit()
    con.close()
    df = load_sqlite_table(db, "hist")
    assert len(df) == 2


def test_duckdb_select_only(tmp_path: Path):
    import duckdb

    db = tmp_path / "d.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE hist AS SELECT '2024-01-01T00:00:00Z'::TIMESTAMP AS timestamp_utc, 72.0 AS zone_t")
    con.close()
    df = load_duckdb_query(db, "SELECT * FROM hist")
    assert len(df) == 1
    with pytest.raises(ValueError):
        load_duckdb_query(db, "DROP TABLE hist")
