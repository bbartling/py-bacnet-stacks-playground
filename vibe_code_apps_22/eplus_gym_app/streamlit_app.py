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
from eplus_gym_app.gl14_monthly import champion_gl14_monthly
from eplus_gym_app.period_explorer import (
    PERIOD_PRESETS,
    locked_calibration_window,
    period_overlay,
)
from eplus_gym_app.pickers import list_bill_csvs_near
from eplus_gym_app.plots import (
    demand_vs_oat_figure,
    dial_progression_figure,
    fuel_monthly_figure,
    gl14_monthly_kwh_figure,
    gl14_monthly_pct_figure,
    gl14_monthly_peak_figure,
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


def _fmt_kwh(x: float | None) -> str:
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
    idf_name = (
        active.idf_pin
        if active
        else (bundle.idf_path.name if bundle.idf_path else "—")
    )
    family = active.family if active else "UNKNOWN"
    met = active.metrics if active else None
    gl14_label = (
        "PASS"
        if met and met.gl14_pass is True
        else ("FAIL" if met and met.gl14_pass is False else "—")
    )
    eui = campus.site_eui_kbtu_ft2() if campus is not None else None
    eui_bit = f" · site EUI **{eui:.1f} kBtu/ft²**" if eui is not None else ""
    physics = (
        "This is the **A04 W2A plant twin** (water-to-air heat pumps). "
        "It is **not** the IdealLoads / BOPTEST structural gym "
        "(`STRUCTURAL_LOAD_DIAGNOSTIC` is CLI-only)."
        if family == "W2A_PHYSICAL_DSM"
        else "This pack is **not** the published A04 W2A plant twin."
    )
    st.info(
        f"**Model:** `{idf_name}` · **{bundle.dsm_champion}** · `{family}`. "
        f"{physics} GL14 **{gl14_label}** · scorecard peak "
        f"**{_fmt_kw(met.peak_kw if met else None)} kW**{eui_bit} · promote=False."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("DSM champion", bundle.dsm_champion)
    c2.metric("Family", family)
    c3.metric("GL14", gl14_label)
    c4.metric("Scorecard peak kW", _fmt_kw(met.peak_kw if met else None))


def _load_campus(bundle: SiteUiBundle) -> Campus | None:
    src = bundle.campus.source
    if not src.is_file():
        return None
    try:
        return _campus_cached(str(src))
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Campus load failed: {exc}")
        return None


def _render_run_dsm_tab(bundle: SiteUiBundle) -> None:
    from eplus_gym_app.dsm_console import render_run_dsm_tab

    render_run_dsm_tab(bundle)


def _render_calibration_tab(
    bundle: SiteUiBundle,
    campus: Campus | None,
    active: ModelCatalogEntry | None,
) -> None:
    st.caption(
        "Published GL14 / closeness / bills / IDF. Not the DSM runner. "
        "Closeness is **electric kW** (BAS interval meter vs E+ facility)."
    )
    gl14_rows = catalog_gl14_table(bundle)
    if gl14_rows:
        st.dataframe(pd.DataFrame(gl14_rows), width="stretch")

    st.subheader("GL14 fuel bills · Actual vs EnergyPlus")
    st.caption(
        "Utility bills vs published A04 W2A monthly facility (eplusmtr). "
        "Not a DSM strategy run and not the IdealLoads C02 / structural farm."
    )
    elec = campus.electric_monthly() if campus is not None else pd.DataFrame()
    pairs = champion_gl14_monthly(bundle, active, campus_elec=elec if not elec.empty else None)
    has_pairs = (
        not pairs.empty
        and pairs["kwh_obs"].notna().any()
        and pairs["kwh_sim"].notna().any()
    )
    if campus is not None:
        campus_path = bundle.campus.source
        st.caption(
            f"**{campus.label}** (`{campus.campus_id}`) · source=`{campus_path.name}`"
        )
        bills = list_bill_csvs_near(campus_path)
        if bills:
            st.caption("Bill CSVs: " + ", ".join(p.name for p in bills))
    if has_pairs:
        plot_pairs = pairs.dropna(subset=["kwh_obs", "kwh_sim"])
        months = [
            str(m)
            for m in plot_pairs["month"].astype(str).tolist()
            if m and m != "nan"
        ]
        pick = months[-1] if months else None
        if months:
            default_fuel = (
                bundle.dial_ladder.peak_day[:7]
                if bundle.dial_ladder.peak_day[:7] in months
                else months[-1]
            )
            pick = st.select_slider(
                "Billing month",
                options=months,
                value=default_fuel,
                key="cal_fuel_month",
            )
        sim_id = str(pairs["sim_id"].dropna().iloc[0]) if "sim_id" in pairs.columns else "A04"
        if pick:
            row = pairs.loc[pairs["month"].astype(str) == pick]
            if not row.empty:
                r0 = row.iloc[0]
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Bill kWh", _fmt_kwh(r0.get("kwh_obs")))
                f2.metric("E+ kWh", _fmt_kwh(r0.get("kwh_sim")))
                f3.metric("E+ vs bill kWh", _fmt_pct(r0.get("pct_error")))
                peak_pct = None
                obs_p, sim_p = r0.get("peak_kw_obs"), r0.get("peak_kw_sim")
                if obs_p == obs_p and sim_p == sim_p and obs_p not in (None, 0):
                    peak_pct = 100.0 * (float(sim_p) - float(obs_p)) / float(obs_p)
                f4.metric("E+ vs bill peak", _fmt_pct(peak_pct))
        st.plotly_chart(
            gl14_monthly_kwh_figure(plot_pairs, highlight=pick, sim_id=sim_id),
            width="stretch",
        )
        st.plotly_chart(
            gl14_monthly_peak_figure(plot_pairs, highlight=pick, sim_id=sim_id),
            width="stretch",
        )
        st.plotly_chart(
            gl14_monthly_pct_figure(plot_pairs, highlight=pick, sim_id=sim_id),
            width="stretch",
        )
        show = pairs.drop(columns=["sim_id"], errors="ignore")
        st.dataframe(show.round(2), width="stretch", hide_index=True)
    elif campus is not None and not elec.empty:
        st.info("No published A04 monthly E+ meter table on this pack — bills only.")
        st.plotly_chart(
            fuel_monthly_figure(elec, title=f"{campus.label} · monthly electric"),
            width="stretch",
        )
        st.dataframe(elec, width="stretch", hide_index=True)
    elif campus is None:
        st.warning("No vibe20 campus on the published pack.")
    else:
        st.info("No monthly utility bills or published A04 monthly E+ on this pack.")

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
        st.caption(
            "closeness% = max(0, 100 − |sim−obs|/obs × 100) on **electric kW** "
            "(BAS interval vs E+ facility)."
        )
        left, right = st.columns(2)
        with left:
            st.markdown("**Weekday closeness % (electric kW)**")
            st.dataframe(
                closeness_pivot(closeness, day_type="weekday").round(1),
                width="stretch",
            )
        with right:
            st.markdown("**Weekend closeness % (electric kW)**")
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

    st.subheader("Actual vs champion (published dial)")
    st.caption(
        "Interval meter vs published A04 dial sim from the pack. "
        "Not a DSM strategy run and not the structural IdealLoads farm. "
        "Period is locked to the last **Run DSM** window (change it there and Run)."
    )
    from eplus_gym_app.dsm_console import load_last_run_meta

    last = st.session_state.get("dsm_last")
    if not last:
        try:
            last = load_last_run_meta(bundle)
        except Exception:  # noqa: BLE001
            last = None
    lock = locked_calibration_window(
        bas,
        peak_day=peak_day,
        last=last if isinstance(last, dict) else None,
        session_preset=st.session_state.get("dsm_period"),
        session_month=st.session_state.get("dsm_month"),
    )
    preset = lock["preset"] if lock["preset"] in PERIOD_PRESETS else "Peak day"
    month = lock["month"]
    bas_months = sorted({str(d)[:7] for d in bas["local_day"].astype(str)})
    month_opts = list(bas_months) or ["2026-01"]
    show_m = month if month in month_opts else month_opts[0]
    st.session_state["cal_locked_period"] = preset
    st.session_state["cal_locked_month"] = show_m
    c_a, c_b = st.columns([2, 1])
    with c_a:
        st.select_slider(
            "Period",
            options=list(PERIOD_PRESETS),
            key="cal_locked_period",
            disabled=True,
        )
    with c_b:
        st.selectbox(
            "Month (for Calendar month)",
            month_opts,
            key="cal_locked_month",
            disabled=True,
        )
    if lock["locked"]:
        st.info(
            f"Locked to last Run DSM · **{preset}** · `{lock['period']}` · "
            f"**{len(lock['days'])}** days."
        )
    else:
        st.caption(
            f"Follows the Run DSM tab (**{preset}** · `{lock['period']}`). "
            "Run a sim to lock this window."
        )
    period = period_overlay(
        bundle,
        active,
        preset=preset,
        month=month if preset == "Calendar month" else None,
        bas_csv=bundle.bas_demand_oat_csv,
        days=lock["days"],
    )
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Days in window", period["n_days"])
    k2.metric("Actual peak kW", _fmt_kw(period["actual_peak_kw"]))
    k3.metric("E+ peak kW", _fmt_kw(period["sim_peak_kw"]))
    k4.metric("E+ vs Actual peak", _fmt_pct(period.get("pct_vs_actual_peak")))
    e1, e2, e3 = st.columns(3)
    e1.metric("Actual kWh", _fmt_kwh(period.get("actual_kwh")))
    e2.metric("E+ kWh", _fmt_kwh(period.get("sim_kwh")))
    e3.metric("E+ vs Actual kWh", _fmt_pct(period.get("pct_vs_actual_kwh")))
    if period.get("sim") is None or (
        hasattr(period.get("sim"), "empty") and period["sim"].empty
    ):
        st.info("No published champion dial sim on this pack yet.")
    st.plotly_chart(period_overlay_figure(period), width="stretch")

    st.subheader("Building (champion IDF)")
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

    # Track tab state. Default on_change="ignore" resets to the first tab on
    # every rerun — so Run results vanished after clicking Run.
    tab_run, tab_cal = st.tabs(
        ["Run DSM", "Calibration"],
        key="lakeside_main_tabs",
        on_change="rerun",
    )
    with tab_run:
        _render_run_dsm_tab(bundle)
    with tab_cal:
        _render_calibration_tab(bundle, campus, bundle.champion())


if __name__ == "__main__":
    main()
