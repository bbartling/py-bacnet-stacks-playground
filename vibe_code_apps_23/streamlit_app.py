"""Vibe 23 Residential DSM Studio — Streamlit console.

Replay a 24h EnergyPlus demo day in ~60s (summer Jul 15 / winter design Jan 3),
browse IDF massing + energy-modeler dashboard, tweak battery sizing, upload
IDF / EPW / tariff files, and inspect the thermostat + battery grid-search story.

Cross-platform EnergyPlus paths come from ``.env`` (see ``.env.example``).
Without EnergyPlus the app runs fixture-only demo mode.

Launch (Windows / Linux / macOS)::

    pip install -e ".[studio]"
    cp .env.example .env   # edit ENERGYPLUS_* for live runs
    # Preferred on Windows (pins Python 3.12 + Streamlit 1.59.2):
    .\\scripts\\run_studio.ps1
    # Or:
    streamlit run streamlit_app.py
"""
from __future__ import annotations

import io
import json
import math
import os
import sys
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from vibe23.energyplus import resolve_native_energyplus
from vibe23.envfile import load_energyplus_env
from vibe23.residential.model import MODEL_IDF, equipment_provenance, find_denver_epw
from vibe23.residential.tariffs import summer_tou_hourly, winter_tou_hourly
from vibe23.studio.charts import (
    cost_bar_figure,
    hour_axis,
    kwh_bar_figure,
    outdoor_kwh_cost_figure,
    playback_figure,
    search_convergence_figure,
    search_progress_ring,
)
from vibe23.studio.demo_data import (
    DEMO_FLOOR_FT2,
    DSM_INTERVAL_MINUTES,
    cumulative_energy_cost,
    cumulative_kwh,
    daily_kwh,
    day_bill,
    downsample_mean,
    dsm_block_size,
    dsm_dt_hours,
    dsm_steps_per_day,
    energy_intensity_kwh_per_ft2,
    f_to_c,
    hourly_cost,
    hourly_kwh,
    illustrative_grid_ranking,
    interval_clock,
    load_outdoor_day,
    load_season_day,
    outdoor_hour_index,
    run_battery_on_load,
)
from vibe23.studio.idf_geometry import idf_massing_figure, parse_idf_geometry
from vibe23.studio.idf_inspect import inspect_idf
from vibe23.studio.idf_preflight import preflight_idf
from vibe23.studio.search_progress import (
    algorithm_pseudocode,
    candidate_rows_for_animation,
    dimensions_from_form,
    enumerate_from_form,
    form_matches_fixture_catalog,
    format_dimension_values,
    load_grid_ranking,
    search_progress_state,
    season_dimension_defaults,
)
from vibe23.studio.session_workspace import (
    ensure_session_id,
    exports_dir,
    rotate_session_id,
    session_root,
    sweep_stale_workspaces,
    touch_heartbeat,
)
from vibe23.studio.uploads import expand_tariff_to_288, parse_epw_day, parse_tariff_csv

PLAY_SECONDS = 60.0
CAND_SECONDS = 0.4
AXES = ("twin", "dr", "cand")

load_energyplus_env()

st.set_page_config(
    page_title="Vibe 23 Residential DSM Studio",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _step_key(axis: str) -> str:
    return {"twin": "step", "dr": "dr_step", "cand": "cand_step"}[axis]


def _playing_key(axis: str) -> str:
    return f"playing_{axis}"


def _do_advance_key(axis: str) -> str:
    return f"_do_advance_{axis}"


def _stop_key(axis: str) -> str:
    return f"_stop_after_advance_{axis}"


def _maybe_advance(axis: str, n: int, *, inclusive_end: bool = False) -> None:
    """Advance one step. For twin/dr, max index is n-1. For cand, n is catalog size and step is evaluated count 0..n."""
    if not st.session_state.pop(_do_advance_key(axis), False):
        return
    key = _step_key(axis)
    cur = int(st.session_state.get(key, 0))
    if inclusive_end:
        # cand: step is evaluated count; stop at n
        nxt = cur + 1
        if nxt >= n:
            st.session_state[key] = n
            st.session_state[_playing_key(axis)] = False
        else:
            st.session_state[key] = nxt
    else:
        nxt = cur + 1
        if nxt >= n:
            st.session_state[key] = n - 1
            st.session_state[_playing_key(axis)] = False
        else:
            st.session_state[key] = nxt
    if st.session_state.pop(_stop_key(axis), False):
        st.session_state[_playing_key(axis)] = False


def _queue_tick(axis: str, n: int, *, seconds: float) -> bool:
    """Return True if this axis requested a rerun (caller should rerun once)."""
    if not st.session_state.get(_playing_key(axis), False):
        return False
    play_once = os.environ.get("VIBE23_STUDIO_PLAY_ONCE") == "1"
    if not play_once:
        time.sleep(seconds)
    st.session_state[_do_advance_key(axis)] = True
    if play_once:
        st.session_state[_stop_key(axis)] = True
    return True


def _transport(
    axis: str,
    n: int,
    *,
    play_label: str = "Play",
    step_label: str = "Playhead",
    metric_label: str = "Clock",
    inclusive_end: bool = False,
    show_clock: bool = True,
) -> None:
    playing = bool(st.session_state.get(_playing_key(axis), False))
    key = _step_key(axis)
    max_v = n if inclusive_end else max(n - 1, 0)
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 3, 2])
    with c1:
        if st.button(play_label, type="primary", use_container_width=True, disabled=playing, key=f"btn_play_{axis}"):
            st.session_state[_playing_key(axis)] = True
            if int(st.session_state.get(key, 0)) >= max_v:
                st.session_state[key] = 0
            st.rerun()
    with c2:
        if st.button("Pause", use_container_width=True, disabled=not playing, key=f"btn_pause_{axis}"):
            st.session_state[_playing_key(axis)] = False
            st.session_state[_do_advance_key(axis)] = False
            st.rerun()
    with c3:
        if st.button("Reset", use_container_width=True, key=f"btn_reset_{axis}"):
            st.session_state[_playing_key(axis)] = False
            st.session_state[_do_advance_key(axis)] = False
            st.session_state[key] = 0
            st.rerun()
    with c4:
        st.slider(
            step_label,
            min_value=0,
            max_value=max_v,
            key=key,
            disabled=playing,
        )
    with c5:
        step = int(st.session_state.get(key, 0))
        if show_clock:
            clock = interval_clock(step, intervals=max(n, 1))
            pct = 100.0 * (step + 1) / max(n, 1)
            st.metric(metric_label, clock, delta=f"{pct:.0f}% of day")
        else:
            pct = 100.0 * step / max(n, 1) if inclusive_end else 100.0 * (step + 1) / max(n, 1)
            st.metric(metric_label, f"{step}/{n}", delta=f"{pct:.0f}%")


