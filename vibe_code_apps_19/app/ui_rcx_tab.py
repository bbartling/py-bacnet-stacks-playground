"""Streamlit RCx / generic multi-equipment plots tab."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.charts import multi_equipment_box, multi_equipment_timeseries, oat_scatter, plotly_config
from app.rcx_plots import (
    PRESETS,
    cohort_wants_fan_slices,
    collect_oat_scatter,
    collect_role_series,
    fan_mode_summary_bundle,
    outlier_equipment_ids,
    preset_by_id,
    series_summary_stats,
)
from app.reports import to_csv_bytes
from app.unit_system import convert_series


def _convert_map(series_map: dict[str, pd.Series], role: str, system: str) -> tuple[dict[str, pd.Series], str]:
    out: dict[str, pd.Series] = {}
    unit = ""
    for eq_id, s in series_map.items():
        conv, unit = convert_series(role, s, system)  # type: ignore[arg-type]
        out[eq_id] = conv
    return out, unit


def _render_summary_stats(
    *,
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    role: str,
    equipment_types: tuple[str, ...] | None,
    chart_series_map: dict[str, pd.Series],
    outlier_z: float,
    unit_system: str,
    key_prefix: str,
) -> None:
    """Summary tables: All / operating on / off for air-side cohorts when proof exists."""
    chart_stats = (
        series_summary_stats(chart_series_map, outlier_z=outlier_z) if chart_series_map else pd.DataFrame()
    )
    if chart_stats.empty and not cohort_wants_fan_slices(equipment_types):
        return

    st.markdown("##### Summary statistics")
    if not cohort_wants_fan_slices(equipment_types):
        if chart_stats.empty:
            return
        st.dataframe(chart_stats, hide_index=True, width="stretch", height=min(360, 80 + 28 * len(chart_stats)))
        st.download_button(
            "Download summary CSV",
            to_csv_bytes(chart_stats),
            "rcx_summary_stats.csv",
            key=f"{key_prefix}_dl_stats",
        )
        return

    _tables, proof_cap = fan_mode_summary_bundle(
        frames,
        role_map,
        role=role,
        equipment_types=equipment_types,
        outlier_z=outlier_z,
    )
    display_tables: dict[str, pd.DataFrame] = {}
    for mode_key in ("all", "on", "off"):
        sm = collect_role_series(
            frames, role_map, role=role, equipment_types=equipment_types, fan_mode=mode_key
        )
        sm, _ = _convert_map(sm, role, unit_system)
        display_tables[mode_key] = series_summary_stats(sm, outlier_z=outlier_z)

    st.caption(proof_cap)
    tab_all, tab_on, tab_off = st.tabs(["All data", "Fan / air on", "Fan / air off"])
    labels = {
        "all": ("All timestamps", tab_all),
        "on": ("Operating (fan proven on or VAV airflow active)", tab_on),
        "off": ("Off / inactive periods", tab_off),
    }
    for mode_key, (blurb, tab) in labels.items():
        with tab:
            st.caption(blurb)
            stats = display_tables.get(mode_key, pd.DataFrame())
            if stats.empty:
                st.info("No rows for this slice — check mapping or operating proof.")
            else:
                n_out = int(stats["outlier"].sum()) if "outlier" in stats.columns else 0
                st.caption(f"{len(stats)} equipment · {n_out} outlier(s) at z≥{outlier_z:g}")
                st.dataframe(
                    stats, hide_index=True, width="stretch", height=min(360, 80 + 28 * len(stats))
                )
                st.download_button(
                    f"Download {mode_key} summary CSV",
                    to_csv_bytes(stats),
                    f"rcx_summary_stats_{mode_key}.csv",
                    key=f"{key_prefix}_dl_stats_{mode_key}",
                )


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
        "Outlier equipment (z≥2.5 on mean) highlighted in red dashed / ★. "
        "AHU / VAV summary stats include All / fan-on / fan-off slices when proof is mapped."
    )

    from app.rcx_plots import rcx_preset_coverage

    with st.expander("RCx preset coverage diagnostics", expanded=False):
        cov = rcx_preset_coverage(frames, role_map, weather=weather)
        st.dataframe(cov, hide_index=True, width="stretch", height=320)
        nonempty = int((cov["row_count"] > 0).sum()) if not cov.empty else 0
        st.caption(f"{nonempty}/{len(cov)} presets have data")
        st.download_button(
            "Download rcx_preset_coverage.csv",
            to_csv_bytes(cov),
            "rcx_preset_coverage.csv",
            key="dl_rcx_coverage",
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
    equipment_types: tuple[str, ...] | None = None

    if mode == "Prebuilt RCx":
        labels = {p.id: f"{p.title} — {p.description}" for p in PRESETS}
        pid = st.selectbox("Preset", list(labels.keys()), format_func=lambda k: labels[k], key="rcx_preset")
        preset = preset_by_id(pid)
        assert preset is not None
        role = preset.role
        chart_kind = preset.chart
        title = preset.title
        equipment_types = preset.equipment_types
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
        fan_on = st.checkbox("Filter chart to fan on", value=False, key="rcx_fan_on")
        chart_kind = st.selectbox("Chart", ["timeseries", "box"], key="rcx_chart_kind")
        equipment_types = tuple(types) if types else None
        series_map = collect_role_series(
            frames,
            role_map,
            role=role.strip(),
            equipment_types=equipment_types,
            filter_fan_on=fan_on,
        )
        series_map, y_title = _convert_map(series_map, role.strip(), unit_system)
        title = f"Generic · {role}"
        role = role.strip()

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
        if not stats.empty:
            st.markdown("##### Summary statistics")
            st.caption("Scatter presets use all timestamps (no fan slice).")
            st.dataframe(stats, hide_index=True, width="stretch", height=min(360, 80 + 28 * len(stats)))
    elif chart_kind == "box":
        fig = multi_equipment_box(series_map, title=title, y_title=y_title, outlier_ids=outliers)
        if fig is None:
            st.info("No series for this preset — check role mapping.")
        else:
            st.plotly_chart(fig, width="stretch", config=plotly_config(filename=f"rcx_{title}"), key="rcx_box")
        _render_summary_stats(
            frames=frames,
            role_map=role_map,
            role=role,
            equipment_types=equipment_types,
            chart_series_map=series_map,
            outlier_z=outlier_z,
            unit_system=unit_system,
            key_prefix=f"rcx_{mode}_{role}",
        )
    else:
        fig = multi_equipment_timeseries(series_map, title=title, y_title=y_title, outlier_ids=outliers)
        if fig is None:
            st.info("No series for this preset — check role mapping.")
        else:
            st.plotly_chart(fig, width="stretch", config=plotly_config(filename=f"rcx_{title}"), key="rcx_ts")
        _render_summary_stats(
            frames=frames,
            role_map=role_map,
            role=role,
            equipment_types=equipment_types,
            chart_series_map=series_map,
            outlier_z=outlier_z,
            unit_system=unit_system,
            key_prefix=f"rcx_{mode}_{role}",
        )
