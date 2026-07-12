"""Streamlit RCx / generic multi-equipment plots tab."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.charts import multi_equipment_box, multi_equipment_timeseries, oat_scatter, plotly_config
from app.occupancy import OccupancySchedule
from app.rcx_plots import (
    PRESETS,
    cohort_wants_fan_slices,
    collect_oat_scatter,
    collect_role_series,
    fan_mode_summary_bundle,
    outlier_equipment_ids,
    preset_by_id,
    series_summary_stats,
    zone_comfort_fail_ranking,
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
    occupancy_schedule: dict | OccupancySchedule | None = None,
    zone_lo_f: float = 70.0,
    zone_hi_f: float = 75.0,
) -> None:
    st.subheader("RCx plots")
    st.caption(
        "Data-model-driven presets (chart type in the name). "
        "Zone comfort ranking uses Overview occupancy calendar + zone low/high. "
        "Outliers (z≥2.5) highlighted. AHU/VAV summaries include All / fan-on / fan-off when proof is mapped."
    )

    from app.rcx_plots import rcx_preset_coverage

    schedule = (
        occupancy_schedule
        if isinstance(occupancy_schedule, OccupancySchedule)
        else OccupancySchedule.from_dict(occupancy_schedule)
    )
    outlier_z = st.slider("Outlier z-score (mean vs cohort)", 1.5, 4.0, 2.5, 0.1, key="rcx_z")

    with st.expander("RCx preset coverage diagnostics", expanded=False):
        cov = rcx_preset_coverage(
            frames,
            role_map,
            weather=weather,
            outlier_z=outlier_z,
            schedule=schedule,
            comfort_low_f=zone_lo_f,
            comfort_high_f=zone_hi_f,
        )
        st.dataframe(cov, hide_index=True, width="stretch", height=320)
        nonempty = int((cov["row_count"] > 0).sum()) if not cov.empty else 0
        st.caption(f"{nonempty}/{len(cov)} presets have data")
        st.download_button(
            "Download rcx_preset_coverage.csv",
            to_csv_bytes(cov),
            "rcx_preset_coverage.csv",
            key="dl_rcx_coverage",
        )

    # Prefer presets with data; still list empties at the bottom with a marker
    cov_by_id = {}
    if not cov.empty:
        cov_by_id = {str(r.preset_id): r for r in cov.itertuples()}
    ordered = sorted(
        PRESETS,
        key=lambda p: (
            0 if (cov_by_id.get(p.id) and int(getattr(cov_by_id[p.id], "row_count", 0) or 0) > 0) else 1,
            PRESETS.index(p),
        ),
    )

    def _label(pid: str) -> str:
        p = preset_by_id(pid)
        title = p.title if p else pid
        row = cov_by_id.get(pid)
        if row is not None and int(getattr(row, "row_count", 0) or 0) == 0:
            return f"{title}  ·  (no data)"
        return title

    pid = st.selectbox(
        "Plot",
        [p.id for p in ordered],
        format_func=_label,
        key="rcx_preset",
    )
    preset = preset_by_id(pid)
    assert preset is not None
    st.caption(preset.description)

    role = preset.role
    chart_kind = preset.chart
    title = preset.title
    equipment_types = preset.equipment_types
    series_map: dict[str, pd.Series] = {}
    long_df = pd.DataFrame()
    y_title = ""
    x_title = "Web OAT °F"

    if chart_kind == "ranking":
        rank = zone_comfort_fail_ranking(
            frames,
            role_map,
            schedule=schedule,
            comfort_low_f=zone_lo_f,
            comfort_high_f=zone_hi_f,
            equipment_types=equipment_types,
            outlier_z=outlier_z,
        )
        st.markdown("##### Zone comfort fail ranking")
        st.caption(
            f"Occupied hours only (Overview schedule). Band **{zone_lo_f:g}–{zone_hi_f:g} °F** "
            f"(same as VAV-1 / SCHED-1). Worst % outside first."
        )
        if rank.empty:
            st.info("No VAV `zone_t` samples during occupied hours — check mapping and schedule.")
        else:
            n_out = int(rank["outlier"].sum()) if "outlier" in rank.columns else 0
            st.caption(f"{len(rank)} zones · {n_out} outlier(s) by fail-% vs cohort")
            st.dataframe(rank, hide_index=True, width="stretch", height=min(480, 80 + 28 * len(rank)))
            st.download_button(
                "Download zone comfort ranking CSV",
                to_csv_bytes(rank),
                "rcx_zone_comfort_ranking.csv",
                key="dl_rcx_zone_rank",
            )
            # Overlay worst offenders' zone temps for visual follow-up
            worst_ids = list(rank["equipment_id"].astype(str).head(12))
            series_map = collect_role_series(
                frames,
                role_map,
                role="zone_t",
                equipment_types=equipment_types,
                equipment_ids=worst_ids,
            )
            series_map, y_title = _convert_map(series_map, "zone_t", unit_system)
            outliers = (
                set(rank.loc[rank["outlier"], "equipment_id"].astype(str))
                if "outlier" in rank.columns
                else set()
            )
            fig = multi_equipment_timeseries(
                series_map,
                title=f"Worst zones — space temp (top {len(worst_ids)})",
                y_title=y_title or "zone_t",
                outlier_ids=outliers,
            )
            if fig is not None:
                st.plotly_chart(
                    fig,
                    width="stretch",
                    config=plotly_config(filename="rcx_zone_comfort_worst"),
                    key="rcx_zone_rank_ts",
                )
        return

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
            if "dry_bulb" in long_df.columns:
                long_df["dry_bulb"], _ = convert_series("oa_t", long_df["dry_bulb"], "metric")
            x_title = "Web wet-bulb °C" if x_pref == "wetbulb" else "Web OAT °C"
        else:
            y_title = role
            x_title = "Web wet-bulb °F" if x_pref == "wetbulb" else "Web OAT °F"
            if preset.dry_bulb_ref:
                x_title = "Wet-bulb °F (markers) · dry-bulb ref (×)"

        fig = oat_scatter(
            long_df,
            title=title,
            x_title=x_title,
            y_title=y_title or role,
            dry_bulb_ref=bool(preset.dry_bulb_ref),
        )
        if fig is None:
            st.info("No scatter points — map plant leave temps and ensure weather/web OAT is loaded.")
        else:
            if preset.dry_bulb_ref:
                st.caption("Primary X = wet-bulb; × markers = same Y vs dry-bulb (approach reference).")
            st.plotly_chart(fig, width="stretch", config=plotly_config(filename=f"rcx_{preset.id}"), key="rcx_scatter")
            st.dataframe(long_df.head(5000), hide_index=True, width="stretch", height=220)
        return

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
            "compare with motor run-hours on Overview."
        )

    stats = series_summary_stats(series_map, outlier_z=outlier_z) if series_map else pd.DataFrame()
    outliers = outlier_equipment_ids(stats)

    if chart_kind == "box":
        fig = multi_equipment_box(series_map, title=title, y_title=y_title, outlier_ids=outliers)
        key = "rcx_box"
    else:
        fig = multi_equipment_timeseries(series_map, title=title, y_title=y_title, outlier_ids=outliers)
        key = "rcx_ts"
    if fig is None:
        st.info("No series for this preset — check role mapping / Data Model.")
    else:
        st.plotly_chart(fig, width="stretch", config=plotly_config(filename=f"rcx_{preset.id}"), key=key)

    _render_summary_stats(
        frames=frames,
        role_map=role_map,
        role=role,
        equipment_types=equipment_types,
        chart_series_map=series_map,
        outlier_z=outlier_z,
        unit_system=unit_system,
        key_prefix=f"rcx_{preset.id}",
    )

    with st.expander("Generic role picker (advanced)", expanded=False):
        g_role = st.text_input("Cookbook role to plot", value="zone_t", key="rcx_generic_role")
        g_types = st.multiselect(
            "Equipment types (empty = all)",
            ["AHU", "VAV", "CHW_PLANT", "CHILLER", "BOILER", "HP", "COOLING_TOWER", "WEATHER", "UNKNOWN"],
            default=[],
            key="rcx_types",
        )
        g_fan = st.checkbox("Filter chart to fan on", value=False, key="rcx_fan_on")
        g_kind = st.selectbox("Chart", ["timeseries", "box"], key="rcx_chart_kind")
        g_et = tuple(g_types) if g_types else None
        g_map = collect_role_series(
            frames,
            role_map,
            role=g_role.strip(),
            equipment_types=g_et,
            filter_fan_on=g_fan,
        )
        g_map, g_yt = _convert_map(g_map, g_role.strip(), unit_system)
        g_stats = series_summary_stats(g_map, outlier_z=outlier_z) if g_map else pd.DataFrame()
        g_out = outlier_equipment_ids(g_stats)
        if g_kind == "box":
            g_fig = multi_equipment_box(g_map, title=f"Generic · {g_role}", y_title=g_yt, outlier_ids=g_out)
        else:
            g_fig = multi_equipment_timeseries(
                g_map, title=f"Generic · {g_role}", y_title=g_yt, outlier_ids=g_out
            )
        if g_fig is None:
            st.info("No series for that role / type filter.")
        else:
            st.plotly_chart(g_fig, width="stretch", config=plotly_config(filename="rcx_generic"), key="rcx_generic_fig")
        if not g_stats.empty:
            st.dataframe(g_stats, hide_index=True, width="stretch", height=min(280, 80 + 28 * len(g_stats)))
