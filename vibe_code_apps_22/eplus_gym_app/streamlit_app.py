"""Lakeside E+ gym — Streamlit + Plotly UI (no live EnergyPlus).

Data-model driven: charts bind to ``SiteUiBundle`` (vibe20 Campus + published
layers). Live month sim stays CLI-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym.month_calendar import DEPLOYABLE_STRATEGIES
from eplus_gym_app.data import (
    available_months,
    load_month_slice,
    mean_daily_profiles,
    month_summary,
)
from eplus_gym_app.idf_geometry import idf_massing_figure, parse_idf_geometry
from eplus_gym_app.load_profiles import (
    closeness_pivot,
    dial_peak_day_overlay,
    find_peak_demand_day,
    load_bas_demand_oat,
    load_closeness_table,
    peak_day_bas_profile,
)
from eplus_gym_app.plots import (
    demand_vs_oat_figure,
    dial_progression_figure,
    facility_overlay_figure,
    kpi_table,
    peak_day_profile_figure,
)
from eplus_gym_app.site_bundle import load_site_ui_bundle


@st.cache_data(show_spinner=False)
def _bundle_cached(site_key: str):
    return load_site_ui_bundle(Path(site_key) if site_key else None)


def _render_farm_tab() -> None:
    months = available_months()
    prefer = [m for m in ("2026-01", "2026-02") if m in months]
    default_ix = months.index(prefer[0]) if prefer else 0
    month = st.selectbox("Month", months, index=default_ix, key="farm_month")
    strategies = st.multiselect(
        "Strategies",
        list(DEPLOYABLE_STRATEGIES),
        default=list(DEPLOYABLE_STRATEGIES),
        key="farm_strats",
    )
    if st.button("Refresh farm cache", key="farm_refresh"):
        st.cache_data.clear()

    if not strategies:
        st.warning("Select at least one strategy.")
        return

    summary = month_summary(month, strategies)
    cov = summary["coverage"]
    present_any = max(
        (int(v.get("n_days") or 0) for v in (cov.get("strategies") or {}).values()),
        default=0,
    )
    n_wanted = int(cov.get("n_calendar_days") or 0)
    c1, c2, c3 = st.columns(3)
    c1.metric("Calendar days in month", n_wanted)
    c2.metric("Max strategy day coverage", present_any)
    c3.metric("Honesty", summary["honesty"])

    st.subheader("KPIs (farm days present)")
    kpis = kpi_table(summary["kpis"])
    if kpis.empty:
        st.info("No KPI rows — farm parquet has no days for this month/strategy yet.")
    else:
        st.dataframe(kpis, width="stretch")

    st.subheader("Mean daily facility kW")
    df = load_month_slice(month, strategies)
    profiles = mean_daily_profiles(df)
    fig = facility_overlay_figure(profiles, month=month)
    st.plotly_chart(fig, width="stretch")

    with st.expander("Coverage detail"):
        st.json(cov)
    st.caption(
        f"provenance={summary['provenance']} · promote={summary['promote']} · "
        "Live month sim is CLI-only: scripts/run_eplus_gym_month_live.py"
    )


def _render_load_profiles_tab(bundle) -> None:
    st.caption(
        f"Campus **{bundle.campus.label}** (`{bundle.campus.campus_id}`) · "
        f"BAS={bundle.honesty.get('bas')} · dial={bundle.honesty.get('dial_ladder')} · "
        f"promote={bundle.promote}"
    )
    if bundle.warnings:
        with st.expander("Bundle warnings"):
            for w in bundle.warnings:
                st.write(f"- {w}")

    bas = load_bas_demand_oat(bundle)
    peak_day = bundle.dial_ladder.peak_day
    if peak_day not in set(bas["local_day"].astype(str)):
        peak_day, peak_kw_auto, _ = find_peak_demand_day(bas)
    else:
        peak_kw_auto = float(
            bas.loc[bas["local_day"] == peak_day, "kw_avg"].max()
        )

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            demand_vs_oat_figure(bas, peak_day=peak_day),
            width="stretch",
        )
    with c2:
        day_prof = peak_day_bas_profile(bas, peak_day)
        st.plotly_chart(
            peak_day_profile_figure(day_prof, day=peak_day, peak_kw=peak_kw_auto),
            width="stretch",
        )

    st.subheader("Weekday / weekend closeness % (Actual vs dial models)")
    closeness = load_closeness_table(bundle)
    if closeness.empty:
        st.info(
            "No precomputed closeness CSV on the site UI bundle. "
            "Publish winter_shape_closeness_*.csv or compute offline."
        )
    else:
        left, right = st.columns(2)
        with left:
            st.markdown("**Weekday closeness %**")
            st.dataframe(
                closeness_pivot(closeness, day_type="weekday").round(1),
                width="stretch",
            )
        with right:
            st.markdown("**Weekend closeness %**")
            st.dataframe(
                closeness_pivot(closeness, day_type="weekend").round(1),
                width="stretch",
            )
        st.caption(
            "closeness% = max(0, 100 − |sim−obs|/obs×100) · segments from archived "
            "GL14 dial ladder · not field savings"
        )

    st.subheader("Peak day — dial progression (Actual vs E+)")
    with st.spinner("Loading dial sim profiles for peak day…"):
        overlay = dial_peak_day_overlay(bundle)
    st.plotly_chart(dial_progression_figure(overlay), width="stretch")
    st.caption(
        f"day={overlay['day']} · utility={overlay['utility_peak_kw']} kW · "
        f"series={list(overlay['series'])} · honesty={overlay['honesty']}"
    )


def _render_building_tab(bundle) -> None:
    st.caption(
        f"Massing honesty={bundle.honesty.get('massing', 'PUBLISHED_IDF_GEOMETRY')} · "
        "geometry from published IDF pin (not site CAD)"
    )
    if bundle.idf_path is None:
        st.warning("No IDF pin resolved on SiteUiBundle.")
        return
    geom = parse_idf_geometry(bundle.idf_path)
    fig = idf_massing_figure(
        geom,
        title=f"{bundle.campus.label} · {bundle.idf_path.name}",
    )
    st.plotly_chart(fig, width="stretch")
    st.json(geom.summary())


def main() -> None:
    st.set_page_config(page_title="Lakeside E+ gym", layout="wide")
    st.title("Lakeside E+ gym")
    st.caption(
        "Data-model driven (vibe20 Campus + site_ui_bundle_v1). "
        "Farm IdealLoads ≠ W2A dial ≠ BAS meter truth."
    )

    try:
        from lakeside.paths import site_root

        site_key = str(site_root())
    except Exception as exc:  # noqa: BLE001
        st.error(f"Site root not set: {exc}")
        return

    try:
        bundle = _bundle_cached(site_key)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load SiteUiBundle: {exc}")
        return

    tab_farm, tab_load, tab_bldg = st.tabs(
        ["IdealLoads farm month", "Load profiles (Actual vs E+)", "Building massing"]
    )
    with tab_farm:
        _render_farm_tab()
    with tab_load:
        _render_load_profiles_tab(bundle)
    with tab_bldg:
        _render_building_tab(bundle)


if __name__ == "__main__":
    main()
