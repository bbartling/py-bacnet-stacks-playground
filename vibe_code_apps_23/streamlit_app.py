"""Vibe 23 Residential DSM Studio — Streamlit console.

Replay a 24h EnergyPlus extreme day in ~60s (summer Jul 15 / winter Jan 15),
browse IDF massing + energy-modeler dashboard, tweak battery sizing, upload
IDF / EPW / tariff files, and inspect the thermostat + battery grid-search story.

Cross-platform EnergyPlus paths come from ``.env`` (see ``.env.example``).
Streamlit Community Cloud runs fixture-only demo mode when EnergyPlus is absent.

Launch (Windows / Linux / macOS)::

    pip install -e ".[studio]"
    cp .env.example .env   # edit ENERGYPLUS_* for live runs
    streamlit run streamlit_app.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from vibe23.energyplus import resolve_native_energyplus
from vibe23.envfile import load_energyplus_env
from vibe23.residential.model import MODEL_IDF, equipment_provenance, find_denver_epw
from vibe23.residential.tariffs import summer_tou_hourly, winter_tou_hourly
from vibe23.studio.charts import cost_bar_figure, hour_axis, kwh_bar_figure, outdoor_kwh_cost_figure, playback_figure
from vibe23.studio.demo_data import (
    DEMO_FLOOR_FT2,
    cumulative_energy_cost,
    cumulative_kwh,
    daily_kwh,
    day_bill,
    energy_intensity_kwh_per_ft2,
    f_to_c,
    hourly_cost,
    hourly_kwh,
    illustrative_grid_ranking,
    interval_clock,
    load_outdoor_day,
    load_season_day,
    run_battery_on_load,
)
from vibe23.studio.idf_geometry import idf_massing_figure, parse_idf_geometry
from vibe23.studio.idf_inspect import inspect_idf
from vibe23.studio.uploads import expand_tariff_to_288, parse_epw_day, parse_tariff_csv

PLAY_SECONDS = 60.0
STREAMLIT_CLOUD = "https://share.streamlit.io"
STREAMLIT_HOME = "https://streamlit.io"
CONTRIBUTE_GITHUB = "https://github.com/bbartling/py-bacnet-stacks-playground"

load_energyplus_env()

st.set_page_config(
    page_title="Vibe 23 Residential DSM Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _theme_css(theme: str) -> str:
    dark = theme != "Light"
    if dark:
        return """
        <style>
          .block-container {
            padding-top: 1rem !important;
            padding-left: 2vw !important;
            padding-right: 2vw !important;
            max-width: 100% !important;
          }
          [data-testid="stAppViewContainer"] { background: #0F1419; }
          div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
          .v23-kicker { letter-spacing: 0.12em; text-transform: uppercase; font-size: 0.72rem;
            color: #E8A838; font-weight: 600; margin-bottom: 0.15rem; }
          .v23-hero { font-size: 1.85rem; font-weight: 700; line-height: 1.15; margin: 0 0 0.35rem 0; color: #E7ECF3; }
          .v23-sub { color: #9AA7B8; margin-bottom: 0.75rem; }
          .v23-card {
            border: 1px solid #2A3545; border-radius: 12px; padding: 0.85rem 1rem;
            background: #1A2332; margin-bottom: 0.75rem;
          }
        </style>
        """
    return """
    <style>
      .block-container {
        padding-top: 1rem !important;
        padding-left: 2vw !important;
        padding-right: 2vw !important;
        max-width: 100% !important;
      }
      [data-testid="stAppViewContainer"] { background: #F7F9FC; }
      div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
      .v23-kicker { letter-spacing: 0.12em; text-transform: uppercase; font-size: 0.72rem;
        color: #B45309; font-weight: 600; margin-bottom: 0.15rem; }
      .v23-hero { font-size: 1.85rem; font-weight: 700; line-height: 1.15; margin: 0 0 0.35rem 0; color: #0F172A; }
      .v23-sub { color: #475569; margin-bottom: 0.75rem; }
      .v23-card {
        border: 1px solid #E2E8F0; border-radius: 12px; padding: 0.85rem 1rem;
        background: #FFFFFF; margin-bottom: 0.75rem;
      }
    </style>
    """


def _init_state() -> None:
    defaults = {
        "playing": False,
        "step": 0,
        "_do_advance": False,
        "_stop_after_advance": False,
        "trace": "DR event",
        "season": "Summer extreme (Jul 15)",
        "ui_theme": "Dark",
        "capacity_kwh": 13.5,
        "max_power_kw": 5.0,
        "eta": 0.95,
        "soc_min": 0.10,
        "soc_max": 0.95,
        "initial_soc": 0.50,
        "attach_battery": True,
        "idf_text": None,
        "idf_name": MODEL_IDF.name,
        "outdoor_override": None,
        "rates_override": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


@st.cache_data(show_spinner=False)
def _day(season_key: str) -> dict:
    return load_season_day(season_key)


@st.cache_data(show_spinner=False)
def _outdoor(season_key: str) -> dict:
    return load_outdoor_day(season=season_key)


@st.cache_data(show_spinner=False)
def _geom_from_text(text: str):
    return parse_idf_geometry(text)


@st.cache_data(show_spinner=False)
def _board() -> dict:
    return illustrative_grid_ranking()


@st.cache_data(show_spinner=False)
def _default_idf_text() -> str:
    return MODEL_IDF.read_text(encoding="utf-8", errors="replace")


def _maybe_advance_playhead(n: int) -> None:
    if not st.session_state.pop("_do_advance", False):
        return
    nxt = int(st.session_state.step) + 1
    if nxt >= n:
        st.session_state.step = n - 1
        st.session_state.playing = False
    else:
        st.session_state.step = nxt
    if st.session_state.pop("_stop_after_advance", False):
        st.session_state.playing = False


def _queue_play_tick(n: int) -> None:
    if not st.session_state.playing:
        return
    play_once = os.environ.get("VIBE23_STUDIO_PLAY_ONCE") == "1"
    if not play_once:
        time.sleep(PLAY_SECONDS / float(n))
    st.session_state._do_advance = True
    if play_once:
        st.session_state._stop_after_advance = True
    st.rerun()


def _transport(n: int) -> None:
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 3, 2])
    with c1:
        if st.button("Play", type="primary", use_container_width=True, disabled=st.session_state.playing):
            st.session_state.playing = True
            if st.session_state.step >= n - 1:
                st.session_state.step = 0
            st.rerun()
    with c2:
        if st.button("Pause", use_container_width=True, disabled=not st.session_state.playing):
            st.session_state.playing = False
            st.session_state._do_advance = False
            st.rerun()
    with c3:
        if st.button("Reset", use_container_width=True):
            st.session_state.playing = False
            st.session_state._do_advance = False
            st.session_state.step = 0
            st.rerun()
    with c4:
        st.slider(
            "Timestep (5-min)",
            min_value=0,
            max_value=n - 1,
            key="step",
            disabled=st.session_state.playing,
            help="288 EnergyPlus intervals ≈ 24 hours. Play walks them in ~60 seconds.",
        )
    with c5:
        clock = interval_clock(int(st.session_state.step), intervals=n)
        pct = 100.0 * (int(st.session_state.step) + 1) / n
        st.metric("Clock", clock, delta=f"{pct:.0f}% of day")


def _season_key() -> str:
    return "winter" if "Winter" in str(st.session_state.season) else "summer"


def _rates_for_season(season_key: str) -> list[float]:
    if st.session_state.rates_override:
        return list(st.session_state.rates_override)
    tariff = winter_tou_hourly() if season_key == "winter" else summer_tou_hourly()
    return list(tariff.energy_rates_per_kwh)


def main() -> None:
    _init_state()
    theme = str(st.session_state.ui_theme)
    st.markdown(_theme_css(theme), unsafe_allow_html=True)
    plot_theme = "light" if theme == "Light" else "dark"

    season_key = _season_key()
    day = _day(season_key)
    n = int(day["intervals"])
    _maybe_advance_playhead(n)
    hours = hour_axis(n)
    rates = _rates_for_season(season_key)
    outdoor = st.session_state.outdoor_override or _outdoor(season_key)

    eplus = resolve_native_energyplus()
    epw = find_denver_epw()

    top_l, top_r = st.columns([3.2, 1.4], gap="large")
    with top_l:
        st.markdown('<div class="v23-kicker">Vibe 23 · Residential DSM Studio</div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="v23-hero">Heat-pump home · summer &amp; winter extremes · battery arbitrage</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="v23-sub">Illustrative TOU · HYPOTHETICAL_GL14_TUNED_DEMO_MODEL · '
            f"Golden/NREL EPW · Carrier 50EZ060 · ~{DEMO_FLOOR_FT2:,.0f} ft² · "
            f"{sys.platform} · {'EnergyPlus ready' if eplus else 'fixture demo mode'}</p>",
            unsafe_allow_html=True,
        )
    with top_r:
        st.radio("Theme", ["Dark", "Light"], key="ui_theme", horizontal=True)
        b1, b2 = st.columns(2)
        b1.link_button("Streamlit Cloud", STREAMLIT_CLOUD, use_container_width=True)
        b2.link_button("Contribute", CONTRIBUTE_GITHUB, use_container_width=True)
        st.caption(f"[streamlit.io]({STREAMLIT_HOME}) · deploy this app or fork the repo")

    with st.sidebar:
        st.header("Extreme day")
        st.radio(
            "Season",
            ["Summer extreme (Jul 15)", "Winter extreme (Jan 15)"],
            key="season",
            help="Jul 15 hot-afternoon DR · Jan 15 morning preheat / shed.",
        )
        st.radio(
            "Thermal trace",
            ["Baseline", "DR event"],
            key="trace",
        )
        st.divider()
        st.header("Battery sizing")
        st.toggle("Dispatch battery on purchased-grid load", key="attach_battery")
        st.slider("Usable capacity (kWh)", 5.0, 27.0, step=0.5, key="capacity_kwh")
        st.slider("Max charge/discharge (kW)", 1.0, 10.0, step=0.5, key="max_power_kw")
        st.slider("One-way efficiency eta", 0.85, 0.99, step=0.01, key="eta")
        c_a, c_b = st.columns(2)
        c_a.slider("SOC min", 0.05, 0.30, step=0.01, key="soc_min")
        c_b.slider("SOC max", 0.70, 1.00, step=0.01, key="soc_max")
        st.session_state.initial_soc = float(
            min(max(float(st.session_state.initial_soc), float(st.session_state.soc_min)), float(st.session_state.soc_max))
        )
        st.slider(
            "Initial SOC",
            min_value=float(st.session_state.soc_min),
            max_value=float(st.session_state.soc_max),
            step=0.01,
            key="initial_soc",
        )
        st.caption("Typical wall-pack: 13.5 kWh · ±5 kW · η≈0.95 · SOC 10–95%.")
        st.divider()
        st.header("Uploads")
        idf_up = st.file_uploader("EnergyPlus IDF", type=["idf", "imf"], help="Parsed with Pydantic for the modeler dashboard.")
        epw_up = st.file_uploader("Weather EPW", type=["epw"], help="Preferred EnergyPlus weather format.")
        tariff_up = st.file_uploader("Tariff CSV", type=["csv"], help="24 / 96 / 288 rates, or hour,rate columns.")
        if idf_up is not None:
            st.session_state.idf_text = idf_up.getvalue().decode("utf-8", errors="replace")
            st.session_state.idf_name = idf_up.name
            st.success(f"IDF loaded · {idf_up.name}")
        if epw_up is not None:
            try:
                month, day = (1, 15) if season_key == "winter" else (7, 15)
                outdoor_model = parse_epw_day(
                    epw_up.getvalue().decode("utf-8", errors="replace"),
                    month=month,
                    day=day,
                    source_name=epw_up.name,
                )
                st.session_state.outdoor_override = outdoor_model.model_dump()
                outdoor = st.session_state.outdoor_override
                st.success(f"EPW day {month}/{day} · {epw_up.name}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"EPW parse failed: {exc}")
        if tariff_up is not None:
            try:
                upload = parse_tariff_csv(tariff_up.getvalue().decode("utf-8", errors="replace"), source_name=tariff_up.name)
                st.session_state.rates_override = expand_tariff_to_288(upload)
                rates = list(st.session_state.rates_override)
                st.success(f"Tariff · {upload.intervals} intervals → 288")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Tariff parse failed: {exc}")
        if st.button("Clear uploads"):
            st.session_state.idf_text = None
            st.session_state.idf_name = MODEL_IDF.name
            st.session_state.outdoor_override = None
            st.session_state.rates_override = None
            st.rerun()
        st.divider()
        with st.expander("EnergyPlus environment", expanded=False):
            st.code(
                "\n".join(
                    [
                        f"platform = {sys.platform}",
                        f"ENERGYPLUS_EXE = {os.environ.get('ENERGYPLUS_EXE') or '(unset)'}",
                        f"ENERGYPLUS_ROOT = {os.environ.get('ENERGYPLUS_ROOT') or '(unset)'}",
                        f"ENERGYPLUS_WEATHER = {os.environ.get('ENERGYPLUS_WEATHER') or '(unset)'}",
                        f"resolved_exe = {eplus}",
                        f"resolved_epw = {epw}",
                    ]
                ),
                language="text",
            )
            st.caption("Copy `.env.example` → `.env` on Windows, Linux, or macOS.")
        prov = equipment_provenance()
        st.caption(f"{prov['equipment']} · {prov['nominal_tons']} ton · COP c/h {prov['cooling_cop']}/{prov['heating_cop']}")

    house_kw = list(day["baseline_kw"] if st.session_state.trace == "Baseline" else day["event_kw"])
    temp_f = list(day["baseline_temp_f"] if st.session_state.trace == "Baseline" else day["event_temp_f"])
    zone_name = "ZONE ONE"

    batt = None
    purchased = None
    soc_pct = None
    if st.session_state.attach_battery:
        batt = run_battery_on_load(
            house_kw,
            capacity_kwh=float(st.session_state.capacity_kwh),
            max_power_kw=float(st.session_state.max_power_kw),
            eta=float(st.session_state.eta),
            soc_min=float(st.session_state.soc_min),
            soc_max=float(st.session_state.soc_max),
            initial_soc=float(st.session_state.initial_soc),
            season=season_key,
        )
        purchased = list(batt["purchased_kw"])  # type: ignore[index]
        soc_pct = [100.0 * float(s) for s in batt["soc"]]  # type: ignore[index]

    step = int(st.session_state.step)
    bill_series = cumulative_energy_cost(purchased or house_kw, tuple(rates))
    house_cum_kwh = cumulative_kwh(house_kw)
    purchased_cum_kwh = cumulative_kwh(purchased) if purchased is not None else None
    house_day_kwh = daily_kwh(house_kw)
    purchased_day_kwh = daily_kwh(purchased) if purchased is not None else house_day_kwh
    house_bill = day_bill(house_kw, season=season_key)
    net_bill = float(batt["billing_cost"]) if batt else house_bill
    intensity = energy_intensity_kwh_per_ft2(house_day_kwh)
    h_kwh = hourly_kwh(house_kw)
    h_cost = hourly_cost(house_kw, rates)
    outdoor_f = list(outdoor["drybulb_f"])

    idf_text = st.session_state.idf_text or _default_idf_text()
    dashboard = inspect_idf(idf_text, source_name=str(st.session_state.idf_name))

    st.plotly_chart(
        outdoor_kwh_cost_figure(
            hourly_kwh=h_kwh,
            outdoor_f=outdoor_f,
            hourly_cost=h_cost,
            title=f"Static extreme-day context · {day.get('label', season_key)} (does not scrub with Play)",
            theme=plot_theme,
        ),
        width="stretch",
    )

    tab_twin, tab_model, tab_batt, tab_dr, tab_grid = st.tabs(
        ["Twin replay", "IDF dashboard", "Battery lab", "DR event", "Grid search"]
    )

    with tab_twin:
        _transport(n)
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("House kW", f"{house_kw[step]:.2f}")
        m2.metric("Purchased kW", f"{(purchased or house_kw)[step]:.2f}")
        m3.metric("kWh to now", f"{(purchased_cum_kwh or house_cum_kwh)[step]:.1f}")
        m4.metric("Daily house kWh", f"{house_day_kwh:.1f}")
        m5.metric("Zone °F", f"{temp_f[step]:.2f}")
        m6.metric("Cost to now", f"${bill_series[step]:.2f}", delta=f"day ${net_bill:.2f}")
        st.caption(
            f"Full-day house **{house_day_kwh:.1f} kWh** · purchased **{purchased_day_kwh:.1f} kWh** · "
            f"~{intensity:.3f} kWh/ft²-day · outdoor now ~{outdoor_f[min(step // 12, 23)]:.1f}°F"
        )
        left, right = st.columns([1.2, 1.0], gap="large")
        with left:
            st.plotly_chart(
                playback_figure(
                    hours=hours,
                    house_kw=house_kw,
                    purchased_kw=purchased,
                    temp_f=temp_f,
                    price=rates,
                    soc_pct=soc_pct,
                    cumulative_house_kwh=house_cum_kwh,
                    cumulative_purchased_kwh=purchased_cum_kwh,
                    step=step,
                    title=f"{st.session_state.season} · {st.session_state.trace} · {interval_clock(step)}",
                ),
                width="stretch",
            )
        with right:
            geom = _geom_from_text(idf_text)
            mass = idf_massing_figure(
                geom,
                zone_temps={zone_name: f_to_c(temp_f[step])},
                title=f"IDF massing · {st.session_state.idf_name}",
                height=520,
            )
            st.plotly_chart(mass, width="stretch")

    with tab_model:
        st.subheader("Energy-modeler dashboard")
        e = dashboard.envelope
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Floor area", f"{e.floor_ft2:,.0f} ft²")
        c2.metric("WWR", f"{e.wwr_pct:.1f}%" if e.wwr_pct is not None else "—")
        c3.metric("Zones", str(e.n_zones))
        c4.metric("HVAC autosize", "Yes" if dashboard.hvac_autosize else "No")
        c5.metric("Cooling", f"{dashboard.cooling_tons:.1f} ton" if dashboard.cooling_tons else "—")
        c6.metric("Heating kW", f"{(dashboard.heating_capacity_w or 0)/1000:.1f}" if dashboard.heating_capacity_w else "—")
        st.markdown('<div class="v23-card">', unsafe_allow_html=True)
        left, right = st.columns(2)
        with left:
            st.write(
                {
                    "source": dashboard.source_name,
                    "version": dashboard.version,
                    "building": dashboard.building_name,
                    "timestep": dashboard.timestep,
                    "location": dashboard.location_name,
                    "lat / lon": f"{dashboard.latitude}, {dashboard.longitude}",
                    "elevation_m": dashboard.elevation_m,
                    "bbox_ft": f"{e.bbox_ft_dx}×{e.bbox_ft_dy}×{e.bbox_ft_dz}",
                    "wall_m2": e.wall_m2,
                    "window_m2": e.window_m2,
                    "roof_m2": e.roof_m2,
                    "autosized_fields": dashboard.autosized_field_count,
                }
            )
        with right:
            st.write(
                {
                    "simulation_control": dashboard.simulation_control.model_dump(),
                    "equipment_types": dashboard.equipment_types,
                    "zones": dashboard.zone_names,
                    "coils": [c.model_dump() for c in dashboard.coils],
                }
            )
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption("Parsed with Pydantic · geometry from BuildingSurface:Detailed (vibe20-style massing).")

    with tab_batt:
        st.subheader("Stage 2 — battery dispatch")
        base_kw = list(day["baseline_kw"])
        event_kw = list(day["event_kw"])
        batt_base = run_battery_on_load(
            base_kw,
            capacity_kwh=float(st.session_state.capacity_kwh),
            max_power_kw=float(st.session_state.max_power_kw),
            eta=float(st.session_state.eta),
            soc_min=float(st.session_state.soc_min),
            soc_max=float(st.session_state.soc_max),
            initial_soc=float(st.session_state.initial_soc),
            season=season_key,
        )
        batt_dr = run_battery_on_load(
            event_kw,
            capacity_kwh=float(st.session_state.capacity_kwh),
            max_power_kw=float(st.session_state.max_power_kw),
            eta=float(st.session_state.eta),
            soc_min=float(st.session_state.soc_min),
            soc_max=float(st.session_state.soc_max),
            initial_soc=float(st.session_state.initial_soc),
            season=season_key,
        )
        cost_cases = {
            "Baseline house": day_bill(base_kw, season=season_key),
            "DR thermal only": day_bill(event_kw, season=season_key),
            "Battery on baseline": batt_base["billing_cost"],
            "Battery on DR": batt_dr["billing_cost"],
        }
        kwh_cases = {
            "Baseline house": daily_kwh(base_kw),
            "DR thermal only": daily_kwh(event_kw),
            "Purchased · batt on baseline": batt_base["purchased_kwh"],
            "Purchased · batt on DR": batt_dr["purchased_kwh"],
        }
        c_left, c_right = st.columns(2)
        c_left.plotly_chart(
            cost_bar_figure(list(cost_cases.keys()), [float(v) for v in cost_cases.values()], title="Illustrative $/day"),
            width="stretch",
        )
        c_right.plotly_chart(
            kwh_bar_figure(list(kwh_cases.keys()), [float(v) for v in kwh_cases.values()], title="Daily energy (kWh)"),
            width="stretch",
        )
        if batt is not None:
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Final SOC", f"{100 * float(batt['final_soc']):.0f}%")
            b2.metric("Save vs house-only", f"${house_bill - net_bill:.2f}")
            b3.metric("Purchased peak kW", f"{max(purchased or [0.0]):.2f}")
            b4.metric("Purchased day kWh", f"{purchased_day_kwh:.1f}", delta=f"house {house_day_kwh:.1f}")

    with tab_dr:
        st.subheader(f"Stage 1 thermal — {day.get('label', season_key)}")
        base_kwh = daily_kwh(list(day["baseline_kw"]))
        event_kwh = daily_kwh(list(day["event_kw"]))
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Baseline peak kW", f"{max(day['baseline_kw']):.2f}")
        d2.metric("Event peak kW", f"{max(day['event_kw']):.2f}")
        d3.metric("Baseline day kWh", f"{base_kwh:.1f}")
        d4.metric("Event day kWh", f"{event_kwh:.1f}", delta=f"{event_kwh - base_kwh:+.1f}")
        base_cum = cumulative_kwh(list(day["baseline_kw"]))
        event_cum = cumulative_kwh(list(day["event_kw"]))
        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.07,
            subplot_titles=("Power (kW)", "Cumulative energy (kWh)", "Zone °F"),
        )
        end = step + 1
        fig.add_trace(go.Scatter(x=hours[:end], y=day["baseline_kw"][:end], name="Baseline kW", line=dict(color="#9AA7B8")), row=1, col=1)
        fig.add_trace(go.Scatter(x=hours[:end], y=day["event_kw"][:end], name="DR event kW", line=dict(color="#E8A838")), row=1, col=1)
        fig.add_trace(go.Scatter(x=hours[:end], y=base_cum[:end], name="Baseline kWh", line=dict(color="#9AA7B8")), row=2, col=1)
        fig.add_trace(go.Scatter(x=hours[:end], y=event_cum[:end], name="DR kWh", line=dict(color="#E8A838")), row=2, col=1)
        fig.add_trace(go.Scatter(x=hours[:end], y=day["baseline_temp_f"][:end], name="Baseline °F", line=dict(color="#8FB8FF")), row=3, col=1)
        fig.add_trace(go.Scatter(x=hours[:end], y=day["event_temp_f"][:end], name="DR °F", line=dict(color="#FF6B6B")), row=3, col=1)
        if season_key == "summer":
            fig.add_vrect(x0=14, x1=18, fillcolor="#E8A838", opacity=0.12, line_width=0, row=1, col=1)
        else:
            fig.add_vrect(x0=6, x1=9, fillcolor="#8FB8FF", opacity=0.12, line_width=0, row=1, col=1)
        fig.add_vline(x=hours[step], line_dash="dash", line_color="#94A3B8")
        fig.update_layout(height=560, legend=dict(orientation="h"), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")

    with tab_grid:
        st.subheader("Two-stage optimizer board")
        board = _board()
        winner = board.get("winner") or {}
        g1, g2, g3 = st.columns(3)
        g1.metric("Winner", str(winner.get("candidate_id", "—")))
        g2.metric("Illustrative $/day", f"${float(winner.get('billing_cost', 0)):.2f}" if winner else "—")
        g3.metric("Catalog size", str(board.get("catalog_size", "—")))
        st.dataframe(
            [
                {
                    "rank": row["rank"],
                    "candidate": row["candidate_id"],
                    "stage": row["stage"],
                    "$/day": None if row["billing_cost"] is None else round(float(row["billing_cost"]), 2),
                    "Δ vs baseline": None
                    if row["delta_vs_baseline"] is None
                    else round(float(row["delta_vs_baseline"]), 2),
                    "note": row["note"][:80],
                }
                for row in board["rows"]
            ],
            hide_index=True,
            width="stretch",
        )
        with st.expander("Run live EnergyPlus thermostat grid (optional)"):
            st.caption("Requires ENERGYPLUS_EXE on this machine (not available on Streamlit Community Cloud).")
            max_c = st.number_input("Max candidates", min_value=1, max_value=16, value=2)
            if st.button("Run thermostat grid for selected season"):
                if eplus is None:
                    st.error("No native EnergyPlus found. Set ENERGYPLUS_EXE in .env.")
                else:
                    try:
                        from vibe23.residential.campaign import run_thermostat_grid

                        with st.spinner("Running EnergyPlus candidates…"):
                            result = run_thermostat_grid(
                                season=season_key,
                                output_root=Path("campaigns/runs/studio_grid") / season_key,
                                max_candidates=int(max_c),
                            )
                        st.success("Grid finished")
                        st.json(result.get("ranking") or result)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Live grid failed: {exc}")

    _queue_play_tick(n)


if __name__ == "__main__":
    main()
