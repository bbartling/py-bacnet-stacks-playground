"""Lakeside E+ gym — Streamlit viewer (picker data only; no live EnergyPlus).

Agents publish IDF / campus.json / bill CSVs / interval CSVs / scorecards.
This app only **picks** those paths and renders charts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym.month_calendar import DEPLOYABLE_STRATEGIES
from eplus_gym_app.campus_fuel import Campus
from eplus_gym_app.data import (
    available_months,
    load_month_slice,
    mean_daily_profiles,
    month_summary,
)
from eplus_gym_app.geom_tables import envelope_table, knobs_table, zones_table
from eplus_gym_app.idf_geometry import idf_massing_figure, parse_idf_geometry
from eplus_gym_app.load_profiles import (
    closeness_pivot,
    dial_peak_day_overlay,
    find_peak_demand_day,
    load_bas_demand_oat,
    load_closeness_table,
    peak_day_bas_profile,
)
from eplus_gym_app.period_explorer import PERIOD_PRESETS, period_overlay
from eplus_gym_app.pickers import (
    list_bill_csvs_near,
    list_campus_jsons,
    list_idf_pins,
    list_interval_csvs,
    resolve_idf,
)
from eplus_gym_app.plots import (
    demand_vs_oat_figure,
    dial_progression_figure,
    facility_overlay_figure,
    fuel_monthly_figure,
    kpi_table,
    peak_day_profile_figure,
    period_overlay_figure,
)
from eplus_gym_app.site_bundle import (
    ModelCatalogEntry,
    SiteUiBundle,
    catalog_gl14_table,
    load_site_ui_bundle,
)


@st.cache_data(show_spinner=False)
def _bundle_cached(site_key: str):
    return load_site_ui_bundle(Path(site_key) if site_key else None)


@st.cache_data(show_spinner=False)
def _campus_cached(path_str: str):
    return Campus.from_json(path_str)


def _fmt_pct(x: float | None) -> str:
    if x is None or x != x:
        return "—"
    return f"{x:+.1f}%"


def _fmt_kw(x: float | None) -> str:
    if x is None or x != x:
        return "—"
    return f"{x:.0f}"


def _render_sidebar_pickers(bundle: SiteUiBundle, site: Path) -> dict:
    """IDF + campus + interval CSV pickers — sole data inputs for the UI."""
    st.sidebar.header("Published data pickers")
    st.sidebar.caption(
        "Viewer only — no EnergyPlus. Agents publish IDF / campus / CSVs; you pick."
    )

    # --- IDF / catalog model ---
    catalog_ids = [m.id for m in bundle.model_catalog]
    idf_names = list_idf_pins(site)
    st.sidebar.subheader("IDF / model")
    source = st.sidebar.radio(
        "IDF source",
        ["Catalog model", "IDF file"],
        horizontal=True,
        key="idf_source",
    )
    active: ModelCatalogEntry | None = None
    idf_path: Path | None = None
    idf_label = ""

    if source == "Catalog model" and catalog_ids:
        labels = {m.id: m.dropdown_label() for m in bundle.model_catalog}
        default = (
            bundle.default_model_id
            if bundle.default_model_id in catalog_ids
            else catalog_ids[0]
        )
        if st.session_state.get("active_model_id") not in catalog_ids:
            st.session_state["active_model_id"] = default
        mid = st.sidebar.selectbox(
            "Catalog model",
            catalog_ids,
            format_func=lambda i: labels.get(i, i),
            key="active_model_id",
        )
        active = bundle.get_model(mid)
        idf_path = active.idf_path if active else None
        idf_label = active.idf_pin if active else ""
    else:
        default_idf = bundle.idf_path.name if bundle.idf_path else (
            idf_names[0] if idf_names else ""
        )
        if not idf_names:
            st.sidebar.error("No .idf files under site eplus/models or repo models/eplus")
        else:
            ix = idf_names.index(default_idf) if default_idf in idf_names else 0
            pick = st.sidebar.selectbox("IDF file", idf_names, index=ix, key="idf_file_pick")
            idf_path = resolve_idf(pick)
            idf_label = pick
            # Match catalog entry if same pin
            for m in bundle.model_catalog:
                if m.idf_pin == pick:
                    active = m
                    st.session_state["active_model_id"] = m.id
                    break

    # --- Campus / fuel ---
    st.sidebar.subheader("Fuel (vibe20 campus)")
    campuses = list_campus_jsons(site)
    campus_labels = {
        str(p): f"{p.parent.name}/{p.name}" for p in campuses
    }
    default_campus = bundle.campus.source if hasattr(bundle.campus, "source") else None
    # CampusRef has source Path
    default_campus = str(getattr(bundle.campus, "source", "") or "")
    campus_opts = [str(p) for p in campuses]
    if default_campus and default_campus not in campus_opts and Path(default_campus).is_file():
        campus_opts = [default_campus] + campus_opts
    if not campus_opts:
        st.sidebar.warning("No campus*.json under utilities/ or uploads/")
        campus_path = None
    else:
        cix = campus_opts.index(default_campus) if default_campus in campus_opts else 0
        campus_sel = st.sidebar.selectbox(
            "campus.json",
            campus_opts,
            index=cix,
            format_func=lambda s: campus_labels.get(s, Path(s).name),
            key="campus_json_pick",
        )
        campus_path = Path(campus_sel)

    # --- Interval / Actual ---
    st.sidebar.subheader("Actual / interval CSV")
    intervals = list_interval_csvs(site)
    # Prefer bundle bas path first
    bas_default = str(bundle.bas_demand_oat_csv)
    int_opts = [str(p) for p in intervals]
    if bas_default not in int_opts and Path(bas_default).is_file():
        int_opts = [bas_default] + int_opts
    if not int_opts:
        st.sidebar.warning("No demand/interval CSVs found")
        bas_path = bundle.bas_demand_oat_csv
    else:
        bix = int_opts.index(bas_default) if bas_default in int_opts else 0
        bas_sel = st.sidebar.selectbox(
            "Demand / interval CSV",
            int_opts,
            index=bix,
            format_func=lambda s: Path(s).name,
            key="bas_csv_pick",
        )
        bas_path = Path(bas_sel)

    st.sidebar.divider()
    st.sidebar.caption(
        f"promote=False · site=`{site.name}` · "
        "GL14 / dial sims stay agent-published on the bundle"
    )
    return {
        "active": active,
        "idf_path": idf_path,
        "idf_label": idf_label,
        "campus_path": campus_path,
        "bas_path": bas_path,
    }


def _render_overview_metrics(active: ModelCatalogEntry | None, idf_label: str) -> None:
    st.caption(
        "Picker-driven viewer (vibe20 Campus + site_ui_bundle). "
        "No live EnergyPlus in this app · promote=False"
    )
    if active is None:
        st.info(f"IDF file **{idf_label}** (no catalog scorecard) — massing only.")
        return
    met = active.metrics
    gl14_label = (
        "PASS"
        if met and met.gl14_pass is True
        else ("FAIL" if met and met.gl14_pass is False else "—")
    )
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Active IDF", idf_label.replace("lakeside_", "").replace(".idf", "")[:32])
    c2.metric("Scorecard peak kW", _fmt_kw(met.peak_kw if met else None))
    c3.metric("NMBE", _fmt_pct(met.nmbe_pct if met else None))
    c4.metric("CVRMSE", _fmt_pct(met.cvrmse_pct if met else None))
    c5.metric("GL14", gl14_label)
    c6.metric("Family", active.family.replace("_", " ")[:22])
    if met and met.role:
        st.caption(met.role)


def _render_fuel_tab(campus_path: Path | None) -> None:
    st.subheader("Fuel records (vibe20 Campus)")
    if campus_path is None or not campus_path.is_file():
        st.warning("Pick a campus.json in the sidebar.")
        return
    try:
        campus = _campus_cached(str(campus_path))
    except Exception as exc:  # noqa: BLE001
        st.error(f"Campus load failed: {exc}")
        return
    st.caption(
        f"**{campus.label}** (`{campus.campus_id}`) · "
        f"buildings={len(campus.buildings)} · meters={len(campus.meters)} · "
        f"source=`{campus_path}`"
    )
    bills = list_bill_csvs_near(campus_path)
    st.write("Bill CSVs next to campus:", ", ".join(p.name for p in bills) or "—")

    elec = campus.electric_monthly()
    eui = campus.site_eui_kbtu_ft2()
    m1, m2, m3 = st.columns(3)
    m1.metric("Electric meters", sum(1 for m in campus.meters if m.fuel == "electricity"))
    m2.metric("Months", int(elec["month"].nunique()) if not elec.empty else 0)
    m3.metric("Site EUI (kBtu/ft²)", f"{eui:.1f}" if eui is not None else "—")
    st.plotly_chart(
        fuel_monthly_figure(elec, title=f"{campus.label} · monthly electric"),
        width="stretch",
    )
    if not elec.empty:
        st.dataframe(elec, width="stretch", hide_index=True)


def _render_period_tab(
    bundle: SiteUiBundle,
    active: ModelCatalogEntry | None,
    bas_path: Path,
) -> None:
    st.subheader("Period explorer (Actual vs selected model)")
    st.caption("Series from **picked** interval CSV + catalog dial sim_dir only.")

    c_a, c_b = st.columns([2, 1])
    with c_a:
        preset = st.select_slider(
            "Period",
            options=list(PERIOD_PRESETS),
            value="Peak day",
            key="period_preset",
        )
    with c_b:
        try:
            bas = load_bas_demand_oat(bundle, csv_path=bas_path)
            bas_months = sorted({str(d)[:7] for d in bas["local_day"].astype(str)})
        except Exception as exc:  # noqa: BLE001
            st.error(f"Interval CSV failed: {exc}")
            return
        months = available_months()
        month_opts = sorted(set(months) | set(bas_months))
        default_m = (
            bundle.dial_ladder.peak_day[:7]
            if bundle.dial_ladder.peak_day[:7] in month_opts
            else (month_opts[0] if month_opts else "2026-01")
        )
        month = st.selectbox(
            "Month (for Calendar month)",
            month_opts or ["2026-01"],
            index=(month_opts.index(default_m) if default_m in month_opts else 0),
            key="period_month",
            disabled=preset != "Calendar month",
        )

    with st.spinner("Building period overlay…"):
        overlay = period_overlay(
            bundle,
            active,
            preset=preset,
            month=month if preset == "Calendar month" else None,
            bas_csv=bas_path,
        )

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Days in window", overlay["n_days"])
    k2.metric("Actual peak kW", _fmt_kw(overlay["actual_peak_kw"]))
    k3.metric(
        f"{overlay.get('sim_id') or 'Sim'} peak kW",
        _fmt_kw(overlay["sim_peak_kw"]),
    )
    k4.metric("Sim vs Actual", _fmt_pct(overlay.get("pct_vs_actual")))
    k5.metric("Utility kW", _fmt_kw(overlay["utility_peak_kw"]))

    if overlay.get("sim") is None or (
        hasattr(overlay.get("sim"), "empty") and overlay["sim"].empty
    ):
        st.info(
            "No dial sim for this IDF pick — choose catalog **A04** (or E20) "
            "with a published sim_dir on the bundle."
        )

    st.plotly_chart(period_overlay_figure(overlay), width="stretch")
    st.caption(
        f"bas=`{bas_path.name}` · model={overlay.get('model_id')} · "
        f"sim={overlay.get('sim_id')} · promote={overlay['promote']}"
    )


def _render_farm_diagnostic_tab() -> None:
    st.error(
        "DIAGNOSTIC ONLY — IdealLoads DR farm. Peaks here are **not** the picked "
        "A04 / fuel campus. Prefer Period explorer + Fuel tabs."
    )
    months = available_months()
    prefer = [m for m in ("2026-01", "2026-02") if m in months]
    default_ix = months.index(prefer[0]) if prefer else 0
    month = st.selectbox("Farm month", months, index=default_ix, key="farm_month")
    strategies = st.multiselect(
        "IdealLoads strategies",
        list(DEPLOYABLE_STRATEGIES),
        default=list(DEPLOYABLE_STRATEGIES),
        key="farm_strats",
    )
    if not strategies:
        return
    summary = month_summary(month, strategies)
    kpis = kpi_table(summary["kpis"])
    if not kpis.empty:
        st.dataframe(
            kpis.rename(
                columns={
                    "strategy_id": "idealLoads_strategy",
                    "peak_kw": "idealLoads_peak_kw",
                }
            ),
            width="stretch",
        )
    df = load_month_slice(month, strategies)
    st.plotly_chart(
        facility_overlay_figure(mean_daily_profiles(df), month=month),
        width="stretch",
    )


def _render_load_profiles_tab(
    bundle: SiteUiBundle,
    active: ModelCatalogEntry | None,
    bas_path: Path,
) -> None:
    st.caption("GL14 scorecards + closeness from **published** bundle artifacts.")
    gl14_rows = catalog_gl14_table(bundle)
    if gl14_rows:
        st.dataframe(pd.DataFrame(gl14_rows), width="stretch")

    try:
        bas = load_bas_demand_oat(bundle, csv_path=bas_path)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Interval CSV failed: {exc}")
        return
    peak_day = bundle.dial_ladder.peak_day
    if peak_day not in set(bas["local_day"].astype(str)):
        peak_day, peak_kw_auto, _ = find_peak_demand_day(bas)
    else:
        peak_kw_auto = float(bas.loc[bas["local_day"] == peak_day, "kw_avg"].max())

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(demand_vs_oat_figure(bas, peak_day=peak_day), width="stretch")
    with c2:
        st.plotly_chart(
            peak_day_profile_figure(
                peak_day_bas_profile(bas, peak_day),
                day=peak_day,
                peak_kw=peak_kw_auto,
            ),
            width="stretch",
        )

    closeness = load_closeness_table(bundle)
    if not closeness.empty:
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

    with st.spinner("Dial peak-day overlay…"):
        overlay = dial_peak_day_overlay(bundle)
    # Re-load Actual from picker bas for consistency
    try:
        bas2 = load_bas_demand_oat(bundle, csv_path=bas_path)
        day = overlay["day"]
        actual = peak_day_bas_profile(bas2, day)
        if not actual.empty:
            overlay["series"]["Actual"] = actual.rename(columns={"kw_avg": "kw"})
            overlay["peak_kw"] = float(actual["kw_avg"].max())
    except Exception:  # noqa: BLE001
        pass
    st.plotly_chart(dial_progression_figure(overlay), width="stretch")


def _render_building_tab(
    active: ModelCatalogEntry | None,
    idf_path: Path | None,
    idf_label: str,
    campus_label: str,
) -> None:
    st.caption("Massing from **picked** IDF only (published geometry, not CAD).")
    if idf_path is None or not idf_path.is_file():
        st.warning("Pick an IDF in the sidebar.")
        return
    geom = parse_idf_geometry(idf_path)
    title = f"{active.label if active else campus_label} · {idf_label}"
    st.plotly_chart(idf_massing_figure(geom, title=title), width="stretch")
    summary = geom.summary()
    st.subheader("Envelope")
    st.dataframe(envelope_table(summary), width="stretch", hide_index=True)
    st.subheader("Zones")
    zt = zones_table(summary)
    if not zt.empty:
        st.dataframe(zt, width="stretch", hide_index=True)
    if active and active.metrics and active.metrics.knobs:
        st.subheader("Scorecard knobs")
        st.dataframe(
            knobs_table(active.metrics.knobs), width="stretch", hide_index=True
        )


def main() -> None:
    st.set_page_config(page_title="Lakeside E+ gym", layout="wide")
    st.title("Lakeside E+ gym")

    try:
        from lakeside.paths import site_root

        site = site_root()
        site_key = str(site)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Site root not set: {exc}")
        return

    try:
        bundle = _bundle_cached(site_key)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load SiteUiBundle: {exc}")
        return

    picks = _render_sidebar_pickers(bundle, site)
    active = picks["active"]
    _render_overview_metrics(active, picks["idf_label"] or "—")

    tab_period, tab_fuel, tab_load, tab_bldg, tab_farm = st.tabs(
        [
            "Period explorer",
            "Fuel (campus)",
            "Load profiles (GL14)",
            "Building massing",
            "IdealLoads farm (diagnostic)",
        ]
    )
    with tab_period:
        _render_period_tab(bundle, active, picks["bas_path"])
    with tab_fuel:
        _render_fuel_tab(picks["campus_path"])
    with tab_load:
        _render_load_profiles_tab(bundle, active, picks["bas_path"])
    with tab_bldg:
        _render_building_tab(
            active,
            picks["idf_path"],
            picks["idf_label"],
            bundle.campus.label,
        )
    with tab_farm:
        _render_farm_diagnostic_tab()


if __name__ == "__main__":
    main()
