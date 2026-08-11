"""Lakeside DSM — human console (published pack only).

Agents ingest/publish ``site_ui_bundle_v1``. This app shows the current IDF +
fuel and runs DSM on the W2A champion. No file pickers. No live E+ in-process.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym_app.campus_fuel import Campus
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
from eplus_gym_app.pickers import list_bill_csvs_near
from eplus_gym_app.plots import (
    demand_vs_oat_figure,
    dial_progression_figure,
    fuel_monthly_figure,
    peak_day_profile_figure,
    period_overlay_figure,
)
from eplus_gym_app.site_bundle import (
    ModelCatalogEntry,
    SiteUiBundle,
    catalog_gl14_table,
    load_site_ui_bundle,
)
from eplus_gym_app.site_pack import SitePackError, ingest_site_pack, inventory_site_pack


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


def _render_sidebar(site: Path, bundle: SiteUiBundle) -> None:
    st.sidebar.header(site.name)
    st.sidebar.caption("Published pack · promote=False · no file pickers")
    inv = inventory_site_pack(site)
    for item in inv.checklist:
        if item.key == "campus_extra":
            continue
        mark = "ok" if item.status == "ok" else item.status
        st.sidebar.write(f"**{item.key}** · {mark}")
        if item.note:
            st.sidebar.caption(item.note)

    with st.sidebar.expander("Load site pack"):
        st.caption("Zip or folder. Agents normally do this via ingest_site_pack.py.")
        uploaded = st.file_uploader("Site pack zip", type=["zip"], key="site_pack_zip")
        folder = st.text_input("Or folder path", key="site_pack_folder")
        if st.button("Ingest pack", key="ingest_pack_btn"):
            try:
                if uploaded is not None:
                    tmp = site / "uploads" / "incoming_site_pack.zip"
                    tmp.parent.mkdir(parents=True, exist_ok=True)
                    tmp.write_bytes(uploaded.getvalue())
                    ingest_site_pack(tmp, site)
                elif folder.strip():
                    ingest_site_pack(Path(folder.strip()), site)
                else:
                    st.warning("Drop a zip or enter a folder path.")
                    return
                _bundle_cached.clear()
                _campus_cached.clear()
                st.success("Pack ingested. Reloading…")
                st.rerun()
            except SitePackError as exc:
                st.error(str(exc))
            except Exception as exc:  # noqa: BLE001
                st.error(f"Ingest failed: {exc}")


def _render_overview(bundle: SiteUiBundle, campus: Campus | None) -> None:
    active = bundle.champion()
    idf_label = (
        active.idf_pin
        if active
        else (bundle.idf_path.name if bundle.idf_path else "—")
    )
    met = active.metrics if active else None
    gl14_label = (
        "PASS"
        if met and met.gl14_pass is True
        else ("FAIL" if met and met.gl14_pass is False else "—")
    )
    eui = campus.site_eui_kbtu_ft2() if campus is not None else None
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Current IDF", idf_label.replace("lakeside_", "").replace(".idf", "")[:28])
    c2.metric("Family", (active.family if active else "—").replace("_", " ")[:22])
    c3.metric("GL14", gl14_label)
    c4.metric("Scorecard peak kW", _fmt_kw(met.peak_kw if met else None))
    c5.metric("Site EUI (kBtu/ft²)", f"{eui:.1f}" if eui is not None else "—")
    c6.metric("DSM champion", bundle.dsm_champion)
    st.caption(
        "Human console: fuel + this IDF + Run DSM. "
        "Agents iterate GL14 outside this UI · promote=False"
    )


def _load_campus(bundle: SiteUiBundle) -> Campus | None:
    src = bundle.campus.source
    if not src.is_file():
        return None
    try:
        return _campus_cached(str(src))
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Campus load failed: {exc}")
        return None


def _render_building_fuel_tab(bundle: SiteUiBundle, campus: Campus | None) -> None:
    active = bundle.champion()
    campus_path = bundle.campus.source

    st.subheader("Fuel (billing campus)")
    if campus is None:
        st.warning("No vibe20 campus on the published pack.")
    else:
        st.caption(
            f"**{campus.label}** (`{campus.campus_id}`) · "
            f"source=`{campus_path.name}`"
        )
        bills = list_bill_csvs_near(campus_path)
        if bills:
            st.caption("Bill CSVs: " + ", ".join(p.name for p in bills))
        elec = campus.electric_monthly()
        st.plotly_chart(
            fuel_monthly_figure(elec, title=f"{campus.label} · monthly electric"),
            width="stretch",
        )
        if not elec.empty:
            st.dataframe(elec, width="stretch", hide_index=True)

    st.subheader("Actual vs champion")
    st.caption("Interval + published A04 dial sim from the pack (not the structural IdealLoads farm).")
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
            bas = load_bas_demand_oat(bundle, csv_path=bundle.bas_demand_oat_csv)
            bas_months = sorted({str(d)[:7] for d in bas["local_day"].astype(str)})
        except Exception as exc:  # noqa: BLE001
            st.error(f"Interval CSV failed: {exc}")
            return
        month_opts = list(bas_months)
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

    overlay = period_overlay(
        bundle,
        active,
        preset=preset,
        month=month if preset == "Calendar month" else None,
        bas_csv=bundle.bas_demand_oat_csv,
    )
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Days in window", overlay["n_days"])
    k2.metric("Actual peak kW", _fmt_kw(overlay["actual_peak_kw"]))
    k3.metric(
        f"{overlay.get('sim_id') or 'Sim'} peak kW",
        _fmt_kw(overlay["sim_peak_kw"]),
    )
    k4.metric("Sim vs Actual", _fmt_pct(overlay.get("pct_vs_actual")))
    if overlay.get("sim") is None or (
        hasattr(overlay.get("sim"), "empty") and overlay["sim"].empty
    ):
        st.info("No published champion dial sim on this pack yet.")
    st.plotly_chart(period_overlay_figure(overlay), width="stretch")

    st.subheader("Building")
    idf_path = (active.idf_path if active else None) or bundle.idf_path
    idf_label = active.idf_pin if active else (idf_path.name if idf_path else "—")
    if idf_path is None or not idf_path.is_file():
        st.warning("No champion IDF on the published pack.")
        return
    geom = parse_idf_geometry(idf_path)
    title = f"{active.label if active else bundle.campus.label} · {idf_label}"
    st.plotly_chart(idf_massing_figure(geom, title=title), width="stretch")
    summary = geom.summary()
    st.dataframe(envelope_table(summary), width="stretch", hide_index=True)
    zt = zones_table(summary)
    if not zt.empty:
        st.dataframe(zt, width="stretch", hide_index=True)
    if active and active.metrics and active.metrics.knobs:
        st.dataframe(
            knobs_table(active.metrics.knobs), width="stretch", hide_index=True
        )


def _render_run_dsm_tab(bundle: SiteUiBundle) -> None:
    from eplus_gym_app.dsm_console import render_run_dsm_tab

    render_run_dsm_tab(bundle)


def _render_calibration_tab(bundle: SiteUiBundle, active: ModelCatalogEntry | None) -> None:
    st.caption("Agent-published GL14 / closeness / dial ladder. Not the DSM runner.")
    gl14_rows = catalog_gl14_table(bundle)
    if gl14_rows:
        st.dataframe(pd.DataFrame(gl14_rows), width="stretch")

    try:
        bas = load_bas_demand_oat(bundle, csv_path=bundle.bas_demand_oat_csv)
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

    overlay = dial_peak_day_overlay(bundle)
    try:
        day = overlay["day"]
        actual = peak_day_bas_profile(bas, day)
        if not actual.empty:
            overlay["series"]["Actual"] = actual.rename(columns={"kw_avg": "kw"})
            overlay["peak_kw"] = float(actual["kw_avg"].max())
    except Exception:  # noqa: BLE001
        pass
    st.plotly_chart(dial_progression_figure(overlay), width="stretch")
    if active and active.metrics and active.metrics.role:
        st.caption(active.metrics.role)


def _hint_site_path() -> str:
    desktop = Path.home() / "OneDrive" / "Desktop" / "testing" / "sp_creekside"
    if desktop.is_dir():
        return str(desktop)
    return ""


def _render_missing_site(exc: BaseException) -> None:
    from lakeside.paths import remember_site_root

    st.error(f"Site root not set: {exc}")
    st.caption(
        "This console reads the published pack under the site workspace. "
        "Paste the folder that contains `reports/` (usually Desktop `testing/sp_creekside`)."
    )
    typed = st.text_input(
        "Site workspace",
        value=_hint_site_path(),
        key="site_root_typed",
    )
    if st.button("Use this site", type="primary", key="use_site_root_btn"):
        try:
            remember_site_root(typed.strip())
            _bundle_cached.clear()
            _campus_cached.clear()
            st.rerun()
        except Exception as pin_exc:  # noqa: BLE001
            st.error(str(pin_exc))


def main() -> None:
    st.set_page_config(page_title="Lakeside DSM", layout="wide")
    st.title("Lakeside DSM")

    try:
        from lakeside.paths import site_root

        site = site_root()
        site_key = str(site)
    except Exception as exc:  # noqa: BLE001
        _render_missing_site(exc)
        return

    try:
        bundle = _bundle_cached(site_key)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load SiteUiBundle: {exc}")
        st.info("Ingest a site pack (sidebar) or run scripts/ingest_site_pack.py")
        return

    _render_sidebar(site, bundle)
    campus = _load_campus(bundle)
    _render_overview(bundle, campus)

    tab_home, tab_run, tab_cal = st.tabs(
        ["Building and fuel", "Run DSM", "Calibration"]
    )
    with tab_home:
        _render_building_fuel_tab(bundle, campus)
    with tab_run:
        _render_run_dsm_tab(bundle)
    with tab_cal:
        _render_calibration_tab(bundle, bundle.champion())


if __name__ == "__main__":
    main()
