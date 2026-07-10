"""Streamlit RCx / generic multi-equipment plots tab."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from app.charts import multi_equipment_box, multi_equipment_timeseries, oat_scatter, plotly_config
from app.rcx_plots import (
    PRESETS,
    collect_oat_scatter,
    collect_role_series,
    outlier_equipment_ids,
    preset_by_id,
    series_summary_stats,
)
from app.reports import to_csv_bytes
from app.unit_system import convert_series, units_map_for_system


def _convert_map(series_map: dict[str, pd.Series], role: str, system: str) -> tuple[dict[str, pd.Series], str]:
    out: dict[str, pd.Series] = {}
    unit = ""
    for eq_id, s in series_map.items():
        conv, unit = convert_series(role, s, system)  # type: ignore[arg-type]
        out[eq_id] = conv
    return out, unit


def render_rcx_plots_tab(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    weather: pd.DataFrame | None,
    unit_system: str = "imperial",
) -> None:
    st.subheader("RCx & generic plots")
    st.caption(
        "Prebuilt mechanical-category overlays (all zone temps, all AHU DATs, duct-static box, "
        "HW/CHW/CW reset scatters vs web weather) plus a generic role picker. "
        "Outlier equipment (z≥2.5 on mean) highlighted in red dashed / ★."
    )

    mode = st.radio("Mode", ["Prebuilt RCx", "Generic picker"], horizontal=True, key="rcx_mode")
    outlier_z = st.slider("Outlier z-score (mean vs cohort)", 1.5, 4.0, 2.5, 0.1, key="rcx_z")

    series_map: dict[str, pd.Series] = {}
    title = ""
    y_title = ""
    x_title = "Web OAT °F"
    chart_kind = "timeseries"
    long_df = pd.DataFrame()
    role = "zone_t"

    if mode == "Prebuilt RCx":
        labels = {p.id: f"{p.title} — {p.description}" for p in PRESETS}
        pid = st.selectbox("Preset", list(labels.keys()), format_func=lambda k: labels[k], key="rcx_preset")
        preset = preset_by_id(pid)
        assert preset is not None
        role = preset.role
        chart_kind = preset.chart
        title = preset.title
        if chart_kind == "scatter_oat":
            x_pref = "wetbulb" if preset.id == "cw_reset_scatter" else "web"
            long_df = collect_oat_scatter(
                frames,
                role_map,
                y_role=preset.role,
                weather=weather,
                equipment_types=preset.equipment_types,
                x_prefer=x_pref,
            )
            if unit_system == "metric" and not long_df.empty:
                long_df = long_df.copy()
                long_df["y"], y_title = convert_series(role, long_df["y"], "metric")
                long_df["oat"], _xu = convert_series("oa_t", long_df["oat"], "metric")
                x_title = "Web wet-bulb °C" if x_pref == "wetbulb" else "Web OAT °C"
            else:
                y_title = role
                x_title = "Web wet-bulb °F" if x_pref == "wetbulb" else "Web OAT °F"
        else:
            series_map = collect_role_series(
                frames,
                role_map,
                role=preset.role,
                equipment_types=preset.equipment_types,
                filter_fan_on=preset.filter_fan_on,
            )
            series_map, y_title = _convert_map(series_map, role, unit_system)
            if preset.filter_fan_on:
                st.info(
                    "Filtered to **fan proven on**. High, flat duct static while the fan runs "
                    "often means a duct-static-pressure reset would save fan energy — "
                    "compare with motor run-hours on Analytics."
                )
    else:
        role = st.text_input("Cookbook role to plot", value="zone_t", key="rcx_generic_role")
        types = st.multiselect(
            "Equipment types (empty = all)",
            ["AHU", "VAV", "CHW_PLANT", "BOILER", "HP", "WEATHER", "UNKNOWN"],
            default=[],
            key="rcx_types",
        )
        fan_on = st.checkbox("Filter to fan on", value=False, key="rcx_fan_on")
        chart_kind = st.selectbox("Chart", ["timeseries", "box"], key="rcx_chart_kind")
        et = tuple(types) if types else None
        series_map = collect_role_series(
            frames,
            role_map,
            role=role.strip(),
            equipment_types=et,
            filter_fan_on=fan_on,
        )
        series_map, y_title = _convert_map(series_map, role.strip(), unit_system)
        title = f"Generic · {role}"

    stats = series_summary_stats(series_map, outlier_z=outlier_z) if series_map else pd.DataFrame()
    outliers = outlier_equipment_ids(stats)

    if chart_kind == "scatter_oat":
        fig = oat_scatter(
            long_df,
            title=title,
            x_title=x_title,
            y_title=y_title or role,
        )
        if fig is None:
            st.info("No scatter points — map plant temps and ensure weather/web OAT is loaded.")
        else:
            st.plotly_chart(fig, width="stretch", config=plotly_config(filename=f"rcx_{title}"), key="rcx_scatter")
            st.dataframe(long_df.head(5000), hide_index=True, width="stretch", height=220)
    elif chart_kind == "box":
        fig = multi_equipment_box(series_map, title=title, y_title=y_title, outlier_ids=outliers)
        if fig is None:
            st.info("No series for this preset — check role mapping.")
        else:
            st.plotly_chart(fig, width="stretch", config=plotly_config(filename=f"rcx_{title}"), key="rcx_box")
    else:
        fig = multi_equipment_timeseries(series_map, title=title, y_title=y_title, outlier_ids=outliers)
        if fig is None:
            st.info("No series for this preset — check role mapping.")
        else:
            st.plotly_chart(fig, width="stretch", config=plotly_config(filename=f"rcx_{title}"), key="rcx_ts")

    if not stats.empty:
        st.markdown("##### Summary statistics")
        st.dataframe(stats, hide_index=True, width="stretch", height=min(360, 80 + 28 * len(stats)))
        st.download_button(
            "Download summary CSV",
            to_csv_bytes(stats),
            "rcx_summary_stats.csv",
            key="dl_rcx_stats",
        )