def _init_state() -> None:
    defaults: dict = {
        "playing_twin": False,
        "playing_dr": False,
        "playing_cand": False,
        "step": 0,
        "dr_step": 0,
        "cand_step": 0,
        "_do_advance_twin": False,
        "_do_advance_dr": False,
        "_do_advance_cand": False,
        "_stop_after_advance_twin": False,
        "_stop_after_advance_dr": False,
        "_stop_after_advance_cand": False,
        "promoted_candidate_id": None,
        "promoted_action": None,
        "promoted_has_trace": False,
        "session_ranking_path": None,
        "dsm_minutes": 5,
        "_dsm_minutes_prev": 5,
        "season": "Summer hot day (Jul 15)",
        "capacity_kwh": 13.5,
        "max_power_kw": 5.0,
        "eta": 0.95,
        "soc_min": 0.10,
        "soc_max": 0.95,
        "initial_soc": 0.50,
        "attach_battery": True,
        "comfort_wtp": 0.10,
        "idf_text": None,
        "idf_name": MODEL_IDF.name,
        "outdoor_override": None,
        "rates_override": None,
        "epw_month": 7,
        "epw_day": 15,
        "econ_target": 5.0,
        "econ_capex": 9800.0,
        "econ_cycles": 250.0,
        "econ_dr_pay": 5.0,
        "econ_res": 3.0,
        "econ_annual_arb": 400.0,
        "econ_incl_dr": True,
        "econ_incl_res": False,
        "grid_max_candidates": 2,
        "epw_upload_name": None,
        "tariff_upload_name": None,
    }
    for dim in season_dimension_defaults("summer"):
        defaults[f"grid_dim_{dim.name}"] = format_dimension_values(dim.values)
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _ensure_session() -> str:
    sid = ensure_session_id(st.session_state)
    root = session_root(sid)
    touch_heartbeat(root)
    sweep_stale_workspaces(protect=root)
    return sid


def _clear_session() -> None:
    """Reset visitor state. Must run before widgets with keys are created."""
    rotate_session_id(st.session_state)
    for axis in AXES:
        st.session_state[_playing_key(axis)] = False
        st.session_state[_do_advance_key(axis)] = False
        st.session_state[_stop_key(axis)] = False
    st.session_state._reset_step = True
    st.session_state._dsm_minutes_prev = 5
    for key in ("dsm_minutes", "step", "dr_step", "cand_step"):
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.dsm_minutes = 5
    st.session_state.step = 0
    st.session_state.dr_step = 0
    st.session_state.cand_step = 0
    st.session_state.promoted_candidate_id = None
    st.session_state.promoted_action = None
    st.session_state.promoted_has_trace = False
    st.session_state.session_ranking_path = None
    st.session_state.idf_text = None
    st.session_state.idf_name = MODEL_IDF.name
    st.session_state.outdoor_override = None
    st.session_state.rates_override = None
    st.session_state.epw_upload_name = None
    st.session_state.tariff_upload_name = None
    st.session_state.epw_month = 7
    st.session_state.epw_day = 15
    st.session_state._season_key_for_epw = None
    for dim in season_dimension_defaults("summer"):
        st.session_state[f"grid_dim_{dim.name}"] = format_dimension_values(dim.values)


def _dsm_label(minutes: int) -> str:
    return "1 hour" if int(minutes) == 60 else f"{int(minutes)} min"


def _hourly_rates(rates_288: list[float]) -> list[float]:
    if len(rates_288) != 288:
        raise ValueError("expected 288 native rates")
    return [sum(rates_288[h * 12 : (h + 1) * 12]) / 12.0 for h in range(24)]


def _expand_hourly_rates(hourly: list[float]) -> list[float]:
    if len(hourly) != 24:
        raise ValueError("expected 24 hourly rates")
    out: list[float] = []
    for value in hourly:
        out.extend([float(value)] * 12)
    return out


def _hourly_editor_frame(outdoor: dict, rates_288: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hour": list(range(24)),
            "outdoor_drybulb_f": [float(v) for v in outdoor["drybulb_f"]],
            "rate_usd_per_kwh": _hourly_rates(rates_288),
        }
    )


def _parse_hourly_csv(text: str) -> tuple[list[float], list[float]]:
    """Parse a 24-row CSV with outdoor_drybulb_f and rate_usd_per_kwh columns."""
    df = pd.read_csv(io.StringIO(text.lstrip("\ufeff")))
    cols = {c.strip().lower(): c for c in df.columns}
    temp_key = next(
        (cols[k] for k in cols if "outdoor" in k or "drybulb" in k or k.endswith("_f") or k == "temp"),
        None,
    )
    rate_key = next(
        (cols[k] for k in cols if "rate" in k or "usd" in k or "price" in k),
        None,
    )
    if temp_key is None or rate_key is None:
        raise ValueError("CSV needs outdoor °F and rate $/kWh columns (see template)")
    temps = [float(v) for v in df[temp_key].tolist()]
    rates = [float(v) for v in df[rate_key].tolist()]
    if len(temps) != 24 or len(rates) != 24:
        raise ValueError(f"need exactly 24 rows (got temps={len(temps)}, rates={len(rates)})")
    return temps, rates


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


@st.cache_data(show_spinner=False)
def _preflight(text: str, name: str):
    return preflight_idf(text, source_name=name)


def _season_key() -> str:
    return "winter" if "Winter" in str(st.session_state.season) else "summer"


def _rates_for_season(season_key: str) -> list[float]:
    if st.session_state.rates_override:
        return list(st.session_state.rates_override)
    tariff = winter_tou_hourly() if season_key == "winter" else summer_tou_hourly()
    return list(tariff.energy_rates_per_kwh)


def _sync_epw_day_defaults(season_key: str) -> None:
    """Reset EPW month/day pickers when the demo season changes."""
    prev = st.session_state.get("_season_key_for_epw")
    if prev == season_key:
        return
    st.session_state._season_key_for_epw = season_key
    if season_key == "winter":
        st.session_state.epw_month = 1
        st.session_state.epw_day = 3
    else:
        st.session_state.epw_month = 7
        st.session_state.epw_day = 15


def _parse_action(action_json: object) -> dict:
    if isinstance(action_json, dict):
        return dict(action_json)
    if isinstance(action_json, str) and action_json.strip():
        try:
            parsed = json.loads(action_json)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _load_session_ranking(season_key: str) -> dict | None:
    try:
        path = st.session_state.get("session_ranking_path")
        if path:
            return load_grid_ranking(season_key, path=path)
        return load_grid_ranking(season_key)
    except Exception:  # noqa: BLE001
        return None


