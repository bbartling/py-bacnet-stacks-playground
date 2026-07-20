"""Dump Data Explorer — browse measured WattLab dump tables / telemetry."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

# Prefer common engineering tables first; remaining tables appear alphabetically.
_PREFERRED = (
    "fdd_findings",
    "fdd_summary",
    "operating_signatures",
    "schedule_inference_table",
    "setpoints",
    "mech_cooling_oat_bins",
    "mech_cooling_coverage",
    "weather_observed",
    "utility_bills",
    "sensor_stats_all",
    "sensor_stats_fan_on",
    "sensor_stats_fan_off",
    "sensor_diurnal_24h",
    "motor_hours",
    "motor_weekly",
    "economizer_weather",
    "rcx_preset_coverage",
    "rcx_zone_comfort_ranking",
    "role_map_gap_report",
    "data_model",
    "sensor_health_matrix",
    "sensor_fault_summary",
)

_MAX_PREVIEW_ROWS = 500


def _ordered_tables(bundle: Any) -> list[str]:
    names = list((getattr(bundle, "tables", None) or {}).keys())
    preferred = [n for n in _PREFERRED if n in names]
    rest = sorted(n for n in names if n not in preferred)
    return preferred + rest


def render(*, bundle: Any = None) -> None:
    st.header("Data Explorer — measured dump evidence")
    st.caption(
        "Browse tables and shared telemetry from the loaded vibe19 WattLab dump. "
        "This is **measured / derived evidence**, not EnergyPlus simulation output."
    )

    if bundle is None:
        st.info("Load a WattLab dump on the Ingest page first.")
        return

    summary = bundle.summary() if hasattr(bundle, "summary") else {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Building", str(summary.get("building_id") or getattr(bundle, "building_id", "?") or "?"))
    c2.metric("Schema", str(summary.get("schema_version") or getattr(bundle, "schema_version", "") or "—"))
    c3.metric("Tables", str(len(summary.get("tables") or getattr(bundle, "tables", {}) or {})))
    c4.metric(
        "Telemetry files",
        str(summary.get("telemetry_file_count") or len(getattr(bundle, "telemetry_paths", {}) or {})),
    )

    mode = st.radio(
        "Browse",
        ["Analytic tables", "Telemetry"],
        horizontal=True,
        key="data_explorer_mode",
    )

    if mode == "Telemetry":
        paths = dict(getattr(bundle, "telemetry_paths", {}) or {})
        if not paths:
            st.warning(
                "No shared `telemetry/` files in this dump "
                "(summary/v3 dumps may omit them, or this is a v2 layout)."
            )
            return
        equip = st.selectbox(
            "Equipment telemetry CSV",
            sorted(paths.keys()),
            key="data_explorer_telemetry_equip",
        )
        df = bundle.load_telemetry(equip) if hasattr(bundle, "load_telemetry") else pd.DataFrame()
        st.caption(f"{equip}: {len(df):,} rows (preview capped at {_MAX_PREVIEW_ROWS})")
        if df.empty:
            st.warning("Could not read that telemetry file.")
            return
        st.dataframe(df.head(_MAX_PREVIEW_ROWS), width="stretch", hide_index=True)
        return

    tables = _ordered_tables(bundle)
    if not tables:
        st.warning("Dump has no analytic tables loaded.")
        return

    name = st.selectbox("Table", tables, key="data_explorer_table")
    df = bundle.table(name) if hasattr(bundle, "table") else pd.DataFrame()
    st.caption(f"{name}: {len(df):,} rows (preview capped at {_MAX_PREVIEW_ROWS})")
    if df.empty:
        st.info("Selected table is empty.")
        return
    st.dataframe(df.head(_MAX_PREVIEW_ROWS), width="stretch", hide_index=True)
