"""Streamlit cache helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from app.config import AppConfig
from app.data_loader import (
    load_building_tree,
    load_duckdb_query,
    load_equipment_csv,
    load_parquet,
    load_sqlite_table,
    load_uploaded_csv,
    normalize_timestamp,
)


@st.cache_data(show_spinner="Loading building CSV tree…")
def cached_building_tree(data_root: str, building_id: str) -> dict[str, pd.DataFrame]:
    return load_building_tree(Path(data_root), building_id)


@st.cache_data(show_spinner="Loading equipment CSV…")
def cached_equipment_csv(history_path: str, columns_path: str | None) -> pd.DataFrame:
    return load_equipment_csv(Path(history_path), Path(columns_path) if columns_path else None)


@st.cache_data
def cached_upload_bytes(name: str, data: bytes) -> pd.DataFrame:
    from io import BytesIO

    return load_uploaded_csv(BytesIO(data))


@st.cache_data
def cached_sqlite(path: str, table: str) -> pd.DataFrame:
    return load_sqlite_table(Path(path), table)


@st.cache_data
def cached_duckdb(path: str, query: str) -> pd.DataFrame:
    return load_duckdb_query(Path(path), query)


@st.cache_data
def cached_parquet(path: str) -> pd.DataFrame:
    return load_parquet(Path(path))


@st.cache_data
def cached_weather(data_root: str, weather_subdir: str) -> pd.DataFrame | None:
    root = Path(data_root) / weather_subdir
    hist = root / "history_wide.csv"
    if not hist.is_file():
        return None
    df = load_equipment_csv(hist, root / "columns.csv" if (root / "columns.csv").is_file() else None)
    if "outside_air_temp_f" in df.columns:
        df = df.rename(columns={"outside_air_temp_f": "wx_oa_t"})
    elif "oa_t" not in df.columns:
        for c in df.columns:
            if "temp" in c.lower():
                df = df.rename(columns={c: "wx_oa_t"})
                break
    return df


def load_rule_defaults(path: Path) -> dict[str, Any]:
    import yaml

    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@st.cache_data
def cached_rule_defaults(path: str) -> dict[str, Any]:
    return load_rule_defaults(Path(path))