def _render_battery_lab(day: dict, season_key: str) -> None:
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
    house_day_kwh = daily_kwh(base_kw)
    purchased_day_kwh = float(batt_base["purchased_kwh"])
    house_bill = day_bill(base_kw, season=season_key)
    net_bill = float(batt_base["billing_cost"])
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Final SOC (baseline)", f"{100 * float(batt_base['final_soc']):.0f}%")
    b2.metric("Save vs house-only", f"${house_bill - net_bill:.2f}")
    b3.metric("Purchased peak kW", f"{max(batt_base['purchased_kw']):.2f}")
    b4.metric("Purchased day kWh", f"{purchased_day_kwh:.1f}", delta=f"house {house_day_kwh:.1f}")
    opt = batt_dr.get("optimality") or batt_base.get("optimality")
    if opt:
        st.caption(
            f"Greedy is a heuristic. On DR load it captures "
            f"**{100 * float(opt.get('greedy_captures_lp_savings_fraction', 0)):.0f}%** of cyclic-LP bill savings "
            f"(greedy save ${float(opt.get('greedy_savings_usd', 0)):.2f} vs LP "
            f"${float(opt.get('lp_savings_usd', 0)):.2f}). Purchased peak is capped ≤ house peak."
        )
        lp_dr = batt_dr.get("lp") or {}
        if lp_dr:
            st.write(
                {
                    "greedy_dr_bill": round(float(batt_dr["billing_cost"]), 3),
                    "lp_dr_bill": round(float(lp_dr["billing_cost"]), 3),
                    "lp_purchased_peak_kw": round(float(lp_dr["purchased_peak_kw"]), 3),
                    "house_peak_kw": round(float(batt_dr.get("house_peak_kw") or max(event_kw)), 3),
                }
            )


def _render_grid_board(session_id: str, season_key: str, eplus) -> None:
    st.subheader("Two-stage optimizer board")
    board = _board()
    winner = board.get("winner") or {}
    g1, g2, g3 = st.columns(3)
    g1.metric("Winner", str(winner.get("candidate_id", "—")))
    g2.metric("Illustrative $/day", f"${float(winner.get('billing_cost', 0)):.2f}" if winner else "—")
    g3.metric("Catalog size", str(board.get("catalog_size", "—")))
    st.table(
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
        ]
    )
    with st.expander("Run live EnergyPlus thermostat grid (optional)"):
        st.caption("Requires ENERGYPLUS_EXE on this machine.")
        st.caption(f"Max candidates (sidebar): {int(st.session_state.grid_max_candidates)}")
        if st.button("Run thermostat grid for selected season"):
            if eplus is None:
                st.error("No native EnergyPlus found. Set ENERGYPLUS_EXE in .env.")
            else:
                try:
                    from vibe23.residential.campaign import run_thermostat_grid

                    out = exports_dir(session_id) / "studio_grid" / season_key
                    with st.spinner("Running EnergyPlus candidates…"):
                        result = run_thermostat_grid(
                            season=season_key,
                            output_root=out,
                            max_candidates=int(st.session_state.grid_max_candidates),
                        )
                    ranking_path = out / "ranking.json"
                    st.session_state.session_ranking_path = str(ranking_path)
                    ranking_payload = result.get("ranking") or {}
                    win = ranking_payload.get("winner") or {}
                    if win:
                        st.session_state.promoted_candidate_id = win.get("candidate_id")
                        st.session_state.promoted_action = _parse_action(win.get("action_json"))
                        st.session_state.promoted_has_trace = True
                    st.success(f"Grid finished · {out}")
                    st.json(ranking_payload or result)
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Live grid failed: {exc}")


