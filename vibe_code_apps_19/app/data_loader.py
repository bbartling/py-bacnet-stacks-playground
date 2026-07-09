"""Load historian CSV trees, uploads, SQLite/DuckDB into pandas DataFrames."""

from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

TS_CANDIDATES = ("timestamp_utc", "timestamp", "time", "datetime", "date_time")


def detect_timestamp_column(df: pd.DataFrame) -> str | None:
    for c in TS_CANDIDATES:
        if c in df.columns:
            return c
    for c in df.columns:
        if "time" in c.lower() or "date" in c.lower():
            return c
    return None


def normalize_timestamp(df: pd.DataFrame, col: str | None = None) -> pd.DataFrame:
    out = df.copy()
    ts_col = col or detect_timestamp_column(out)
    if ts_col is None:
        return out
    out[ts_col] = pd.to_datetime(out[ts_col], utc=True, errors="coerce")
    out = out.dropna(subset=[ts_col])
    out = out.sort_values(ts_col).set_index(ts_col)
    out.index.name = "timestamp"
    return out


def infer_poll_seconds(df: pd.DataFrame) -> float:
    if not isinstance(df.index, pd.DatetimeIndex) or len(df.index) < 2:
        return 300.0
    deltas = df.index.to_series().diff().dropna().dt.total_seconds()
    if deltas.empty:
        return 300.0
    med = float(deltas.median())
    return med if med > 0 else 300.0


def validate_dataframe(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    if df.empty:
        issues.append("DataFrame is empty")
    if not isinstance(df.index, pd.DatetimeIndex):
        issues.append("No datetime index — assign or detect timestamp column")
    if df.index.has_duplicates:
        issues.append(f"Duplicate timestamps: {int(df.index.duplicated().sum())}")
    return issues


def _read_columns_map(columns_path: Path) -> dict[str, str]:
    """col -> point_role or col name."""
    if not columns_path.is_file():
        return {}
    df = pd.read_csv(columns_path)
    col_key = "col" if "col" in df.columns else df.columns[0]
    role_key = next((c for c in ("point_role", "role", "description") if c in df.columns), None)
    out: dict[str, str] = {}
    for _, row in df.iterrows():
        col = str(row[col_key]).strip()
        if not col or col in ("col", "column"):
            continue
        role = str(row[role_key]).strip() if role_key else col
        out[col] = role
    return out


def load_equipment_csv(history_path: Path, columns_path: Path | None = None) -> pd.DataFrame:
    raw = pd.read_csv(history_path)
    ts = detect_timestamp_column(raw)
    df = normalize_timestamp(raw, ts)
    if columns_path and columns_path.is_file():
        _read_columns_map(columns_path)  # validate file exists
    return df


def discover_equipment(building_root: Path) -> list[dict[str, Any]]:
    """Find equipment folders with history_wide.csv + columns.csv."""
    found: list[dict[str, Any]] = []
    if not building_root.is_dir():
        return found
    for path in building_root.rglob("history_wide.csv"):
        eq_dir = path.parent
        cols = eq_dir / "columns.csv"
        eq_id = eq_dir.name
        rel = eq_dir.relative_to(building_root)
        if len(rel.parts) > 1:
            eq_id = rel.parts[-1]
        found.append(
            {
                "equipment_id": eq_id,
                "history_path": path,
                "columns_path": cols if cols.is_file() else None,
                "folder": eq_dir,
            }
        )
    return sorted(found, key=lambda x: x["equipment_id"])


def load_building_tree(data_root: Path, building_id: str) -> dict[str, pd.DataFrame]:
    building_root = data_root / building_id
    manifest_path = building_root / "manifest.json"
    grid_minutes = 5
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        grid_minutes = int(manifest.get("grid_minutes", 5))
    out: dict[str, pd.DataFrame] = {}
    for eq in discover_equipment(building_root):
        df = load_equipment_csv(eq["history_path"], eq.get("columns_path"))
        df.attrs["poll_seconds"] = grid_minutes * 60.0
        df.attrs["equipment_id"] = eq["equipment_id"]
        df.attrs["columns_path"] = eq.get("columns_path")
        out[eq["equipment_id"]] = df
    return out


def load_uploaded_csv(file: BytesIO | Any) -> pd.DataFrame:
    raw = pd.read_csv(file)
    return normalize_timestamp(raw)


def load_local_folder(folder: Path) -> dict[str, pd.DataFrame]:
    return load_building_tree(folder.parent, folder.name) if (folder / "manifest.json").is_file() else {
        eq["equipment_id"]: load_equipment_csv(eq["history_path"], eq.get("columns_path"))
        for eq in discover_equipment(folder)
    }


def load_sqlite_table(db_path: Path, table: str) -> pd.DataFrame:
    import sqlite3

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        df = pd.read_sql_query(f'SELECT * FROM "{table}"', con)
    finally:
        con.close()
    return normalize_timestamp(df)


def load_duckdb_query(db_path: Path, query: str) -> pd.DataFrame:
    import duckdb

    q = query.strip()
    if not re.match(r"^\s*select\b", q, re.I):
        raise ValueError("Only read-only SELECT queries are allowed")
    if re.search(r"\b(insert|update|delete|drop|create|alter|attach)\b", q, re.I):
        raise ValueError("Destructive SQL is not allowed")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        df = con.execute(q).df()
    finally:
        con.close()
    return normalize_timestamp(df)


def load_parquet(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if not isinstance(df.index, pd.DatetimeIndex):
        df = normalize_timestamp(df)
    return df