def main() -> None:
    _init_state()
    if st.session_state.pop("_pending_clear", False):
        _clear_session()
    session_id = _ensure_session()

    season_key = _season_key()
    _sync_epw_day_defaults(season_key)
    day = _day(season_key)
    rates_native = _rates_for_season(season_key)
    outdoor = st.session_state.outdoor_override or _outdoor(season_key)

    eplus = resolve_native_energyplus()
    epw = find_denver_epw()

    st.title("Vibe 23 — Residential DSM Studio")
    st.caption(
        "Illustrative TOU · HYPOTHETICAL_GL14_TUNED_DEMO_MODEL · Golden/NREL EPW · Carrier 50EZ060 · "
        f"~{DEMO_FLOOR_FT2:,.0f} ft² · {sys.platform} · "
        f"{'EnergyPlus ready' if eplus else 'fixture demo mode (no EnergyPlus on this machine)'}."
    )

    with st.sidebar:
        st.header("DSM playhead")
        if st.button("Clear session", help="Wipe this browser's uploads + temp workspace; mint a new session id."):
            st.session_state._pending_clear = True
            st.rerun()
        st.select_slider(
            "Sim interval",
            options=list(DSM_INTERVAL_MINUTES),
            format_func=_dsm_label,
            key="dsm_minutes",
            help="Coarsen twin replay for DSM viewing. Native fixture stays 5-min / 288.",
        )
        st.caption(f"Session `{session_id[:8]}…` · per-browser workspace")
        st.divider()
        st.header("Demo day")
        st.radio(
            "Season",
            ["Summer hot day (Jul 15)", "Winter design cold (Jan 3)"],
            key="season",
            help="Jul 15 hot-afternoon DR aligned to TOU peak · Jan 3 near-design cold morning shed. "
            "Mild Jan 15 is retained as fixtures/studio/winter_typical_jan15_dr_day.json. "
            "Twin replay animates the normal (baseline) day; DR event and Grid search have independent playheads.",
        )
        st.divider()
        with st.expander("Battery sizing", expanded=True):
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
        with st.expander("Comfort WTP", expanded=False):
            st.slider(
                "ILLUSTRATIVE comfort WTP ($/°F·h vs baseline)",
                min_value=0.0,
                max_value=0.50,
                step=0.05,
                key="comfort_wtp",
                help="Willingness-to-pay for thermal deviation from the paired baseline trajectory.",
            )
        with st.expander("Economics assumptions", expanded=False):
            st.slider("Target $/event", 0.0, 20.0, step=1.0, key="econ_target")
            st.slider("BESS net CapEx $", 0.0, 20000.0, step=100.0, key="econ_capex")
            st.slider("Cycles / year", 1.0, 500.0, step=10.0, key="econ_cycles")
            st.slider("DR incentive $/event", 0.0, 20.0, step=1.0, key="econ_dr_pay")
            st.slider("Resilience $/day (ILLUSTRATIVE)", 0.0, 20.0, step=0.5, key="econ_res")
            st.slider(
                "Assumed annual arbitrage $",
                0.0,
                2000.0,
                step=50.0,
                key="econ_annual_arb",
                help="Set explicitly. Extreme demo-day ×365 is forbidden.",
            )
            st.toggle("Include DR incentive layer", key="econ_incl_dr")
            st.toggle("Include resilience layer", key="econ_incl_res")
        with st.expander("Grid search", expanded=False):
            st.slider("Max candidates", 1, 16, step=1, key="grid_max_candidates")
        st.divider()
        st.info("Upload IDF / EPW / tariff and edit hourly weather + pricing on the **Inputs** tab.")
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
                        f"session_id = {session_id}",
                        f"session_root = {session_root(session_id)}",
                    ]
                ),
                language="text",
            )
            st.caption("Copy `.env.example` → `.env` on Windows, Linux, or macOS.")
        prov = equipment_provenance()
        st.caption(f"{prov['equipment']} · {prov['nominal_tons']} ton · COP c/h {prov['cooling_cop']}/{prov['heating_cop']}")

    minutes = int(st.session_state.dsm_minutes)
    block = dsm_block_size(minutes)
    dt_hours = dsm_dt_hours(minutes)
    n = dsm_steps_per_day(minutes)
    prev_minutes = st.session_state.get("_dsm_minutes_prev")
    if prev_minutes is not None and int(prev_minutes) != minutes:
        st.session_state.playing_twin = False
        st.session_state.playing_dr = False
        st.session_state._do_advance_twin = False
        st.session_state._do_advance_dr = False
        st.session_state._reset_step = True
    st.session_state._dsm_minutes_prev = minutes

    ranking = _load_session_ranking(season_key)
    anim_rows = candidate_rows_for_animation(ranking) if ranking else []
    n_cand = len(anim_rows)

    if st.session_state.pop("_reset_step", False):
        st.session_state.step = 0
        st.session_state.dr_step = 0
    else:
        if int(st.session_state.get("step", 0)) >= n:
            st.session_state.step = max(0, n - 1)
        if int(st.session_state.get("dr_step", 0)) >= n:
            st.session_state.dr_step = max(0, n - 1)

    _maybe_advance("twin", n)
    _maybe_advance("dr", n)
    _maybe_advance("cand", n_cand, inclusive_end=True)

    cand_step = int(st.session_state.get("cand_step", 0))
    if cand_step < 0:
        st.session_state.cand_step = 0
    elif cand_step > n_cand:
        st.session_state.cand_step = n_cand

    hours = hour_axis(n)

    # Twin replay always uses the normal (baseline) day — DR is a separate tab.
    house_kw_native = list(day["baseline_kw"])
    temp_f_native = list(day["baseline_temp_f"])
    zone_name = "ZONE ONE"

    batt = None
    purchased_native = None
    soc_pct_native = None
    if st.session_state.attach_battery:
        batt = run_battery_on_load(
            house_kw_native,
            capacity_kwh=float(st.session_state.capacity_kwh),
            max_power_kw=float(st.session_state.max_power_kw),
            eta=float(st.session_state.eta),
            soc_min=float(st.session_state.soc_min),
            soc_max=float(st.session_state.soc_max),
            initial_soc=float(st.session_state.initial_soc),
            season=season_key,
        )
        purchased_native = list(batt["purchased_kw"])  # type: ignore[index]
        soc_pct_native = [100.0 * float(s) for s in batt["soc"]]  # type: ignore[index]

    house_kw = downsample_mean(house_kw_native, block)
    temp_f = downsample_mean(temp_f_native, block)
    purchased = downsample_mean(purchased_native, block) if purchased_native is not None else None
    soc_pct = downsample_mean(soc_pct_native, block) if soc_pct_native is not None else None
    rates = downsample_mean(rates_native, block)

    step = int(st.session_state.step)
    bill_series = cumulative_energy_cost(purchased or house_kw, tuple(rates), dt_hours=dt_hours)
    house_cum_kwh = cumulative_kwh(house_kw, dt_hours=dt_hours)
    purchased_cum_kwh = cumulative_kwh(purchased, dt_hours=dt_hours) if purchased is not None else None
    house_day_kwh = daily_kwh(house_kw_native)
    purchased_day_kwh = daily_kwh(purchased_native) if purchased_native is not None else house_day_kwh
    house_bill = day_bill(house_kw_native, season=season_key)
    net_bill = float(batt["billing_cost"]) if batt else house_bill
    intensity = energy_intensity_kwh_per_ft2(house_day_kwh)
    h_kwh = hourly_kwh(house_kw_native)
    h_cost = hourly_cost(house_kw_native, rates_native)
    outdoor_f = list(outdoor["drybulb_f"])

    idf_text = st.session_state.idf_text or _default_idf_text()
    dashboard = inspect_idf(idf_text, source_name=str(st.session_state.idf_name))
    pf = _preflight(idf_text, str(st.session_state.idf_name))

    tab_inputs, tab_twin, tab_grid, tab_dr, tab_econ = st.tabs(
        ["Inputs", "Twin replay", "Grid search", "DR event", "Economics"]
    )

    with tab_inputs:
        st.subheader("Upload model + weather + tariff")
        st.caption(
            "Bring your own IDF (assumed calibrated), EPW weather, and pricing. "
            "Fixture demo mode still works with no EnergyPlus."
        )
        u1, u2, u3 = st.columns(3)
        with u1:
            idf_up = st.file_uploader("EnergyPlus IDF", type=["idf", "imf"], key="inputs_idf")
        with u2:
            epw_up = st.file_uploader("Weather EPW", type=["epw"], key="inputs_epw")
        with u3:
            tariff_up = st.file_uploader("Tariff CSV", type=["csv"], key="inputs_tariff")

        p1, p2 = st.columns(2)
        with p1:
            st.number_input(
                "EPW extract month",
                min_value=1,
                max_value=12,
                key="epw_month",
                help="Calendar month used when parsing an uploaded EPW day.",
            )
        with p2:
            st.number_input(
                "EPW extract day",
                min_value=1,
                max_value=31,
                key="epw_day",
                help="Calendar day used when parsing an uploaded EPW day.",
            )
        if idf_up is not None:
            token = (idf_up.name, int(idf_up.size))
            if st.session_state.get("_last_idf_token") != token:
                st.session_state._last_idf_token = token
                st.session_state.idf_text = idf_up.getvalue().decode("utf-8", errors="replace")
                st.session_state.idf_name = idf_up.name
                st.rerun()
            st.success(f"IDF loaded · {st.session_state.idf_name}")
        if epw_up is not None:
            token = (epw_up.name, int(epw_up.size), int(st.session_state.epw_month), int(st.session_state.epw_day))
            if st.session_state.get("_last_epw_token") != token:
                try:
                    outdoor_model = parse_epw_day(
                        epw_up.getvalue().decode("utf-8", errors="replace"),
                        month=int(st.session_state.epw_month),
                        day=int(st.session_state.epw_day),
                        source_name=epw_up.name,
                    )
                    st.session_state._last_epw_token = token
                    st.session_state.outdoor_override = outdoor_model.model_dump()
                    st.session_state.epw_upload_name = epw_up.name
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"EPW parse failed: {exc}")
            elif st.session_state.outdoor_override:
                st.success(f"EPW loaded · {epw_up.name}")
        if tariff_up is not None:
            token = (tariff_up.name, int(tariff_up.size))
            if st.session_state.get("_last_tariff_token") != token:
                try:
                    upload = parse_tariff_csv(
                        tariff_up.getvalue().decode("utf-8", errors="replace"),
                        source_name=tariff_up.name,
                    )
                    st.session_state._last_tariff_token = token
                    st.session_state.rates_override = expand_tariff_to_288(upload)
                    st.session_state.tariff_upload_name = tariff_up.name
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Tariff parse failed: {exc}")
            elif st.session_state.rates_override:
                st.success(f"Tariff loaded · {tariff_up.name}")
        if st.button("Clear uploads", key="inputs_clear_uploads"):
            st.session_state.idf_text = None
            st.session_state.idf_name = MODEL_IDF.name
            st.session_state.outdoor_override = None
            st.session_state.rates_override = None
            st.session_state.epw_upload_name = None
            st.session_state.tariff_upload_name = None
            st.session_state._last_idf_token = None
            st.session_state._last_epw_token = None
            st.session_state._last_tariff_token = None
            st.rerun()

        st.subheader("Hourly weather + electricity price editor")
        st.caption(
            "Spreadsheet-style 24-row day. Units: outdoor dry-bulb °F · rate USD/kWh. "
            "Apply expands rates to the native 5-min (288) grid used by the DSM search."
        )
        editor_df = _hourly_editor_frame(outdoor, rates_native)
        hourly_csv_up = st.file_uploader(
            "Seed editor from hourly CSV (optional)",
            type=["csv"],
            key="inputs_hourly_csv",
            help="Same columns as Download hourly CSV template.",
        )
        if hourly_csv_up is not None:
            token = (hourly_csv_up.name, int(hourly_csv_up.size))
            if st.session_state.get("_last_hourly_csv_token") != token:
                try:
                    temps, hourly_rates = _parse_hourly_csv(
                        hourly_csv_up.getvalue().decode("utf-8", errors="replace")
                    )
                    st.session_state._last_hourly_csv_token = token
                    st.session_state.outdoor_override = {
                        "source_name": hourly_csv_up.name,
                        "month": int(st.session_state.epw_month),
                        "day": int(st.session_state.epw_day),
                        "drybulb_f": temps,
                        "drybulb_c": [(t - 32.0) * 5.0 / 9.0 for t in temps],
                        "location": "hourly CSV upload",
                    }
                    st.session_state.rates_override = _expand_hourly_rates(hourly_rates)
                    st.session_state.tariff_upload_name = hourly_csv_up.name
                    st.success(f"Seeded editor from {hourly_csv_up.name}")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Hourly CSV parse failed: {exc}")
        edited = st.data_editor(
            editor_df,
            hide_index=True,
            width="stretch",
            num_rows="fixed",
            column_config={
                "hour": st.column_config.NumberColumn("Hour", disabled=True, format="%d"),
                "outdoor_drybulb_f": st.column_config.NumberColumn("Outdoor °F", format="%.1f"),
                "rate_usd_per_kwh": st.column_config.NumberColumn("Rate $/kWh", format="%.3f", min_value=0.0),
            },
            key="hourly_inputs_editor",
        )
        a1, a2 = st.columns(2)
        with a1:
            if st.button("Apply hourly weather + rates", type="primary"):
                temps = [float(v) for v in edited["outdoor_drybulb_f"].tolist()]
                hourly_rates = [float(v) for v in edited["rate_usd_per_kwh"].tolist()]
                if len(temps) != 24 or len(hourly_rates) != 24:
                    st.error("Need exactly 24 hourly rows.")
                else:
                    st.session_state.outdoor_override = {
                        "source_name": "hourly_editor",
                        "month": int(st.session_state.epw_month),
                        "day": int(st.session_state.epw_day),
                        "drybulb_f": temps,
                        "drybulb_c": [(t - 32.0) * 5.0 / 9.0 for t in temps],
                        "location": "manual hourly editor",
                    }
                    st.session_state.rates_override = _expand_hourly_rates(hourly_rates)
                    st.success("Applied hourly outdoor °F and illustrative $/kWh to this session.")
                    st.rerun()
        with a2:
            st.download_button(
                "Download hourly CSV template",
                data=editor_df.to_csv(index=False),
                file_name="vibe23_hourly_weather_tariff.csv",
                mime="text/csv",
            )

        st.subheader("Day context (Inputs only)")
        outdoor_src = (
            st.session_state.epw_upload_name
            or (outdoor.get("source_name") if isinstance(outdoor, dict) else None)
            or "fixture outdoor"
        )
        rate_src = st.session_state.tariff_upload_name or "fixture TOU"
        idf_src = st.session_state.idf_name
        st.caption(
            f"**Data vintage:** IDF `{idf_src}` · outdoor `{outdoor_src}` · rates `{rate_src}`. "
            "Outdoor °F and $/kWh refresh immediately after EPW/tariff upload or Apply. "
            "Hourly kWh still comes from the fixture EnergyPlus day and only changes after a re-simulation."
        )
        st.plotly_chart(
            outdoor_kwh_cost_figure(
                hourly_kwh=h_kwh,
                outdoor_f=outdoor_f,
                hourly_cost=h_cost,
                title=f"Static extreme-day context · {day.get('label', season_key)}",
                theme="light",
            ),
            width="stretch",
        )

        st.subheader("IDF compatibility")
        v1, v2, v3 = st.columns(3)
        v1.metric("Visualize", "OK" if pf.can_visualize else "Blocked")
        v2.metric("Simulate (runner)", "OK" if pf.can_simulate else "Blocked")
        v3.metric("Zones / Timestep", f"{pf.n_zones} / {pf.declared_timestep or '—'}")
        if pf.blockers:
            st.warning("Blockers:\n- " + "\n- ".join(pf.blockers))
        if pf.warnings:
            st.info("Warnings:\n- " + "\n- ".join(pf.warnings))
        if pf.can_visualize and pf.can_simulate and not pf.warnings:
            st.success("IDF looks compatible with Studio visualize + residential runner paths.")

        st.subheader("Energy-modeler dashboard")
        e = dashboard.envelope
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Floor area", f"{e.floor_ft2:,.0f} ft²")
        c2.metric("WWR", f"{e.wwr_pct:.1f}%" if e.wwr_pct is not None else "—")
        c3.metric("Zones", str(e.n_zones))
        c4.metric("HVAC autosize", "Yes" if dashboard.hvac_autosize else "No")
        c5.metric("Cooling", f"{dashboard.cooling_tons:.1f} ton" if dashboard.cooling_tons else "—")
        c6.metric("Heating kW", f"{(dashboard.heating_capacity_w or 0)/1000:.1f}" if dashboard.heating_capacity_w else "—")
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
        st.write(
            {
                "simulation_control": dashboard.simulation_control.model_dump(),
                "equipment_types": dashboard.equipment_types,
                "zones": dashboard.zone_names,
                "coils": [c.model_dump() for c in dashboard.coils],
            }
        )
        st.caption("Parsed with Pydantic · geometry from BuildingSurface:Detailed (vibe20-style massing).")

        st.subheader("IDF massing (static)")
        if pf.can_visualize:
            geom = _geom_from_text(idf_text)
            mass = idf_massing_figure(geom, zone_temps={}, title=f"IDF massing · {st.session_state.idf_name}", height=480)
            st.plotly_chart(mass, width="stretch")
        else:
            st.warning("Massing unavailable — IDF lacks BuildingSurface:Detailed.")

    with tab_twin:
        st.caption("Animates the **normal (baseline) day** only. Demand-response events live on the DR event tab.")
        _transport("twin", n)
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("House kW", f"{house_kw[step]:.2f}")
        m2.metric("Purchased kW", f"{(purchased or house_kw)[step]:.2f}")
        m3.metric("kWh to now", f"{(purchased_cum_kwh or house_cum_kwh)[step]:.1f}")
        m4.metric("Daily house kWh", f"{house_day_kwh:.1f}")
        m5.metric("Zone °F", f"{temp_f[step]:.2f}")
        m6.metric("Cost to now", f"${bill_series[step]:.2f}", delta=f"day ${net_bill:.2f}")
        st.caption(
            f"Full-day house **{house_day_kwh:.1f} kWh** · purchased **{purchased_day_kwh:.1f} kWh** · "
            f"~{intensity:.3f} kWh/ft²-day · outdoor now ~{outdoor_f[outdoor_hour_index(step, minutes=minutes)]:.1f}°F · "
            f"DSM {_dsm_label(minutes)} ({n} steps)"
        )
        if st.session_state.promoted_candidate_id:
            action = st.session_state.promoted_action or {}
            st.info(
                f"Promoted candidate `{st.session_state.promoted_candidate_id}` · action = {action}. "
                "Twin still animates the fixture baseline trajectory unless a live run provided traces "
                f"(has_trace={bool(st.session_state.promoted_has_trace)})."
            )
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
                title=(
                    f"{st.session_state.season} · Baseline (normal day) · "
                    f"{interval_clock(step, intervals=n)} · {_dsm_label(minutes)}"
                ),
            ),
            width="stretch",
        )
        with st.expander("Temperature-colored massing", expanded=False):
            if pf.can_visualize:
                geom = _geom_from_text(idf_text)
                mass = idf_massing_figure(
                    geom,
                    zone_temps={zone_name: f_to_c(temp_f[step])},
                    title=f"IDF massing · {st.session_state.idf_name}",
                    height=520,
                )
                st.plotly_chart(mass, width="stretch")
            else:
                st.warning("Massing unavailable — IDF lacks BuildingSurface:Detailed. See Inputs → IDF compatibility.")

    with tab_grid:
        st.subheader("Finite thermostat grid search")
        st.markdown(
            "The residential search is intentionally boring and honest: **freeze** experiment state "
            "(model / weather / tariff / EnergyPlus version), **enumerate** a Cartesian product of "
            "thermostat dimensions, **simulate** each candidate as one EnergyPlus subprocess, then "
            "**rank** by billing cost with soft/comfort gates. There is no gradient, no pruning, and "
            "`max_candidates` only truncates from the front of the catalog. Fixture scores are "
            "pre-computed; editing the grid beyond the fixture catalog needs a live EnergyPlus run."
        )

        dims = season_dimension_defaults(season_key)
        for dim in dims:
            key = f"grid_dim_{dim.name}"
            if key not in st.session_state:
                st.session_state[key] = format_dimension_values(dim.values)
            st.text_input(
                f"{dim.name} (comma-separated)",
                key=key,
                help="Edit values to re-enumerate the catalog. Fixture replay scores require a catalog match.",
            )

        form = {dim.name: str(st.session_state.get(f"grid_dim_{dim.name}", "")) for dim in dims}
        try:
            form_dims = dimensions_from_form(form, season=season_key)
            candidates = enumerate_from_form(form, season=season_key)
            enum_ok = True
            enum_err = None
        except ValueError as exc:
            form_dims = dims
            candidates = ()
            enum_ok = False
            enum_err = str(exc)

        st.code(
            algorithm_pseudocode(season=season_key, dims=form_dims, n=len(candidates)),
            language="text",
        )
        if not enum_ok:
            st.error(f"Dimension form invalid: {enum_err}")
        else:
            st.metric("Enumerated catalog N", len(candidates))
            st.table(
                [
                    {
                        "ordinal": c.ordinal,
                        "id": c.candidate_id,
                        "action": dict(c.action),
                    }
                    for c in candidates
                ]
            )

        matches_fixture = form_matches_fixture_catalog(form, season=season_key) if enum_ok else False
        if ranking is None:
            st.warning("No ranking JSON available for this season.")
        elif not matches_fixture:
            st.caption(
                "Form dimensions do **not** match the fixture catalog — live EnergyPlus scores are required "
                "for this grid. Animation below still replays the committed fixture ranking for training only "
                "when a ranking is loaded; treat costs as illustrative of the fixture search, not your edited grid."
            )
        else:
            src = st.session_state.get("session_ranking_path") or f"fixtures/studio/{season_key}_thermostat_grid_ranking.json"
            st.caption(f"Form matches fixture catalog · ranking source: `{src}`")

        evaluated = int(st.session_state.get("cand_step", 0))
        if evaluated < 0:
            evaluated = 0
        if evaluated > n_cand:
            evaluated = n_cand
            st.session_state.cand_step = n_cand

        _transport(
            "cand",
            n_cand,
            play_label="Run search",
            step_label="Candidates evaluated",
            metric_label="Progress",
            inclusive_end=True,
            show_clock=False,
        )

        progress = search_progress_state(anim_rows, evaluated)
        ring_col, conv_col = st.columns([1, 1.4])
        with ring_col:
            st.plotly_chart(
                search_progress_ring(
                    progress["fraction"],
                    label=f"{evaluated} / {n_cand} candidates",
                    sublabel="EnergyPlus search replay",
                ),
                width="stretch",
            )
        with conv_col:
            costs: list[float | None] = []
            best_so_far: list[float | None] = []
            rejected_indices: list[int] = []
            running_best = float("inf")
            for i, row in enumerate(anim_rows[:evaluated]):
                try:
                    cost_v = float(row.get("billing_cost"))
                except (TypeError, ValueError):
                    cost_v = float("inf")
                feasible = (
                    math.isfinite(cost_v)
                    and bool(row.get("soft_ok"))
                    and bool(row.get("comfort_ok"))
                )
                if not feasible:
                    costs.append(None)
                    rejected_indices.append(i)
                else:
                    costs.append(cost_v)
                    if cost_v < running_best:
                        running_best = cost_v
                best_so_far.append(None if running_best == float("inf") else running_best)
            st.plotly_chart(
                search_convergence_figure(
                    costs=costs,
                    best_so_far=best_so_far,
                    current_index=max(evaluated - 1, 0),
                    rejected_indices=rejected_indices,
                    title="Search convergence ($/day)",
                ),
                width="stretch",
            )

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("EnergyPlus runs", f"{progress['eplus_runs']} / {progress['total_runs']}")
        p2.metric("Feasible / rejected", f"{progress['feasible']} / {progress['rejected']}")
        wall = progress["wall_seconds_so_far"]
        proj = progress["wall_seconds_projected"]
        p3.metric(
            "Wall time",
            f"{wall:.1f}s",
            delta=None if proj is None else f"~{proj:.0f}s projected",
        )
        best_cost = progress["best_cost"]
        p4.metric("Best cost", "—" if best_cost is None else f"${best_cost:.2f}")

        st.caption(
            "What is an iteration? One catalog candidate = one full EnergyPlus day simulation "
            "(plus a shared baseline run). The progress slider is candidates evaluated, not clock time."
        )
        st.code("\n".join(progress["log_lines"]) or "(press Run search)", language="text")

        if st.button("Promote winner to Twin", type="primary", key="promote_winner"):
            row = progress.get("best_row")
            if row is None and ranking:
                win = ranking.get("winner") or {}
                if str(win.get("candidate_id")) == "BASELINE":
                    for cand in ranking.get("rows") or []:
                        if str(cand.get("candidate_id")) != "BASELINE":
                            row = cand
                            break
                else:
                    row = win
            if not row:
                st.warning("No feasible winner yet — advance the search or load a ranking.")
            else:
                st.session_state.promoted_candidate_id = row.get("candidate_id")
                st.session_state.promoted_action = _parse_action(row.get("action_json"))
                st.session_state.promoted_has_trace = False
                st.success(
                    f"Promoted `{st.session_state.promoted_candidate_id}`. "
                    "Twin still uses the fixture baseline kW/°F series — fixture rankings do not carry "
                    "per-candidate traces. Live EnergyPlus runs can attach traces later."
                )
                st.rerun()

        _render_grid_board(session_id, season_key, eplus)

    with tab_dr:
        from vibe23.comfort import degree_hours_abs_delta, degree_hours_outside_band, net_welfare_usd
        from vibe23.residential.thermostat import comfort_ok

        st.subheader(f"Stage 1 thermal — {day.get('label', season_key)}")
        st.caption(
            "Independent playhead from Twin replay — scrub or Play this DR event day on its own clock."
        )
        _transport("dr", n)
        dr_step = int(st.session_state.dr_step)
        end = dr_step + 1

        base_kwh = daily_kwh(list(day["baseline_kw"]))
        event_kwh = daily_kwh(list(day["event_kw"]))
        base_bill = day_bill(list(day["baseline_kw"]), season=season_key)
        event_bill = day_bill(list(day["event_kw"]), season=season_key)
        bill_savings = base_bill - event_bill
        dh_vs_base = degree_hours_abs_delta(list(day["event_temp_f"]), list(day["baseline_temp_f"]))
        band = degree_hours_outside_band(list(day["event_temp_f"]))
        wtp = float(st.session_state.comfort_wtp)
        welfare = net_welfare_usd(bill_savings_usd=bill_savings, degree_hours=dh_vs_base, wtp_usd_per_f_h=wtp)
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Baseline peak kW", f"{max(day['baseline_kw']):.2f}")
        d2.metric("Event peak kW", f"{max(day['event_kw']):.2f}")
        d3.metric("Bill savings $/day", f"${bill_savings:.2f}")
        d4.metric(
            "Net welfare $/day",
            f"${welfare['net_welfare_usd']:.2f}",
            delta=f"comfort −${welfare['comfort_cost_usd']:.2f}",
        )
        st.caption(
            f"Comfort OK (hard band {band['low_f']:.1f}–{band['high_f']:.1f}°F): "
            f"**{comfort_ok(list(day['event_temp_f']))}** · "
            f"|ΔT| vs baseline = **{dh_vs_base:.2f} °F·h** · "
            f"band exceedance = **{band['total_degree_hours']:.2f} °F·h**. "
            f"WTP = ${wtp:.2f}/°F·h (sidebar). Net welfare = bill savings − WTP×°F·h (ILLUSTRATIVE)."
        )
        d5, d6 = st.columns(2)
        d5.metric("Baseline day kWh", f"{base_kwh:.1f}")
        d6.metric("Event day kWh", f"{event_kwh:.1f}", delta=f"{event_kwh - base_kwh:+.1f}")
        base_disp = downsample_mean(list(day["baseline_kw"]), block)
        event_disp = downsample_mean(list(day["event_kw"]), block)
        base_temp = downsample_mean(list(day["baseline_temp_f"]), block)
        event_temp = downsample_mean(list(day["event_temp_f"]), block)
        base_cum = cumulative_kwh(base_disp, dt_hours=dt_hours)
        event_cum = cumulative_kwh(event_disp, dt_hours=dt_hours)
        hx = hours[:end]
        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.07,
            subplot_titles=("Power (kW)", "Cumulative energy (kWh)", "Zone °F"),
        )
        fig.add_trace(go.Scatter(x=hx, y=base_disp[:end], name="Baseline kW", line=dict(color="#9AA7B8")), row=1, col=1)
        fig.add_trace(go.Scatter(x=hx, y=event_disp[:end], name="DR event kW", line=dict(color="#E8A838")), row=1, col=1)
        fig.add_trace(go.Scatter(x=hx, y=base_cum[:end], name="Baseline kWh", line=dict(color="#9AA7B8")), row=2, col=1)
        fig.add_trace(go.Scatter(x=hx, y=event_cum[:end], name="DR kWh", line=dict(color="#E8A838")), row=2, col=1)
        fig.add_trace(go.Scatter(x=hx, y=base_temp[:end], name="Baseline °F", line=dict(color="#8FB8FF")), row=3, col=1)
        fig.add_trace(go.Scatter(x=hx, y=event_temp[:end], name="DR °F", line=dict(color="#FF6B6B")), row=3, col=1)
        if season_key == "summer":
            fig.add_vrect(x0=15, x1=20, fillcolor="#E8A838", opacity=0.12, line_width=0, row=1, col=1)
        else:
            fig.add_vrect(x0=6, x1=9, fillcolor="#8FB8FF", opacity=0.12, line_width=0, row=1, col=1)
        vline_x = hours[dr_step] if hours else 0.0
        for r in (1, 2, 3):
            fig.add_vline(x=vline_x, line=dict(color="#64748B", width=1, dash="dot"), row=r, col=1)
        fig.update_layout(height=560, legend=dict(orientation="h"), paper_bgcolor="rgba(0,0,0,0)")
        fig.update_xaxes(range=[0, 24])
        st.plotly_chart(fig, width="stretch")

    with tab_econ:
        from vibe23.economics import (
            LifecycleAssumptions,
            default_day_type_weights,
            distribution_bands,
            lifecycle_report,
            methods_appendix_markdown,
            price_discovery_summary,
            residential_day_value_stack,
            tornado_one_at_a_time,
            weighted_annual_from_days,
        )
        from vibe23.residential.constants import SUMMER_TOU_PEAK_END, SUMMER_TOU_PEAK_START

        _render_battery_lab(day, season_key)

        st.subheader("What price / incentive is required?")
        st.caption(
            "ILLUSTRATIVE inverse economics on the active demo day — not a calibrated ROI tool. "
            "Never annualize one extreme day ×365 without explicit day-type weights. "
            "Assumptions live in the sidebar."
        )
        base_kw = list(day["baseline_kw"])
        event_kw = list(day["event_kw"])
        base_bill = day_bill(base_kw, season=season_key)
        event_bill = day_bill(event_kw, season=season_key)
        tou_save = base_bill - event_bill

        def _period_kwh(kw: list[float], start: float, end: float) -> float:
            nn = len(kw)
            total = 0.0
            for i, v in enumerate(kw):
                hour = (i + 1) * 24.0 / max(nn, 1)
                if start < hour <= end:
                    total += float(v) * dt_hours
            return total

        if season_key == "summer":
            p0, p1 = SUMMER_TOU_PEAK_START, SUMMER_TOU_PEAK_END
        else:
            p0, p1 = 6.0, 9.0
        kwh_shed = max(0.0, _period_kwh(base_kw, p0, p1) - _period_kwh(event_kw, p0, p1))
        event_hours = max(0.25, p1 - p0)

        target_event = float(st.session_state.econ_target)
        net_capex = float(st.session_state.econ_capex)
        cycles_yr = float(st.session_state.econ_cycles)
        include_dr = bool(st.session_state.econ_incl_dr)
        include_res = bool(st.session_state.econ_incl_res)
        dr_pay = float(st.session_state.econ_dr_pay)
        res_val = float(st.session_state.econ_res)
        annual_arb = float(st.session_state.econ_annual_arb)

        off_peak = 0.08
        eta_rt = float(st.session_state.eta) ** 2
        disc = price_discovery_summary(
            kwh_shed=max(kwh_shed, 1e-6),
            event_hours=event_hours,
            tou_savings_usd=tou_save,
            capacity_kwh=float(st.session_state.capacity_kwh),
            eta_rt=eta_rt,
            net_capex_usd=net_capex,
            off_peak=off_peak,
            targets_usd=(2.0, float(target_event), 10.0),
            cycles_per_year=cycles_yr,
            payback_years=10.0,
        )
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("TOU bill save $/day", f"${tou_save:.2f}")
        e2.metric("Peak-window kWh shed", f"{kwh_shed:.2f}")
        row = next(
            r for r in disc["incentive_table"] if abs(float(r["target_usd_per_event"]) - float(target_event)) < 1e-9
        )
        e3.metric("Required $/kWh shed", f"${float(row['required_usd_per_kwh_shed']):.2f}")
        br = disc["bess_arbitrage_breakeven"]
        e4.metric("Peak $/kWh for 10-yr arb", f"${float(br['required_peak_usd_per_kwh']):.2f}")

        stack = residential_day_value_stack(
            tou_arbitrage_usd=tou_save,
            dr_incentive_usd=dr_pay,
            include_dr_incentive=include_dr,
            resilience_usd=res_val,
            include_resilience=include_res,
        )
        st.write("Value stack (enabled layers only)")
        st.table(stack["waterfall"])
        st.metric("Stack total $/day", f"${float(stack['total_usd']):.2f}")

        st.subheader("BESS lifecycle (arbitrage cashflows only)")
        life = lifecycle_report(
            LifecycleAssumptions(
                net_capex_usd=net_capex,
                annual_arbitrage_usd=annual_arb,
                discount_rate=0.07,
                lifetime_years=10,
                warranty_years=10,
                throughput_kwh_per_year=float(st.session_state.capacity_kwh) * 0.85 * cycles_yr,
                tax_credit_frac=0.0,
                tax_credit_evidence="NONE",
            )
        )
        l1, l2, l3 = st.columns(3)
        l1.metric("NPV $", f"${float(life['npv_usd']):.0f}")
        pb = life["simple_payback_years"]
        l2.metric("Simple payback yr", "—" if pb is None else f"{float(pb):.1f}")
        lcos = life["lcos_usd_per_kwh"]
        l3.metric("LCOS $/kWh", "—" if lcos is None else f"${float(lcos):.3f}")
        st.warning(life["warning"])

        st.subheader("Uncertainty — weighted days + tornado")
        weights = default_day_type_weights()
        day_vals = {
            "summer_hot": tou_save if season_key == "summer" else 0.4,
            "summer_typical": max(0.0, tou_save * 0.35) if season_key == "summer" else 0.2,
            "winter_design": tou_save if season_key == "winter" else 1.0,
            "winter_typical": 0.5,
            "shoulder": 0.15,
        }
        annual = weighted_annual_from_days(day_vals, weights)
        samples = [annual["annual_usd"] * m for m in (0.4, 0.6, 0.8, 1.0, 1.1, 1.3, 1.6)]
        bands = distribution_bands(samples)
        u1, u2, u3, u4 = st.columns(4)
        u1.metric("Weighted annual $", f"${annual['annual_usd']:.0f}")
        u2.metric("P10", f"${bands['p10_usd']:.0f}")
        u3.metric("P50", f"${bands['p50_usd']:.0f}")
        u4.metric("P90", f"${bands['p90_usd']:.0f}")
        st.caption(f"Day-type weights (days/yr): {weights}")

        def _eval(params: dict) -> float:
            return float(params["tou_save"]) * float(params["event_days"]) + float(params["dr_pay"]) * float(
                params["event_days"]
            ) * (1.0 if include_dr else 0.0) - 0.01 * float(params["capex"])

        tornado = tornado_one_at_a_time(
            {
                "tou_save": max(tou_save, 0.01),
                "event_days": 20.0,
                "dr_pay": dr_pay,
                "capex": net_capex,
            },
            evaluate=_eval,
        )
        st.table(
            [
                {
                    "param": b["param"],
                    "low $": round(float(b["low_usd"]), 1),
                    "high $": round(float(b["high_usd"]), 1),
                    "swing $": round(float(b["swing_usd"]), 1),
                }
                for b in tornado["bars"]
            ]
        )

        appendix = methods_appendix_markdown(
            day=day,
            equipment=equipment_provenance(),
            battery={
                "capacity_kwh": float(st.session_state.capacity_kwh),
                "max_power_kw": float(st.session_state.max_power_kw),
                "eta": float(st.session_state.eta),
            },
            economics={
                "tou_save_usd": tou_save,
                "kwh_shed": kwh_shed,
                "price_discovery": disc,
                "value_stack_total": stack["total_usd"],
                "lifecycle_npv": life["npv_usd"],
                "weighted_annual_usd": annual["annual_usd"],
                "bands": bands,
            },
        )
        st.download_button(
            "Download methods appendix (.md)",
            data=appendix,
            file_name="vibe23_methods_appendix.md",
            mime="text/markdown",
            key="econ_methods_dl",
        )
        with st.expander("Methods appendix preview"):
            st.code(appendix, language="markdown")

    need_rerun = False
    need_rerun |= _queue_tick("twin", n, seconds=PLAY_SECONDS / float(max(n, 1)))
    need_rerun |= _queue_tick("dr", n, seconds=PLAY_SECONDS / float(max(n, 1)))
    need_rerun |= _queue_tick("cand", n_cand, seconds=CAND_SECONDS)
    if need_rerun:
        st.rerun()


if __name__ == "__main__":
    main()
