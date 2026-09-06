"""Vibe 23 Residential DSM Studio — Streamlit console.

Live EnergyPlus on the Render worker powers Grid search / Twin / Flex.
No synthetic proxy rankings are shown as results — without a configured
worker or session run those tabs say EnergyPlus not ready.

Launch (Windows / Linux / macOS)::

    pip install -e ".[studio]"
    cp .env.example .env   # set EPLUS_WORKER_URL + EPLUS_WORKER_API_KEY
    # Preferred on Windows (pins Python 3.12 + Streamlit 1.59.2):
    .\\scripts\\run_studio.ps1
    # Or:
    streamlit run streamlit_app.py

Human guide: AGENTS.md · demo IDF/EPW under ``src/vibe23/assets/`` (mirrored in ``model/``)
"""
from __future__ import annotations

import hashlib
import importlib
import io
import json
import math
import os
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from vibe23.battery import BatteryParams
from vibe23.envfile import load_energyplus_env
from vibe23.residential.constants import INTERVALS_PER_DAY, MAX_COOL_F, MAX_HEAT_F
from vibe23.residential.model import (
    DEFAULT_EPW_NAME,
    MODEL_IDF,
    ensure_demo_assets,
    equipment_provenance,
)
from vibe23.residential.tariffs import summer_tou_hourly, winter_tou_hourly
from vibe23.tariff import TariffEvidence, TariffScenario
import vibe23.energyplus_worker as _eplus_worker
import vibe23.studio.charts as _studio_charts
import vibe23.studio.units as _studio_units

# Long-lived Streamlit processes cache package imports; reload so helper
# signature / symbol changes apply without a full process restart.
_eplus_worker = importlib.reload(_eplus_worker)
_studio_charts = importlib.reload(_studio_charts)
_studio_units = importlib.reload(_studio_units)

from vibe23.studio.charts import (  # noqa: E402
    cost_bar_figure,
    hour_axis,
    kwh_bar_figure,
    outdoor_kwh_cost_figure,
    playback_figure,
    qtable_heatmap_figure,
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
    f_to_c,
    hourly_cost,
    hourly_kwh,
    interval_clock,
    load_outdoor_day,
    load_season_day,
    outdoor_hour_index,
    run_battery_on_load,
)
from vibe23.studio.units import (  # noqa: E402
    area_unit,
    c_to_f,
    comfort_wtp_label,
    display_area,
    display_temp,
    display_temp_series,
    energy_intensity,
    intensity_unit,
    normalize_units,
    temp_unit,
)
from vibe23.studio.idf_geometry import idf_massing_figure, parse_idf_geometry
from vibe23.studio.idf_inspect import inspect_idf
from vibe23.studio.idf_preflight import preflight_idf
from vibe23.studio.search_progress import (
    candidate_rows_for_animation,
    format_dimension_values,
    load_grid_ranking,
    load_twin_export,
    qtable_matrix,
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

# Reject any ranking/twin payload that self-declares as algebraic proxy (never show as results).
PROXY_FIXTURE_KIND = "ILLUSTRATIVE_PHYSICS_PROXY"

load_energyplus_env()


def _apply_cloud_secrets() -> None:
    """Pull Streamlit Cloud secrets into os.environ when present (no-op locally)."""
    try:
        secrets = st.secrets  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return
    for key in (
        "EPLUS_WORKER_URL",
        "EPLUS_WORKER_API_KEY",
        "EPLUS_BACKEND",
        "ENERGYPLUS_EXE",
        "ENERGYPLUS_ROOT",
        "ENERGYPLUS_WEATHER",
    ):
        try:
            value = secrets.get(key)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            value = None
        if value is None:
            continue
        text = str(value).strip()
        if text and not os.environ.get(key):
            os.environ[key] = text


def _sync_eplus_backend_env() -> str:
    """Studio is Render-only — always pin worker backend."""
    os.environ["EPLUS_BACKEND"] = "worker"
    st.session_state.eplus_backend = "worker"
    return "worker"


def _live_sim_ready() -> tuple[bool, str]:
    """Return (ready, human label) for live EnergyPlus search buttons."""
    from vibe23.energyplus_worker import worker_configured

    _sync_eplus_backend_env()
    if worker_configured():
        return True, "EnergyPlus worker"
    return False, "worker URL/API key missing"


_WORKER_LIGHT_COLORS = {
    "green": "#22C55E",
    "yellow": "#EAB308",
    "red": "#EF4444",
}
_WORKER_LIGHT_LABELS = {
    "live": "live",
    "starting": "starting",
    "sleeping": "sleeping",
    "unconfigured": "not configured",
}


def _worker_status_cached(*, force: bool = False, quick_timeout: float = 2.5) -> dict:
    """Probe worker with a short TTL so Streamlit reruns stay responsive."""
    # Use reloaded module attribute so long-lived Streamlit picks up new symbols.
    probe_worker_status = getattr(_eplus_worker, "probe_worker_status", None)
    worker_configured = getattr(_eplus_worker, "worker_configured")

    # AppTest / CI: never hit the network.
    if os.environ.get("VIBE23_STUDIO_PLAY_ONCE") == "1":
        if worker_configured():
            return {
                "light": "green",
                "label": "live",
                "try_seconds": 0.0,
                "health": {"ok": True},
                "error": None,
                "cached": True,
            }
        return {
            "light": "red",
            "label": "unconfigured",
            "try_seconds": 0.0,
            "health": None,
            "error": "missing worker env",
            "cached": True,
        }

    if probe_worker_status is None:
        return {
            "light": "red",
            "label": "unconfigured",
            "try_seconds": 0.0,
            "health": None,
            "error": "probe_worker_status missing — restart Studio",
            "cached": True,
        }

    now = time.time()
    cached = st.session_state.get("_worker_status_cache")
    cache_at = float(st.session_state.get("_worker_status_at") or 0.0)
    if st.session_state.get("_worker_light_override") == "yellow":
        return {
            "light": "yellow",
            "label": "starting",
            "try_seconds": 0.0,
            "health": None,
            "error": None,
            "cached": True,
        }
    if (not force) and cached and (now - cache_at) < 20.0:
        return {**cached, "cached": True}
    status = probe_worker_status(quick_timeout=quick_timeout)
    st.session_state._worker_status_cache = status
    st.session_state._worker_status_at = now
    return {**status, "cached": False}


def _render_worker_stoplight(status: dict, *, compact: bool = False) -> None:
    light = str(status.get("light") or "red")
    label = _WORKER_LIGHT_LABELS.get(str(status.get("label") or ""), str(status.get("label") or light))
    color = _WORKER_LIGHT_COLORS.get(light, _WORKER_LIGHT_COLORS["red"])
    size = 12 if compact else 16
    detail = ""
    if not compact and status.get("try_seconds"):
        detail = f" · {float(status['try_seconds']):.1f}s"
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:0.5rem;margin:0.15rem 0 0.35rem 0;">'
        f'<span style="width:{size}px;height:{size}px;border-radius:50%;'
        f'background:{color};box-shadow:0 0 0 2px rgba(0,0,0,0.08);'
        f'display:inline-block;flex-shrink:0;" title="EnergyPlus worker"></span>'
        f'<span style="font-size:0.9rem;">Worker <strong>{label}</strong>{detail}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


_apply_cloud_secrets()

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
        "session_twin_export_path": None,
        "grid_config_fp": None,
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
        "grid_max_candidates": 5,
        "comfort_low_f": MAX_HEAT_F,
        "comfort_high_f": MAX_COOL_F,
        "eplus_backend": "worker",
        "idf_uploaded": False,
        "units": "imperial",
        "epw_upload_name": None,
        "tariff_upload_name": None,
        "epw_bytes": None,
        "worker_jobs": [],
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
    st.session_state.session_twin_export_path = None
    st.session_state.grid_config_fp = None
    st.session_state.comfort_low_f = MAX_HEAT_F
    st.session_state.comfort_high_f = MAX_COOL_F
    st.session_state.grid_max_candidates = 5
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


def _sidebar_battery_params() -> BatteryParams:
    """Battery sized from the sidebar, so a live search scores the box the user configured."""
    power = float(st.session_state.max_power_kw)
    eta = float(st.session_state.eta)
    soc_min = float(st.session_state.soc_min)
    soc_max = float(st.session_state.soc_max)
    initial = min(max(float(st.session_state.initial_soc), soc_min), soc_max)
    return BatteryParams(
        capacity_kwh=float(st.session_state.capacity_kwh),
        max_charge_kw=power,
        max_discharge_kw=power,
        eta_c=eta,
        eta_d=eta,
        soc_min=soc_min,
        soc_max=soc_max,
        initial_soc=initial,
    )


def _live_idf_arg(session_id: str) -> str | None:
    """Path to the browser-uploaded IDF (required). Never falls back to the package model.
    """
    if not st.session_state.get("idf_uploaded"):
        return None
    text = st.session_state.get("idf_text")
    if not text:
        return None
    staged = exports_dir(session_id) / "live_idf"
    staged.mkdir(parents=True, exist_ok=True)
    target = staged / "uploaded.idf"
    target.write_text(str(text), encoding="utf-8")
    return str(target)


def _grid_max_candidates() -> int | None:
    """Catalog truncate for live Render runs. None = full 169."""
    n = int(st.session_state.get("grid_max_candidates") or 169)
    if n >= 169:
        return None
    return max(1, n)


def _grid_candidate_count_label() -> str:
    n = _grid_max_candidates()
    return "169" if n is None else str(n)


def _live_epw_arg(session_id: str) -> str | None:
    """Stage an uploaded EPW for live runs; None → package Golden EPW via find_denver_epw."""
    raw = st.session_state.get("epw_bytes")
    name = st.session_state.get("epw_upload_name") or "upload.epw"
    if not raw:
        return None
    staged = exports_dir(session_id) / "live_epw"
    staged.mkdir(parents=True, exist_ok=True)
    target = staged / Path(str(name)).name
    if not str(target).lower().endswith(".epw"):
        target = staged / "upload.epw"
    target.write_bytes(bytes(raw))
    return str(target)


def _live_tariff_override():
    """Build a TariffScenario from the Inputs editor rates, when present."""
    rates = st.session_state.get("rates_override")
    if not rates:
        return None
    values = [float(v) for v in rates]
    if len(values) != INTERVALS_PER_DAY:
        return None
    return TariffScenario(
        tariff_id="studio_upload_override",
        evidence=TariffEvidence.ILLUSTRATIVE,
        energy_rates_per_kwh=tuple(values),
        demand_rate_per_kw=0.0,
        source_reference="Streamlit Inputs tariff / hourly editor",
        notes="ILLUSTRATIVE_HIGH_VALUE_TOU_TARIFF",
    )


def _remember_worker_job(job_id: str | None, *, candidate_id: str | None = None, status: str = "submitted") -> None:
    if not job_id:
        return
    jobs = list(st.session_state.get("worker_jobs") or [])
    jobs.insert(
        0,
        {
            "job_id": str(job_id),
            "candidate_id": candidate_id,
            "status": status,
            "at": time.strftime("%H:%M:%S"),
        },
    )
    st.session_state.worker_jobs = jobs[:40]


def _grid_config_fingerprint(season_key: str) -> str:
    """Identity of every input a live grid search consumes.

    Stored alongside a live run so stale session ranking / twin paths can be dropped when
    the user changes the battery, comfort band, season, or IDF underneath them.
    """
    idf_text = st.session_state.get("idf_text")
    idf_id = hashlib.sha256(str(idf_text).encode("utf-8")).hexdigest()[:16] if idf_text else "default"
    epw_raw = st.session_state.get("epw_bytes")
    epw_id = hashlib.sha256(bytes(epw_raw)).hexdigest()[:16] if epw_raw else "package"
    rates = st.session_state.get("rates_override")
    rates_id = (
        hashlib.sha256(json.dumps([float(v) for v in rates]).encode("utf-8")).hexdigest()[:16]
        if rates
        else "season_default"
    )
    payload = {
        "season": season_key,
        "attach_battery": bool(st.session_state.attach_battery),
        "battery": _sidebar_battery_params().to_dict(),
        "comfort_low_f": float(st.session_state.comfort_low_f),
        "comfort_high_f": float(st.session_state.comfort_high_f),
        "max_candidates": _grid_max_candidates() or 169,
        "idf": idf_id,
        "epw": epw_id,
        "rates": rates_id,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _render_zone_drift_sliders(*, units: str, t_unit: str) -> None:
    """Unit-aware allowable zone temp band (stored internally as °F)."""
    st.caption(
        f"Hard FAIL gate for ranking — zone must stay inside this band "
        f"(display {t_unit}; EnergyPlus scoring stays °F)."
    )
    if units == "metric":
        low_c = st.slider(
            f"Allowable zone low {t_unit} (FAIL below)",
            display_temp(60.0, "metric"),
            display_temp(72.0, "metric"),
            value=display_temp(float(st.session_state.comfort_low_f), "metric"),
            step=0.25,
            help="Cells whose zone temp dips below this FAIL comfort.",
        )
        high_c = st.slider(
            f"Allowable zone high {t_unit} (FAIL above)",
            display_temp(72.0, "metric"),
            display_temp(85.0, "metric"),
            value=display_temp(float(st.session_state.comfort_high_f), "metric"),
            step=0.25,
            help="Cells whose zone temp drifts above this FAIL comfort.",
        )
        st.session_state.comfort_low_f = c_to_f(float(low_c))
        st.session_state.comfort_high_f = c_to_f(float(high_c))
    else:
        st.slider(
            f"Allowable zone low {t_unit} (FAIL below)",
            60.0,
            72.0,
            step=0.5,
            key="comfort_low_f",
            help="Cells whose zone temp dips below this FAIL comfort.",
        )
        st.slider(
            f"Allowable zone high {t_unit} (FAIL above)",
            72.0,
            85.0,
            step=0.5,
            key="comfort_high_f",
            help="Cells whose zone temp drifts above this FAIL comfort.",
        )


def _invalidate_stale_live_run(season_key: str) -> bool:
    """Drop live-run artifact paths whose inputs no longer match the sidebar.

    Returns True when a stale live run was cleared, so the caller can say so.
    """
    if not st.session_state.get("session_ranking_path"):
        return False
    current = _grid_config_fingerprint(season_key)
    if st.session_state.get("grid_config_fp") == current:
        return False
    st.session_state.session_ranking_path = None
    st.session_state.session_twin_export_path = None
    st.session_state.grid_config_fp = None
    st.session_state.promoted_has_trace = False
    return True


def _record_live_run(season_key: str, out_root) -> None:
    st.session_state.session_ranking_path = str(out_root / "ranking.json")
    st.session_state.session_twin_export_path = str(out_root / "twin_export.json")
    st.session_state.grid_config_fp = _grid_config_fingerprint(season_key)


def _run_live_campaign(
    *,
    session_id: str,
    season_key: str,
    live_ready: bool,
    live_label: str,
    max_candidates: int | None,
) -> None:
    """Submit thermostat grid search to the EnergyPlus worker and stash session artifacts."""
    idf_path = _live_idf_arg(session_id)
    if not idf_path:
        st.error("Upload an IDF on **Inputs** first.")
        return
    if not live_ready:
        st.error("Worker not ready — wake it and check API key secrets.")
        return
    try:
        from vibe23.residential.campaign import run_thermostat_grid

        n_label = "169" if max_candidates is None or int(max_candidates) >= 169 else str(int(max_candidates))
        out = exports_dir(session_id) / "studio_grid" / season_key
        epw_path = _live_epw_arg(session_id)
        tariff = _live_tariff_override()

        def _on_progress(event: dict) -> None:
            _remember_worker_job(
                event.get("worker_job_id"),
                candidate_id=str(event.get("candidate_id") or ""),
                status=str(event.get("phase") or "running"),
            )

        with st.spinner(f"{n_label}-cell campaign on EnergyPlus worker…"):
            result = run_thermostat_grid(
                season=season_key,
                output_root=out,
                max_candidates=max_candidates,
                comfort_low_f=float(st.session_state.comfort_low_f),
                comfort_high_f=float(st.session_state.comfort_high_f),
                attach_battery=bool(st.session_state.attach_battery),
                battery_params=_sidebar_battery_params(),
                idf=idf_path,
                epw=epw_path,
                tariff=tariff,
                store_traces=True,
                progress_callback=_on_progress,
            )
        _record_live_run(season_key, out)
        ranking_payload = result.get("ranking") or {}
        st.session_state.cand_step = len(candidate_rows_for_animation(ranking_payload))
        win = ranking_payload.get("winner") or {}
        if win:
            st.session_state.promoted_candidate_id = win.get("candidate_id")
            st.session_state.promoted_action = _parse_action(win.get("action_json"))
            st.session_state.promoted_has_trace = bool(
                ((result.get("twin_export") or {}).get("winner") or {}).get("facility_kw")
            )
        st.success(f"Live search finished via {live_label} · {out}")
        st.rerun()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Live grid failed: {exc}")


def _is_live_ranking() -> bool:
    """True when the loaded ranking came from this session's live EnergyPlus run."""
    return bool(st.session_state.get("session_ranking_path"))


def _payload_is_proxy(payload: dict | None) -> bool:
    return str((payload or {}).get("fixture_kind") or "") == PROXY_FIXTURE_KIND


def _eplus_status_banner(live_ready: bool, live_label: str) -> None:
    if live_ready:
        st.success(f"EnergyPlus ready · {live_label}")
    else:
        st.error(
            "EnergyPlus worker not ready — set `EPLUS_WORKER_URL` + `EPLUS_WORKER_API_KEY`, "
            "then open [https://vibe23-energyplus-worker.onrender.com/]"
            "(https://vibe23-energyplus-worker.onrender.com/) or use **Wake worker** in the sidebar."
        )


def _load_session_ranking(season_key: str) -> dict | None:
    """Live session ranking only — never fall back to committed proxy fixtures."""
    path = st.session_state.get("session_ranking_path")
    if not path:
        return None
    try:
        payload = load_grid_ranking(season_key, path=path)
    except Exception:  # noqa: BLE001
        return None
    if _payload_is_proxy(payload):
        return None
    return payload


def _load_session_twin_export(season_key: str) -> dict | None:
    """Live session twin traces only — never fall back to committed proxy fixtures."""
    path = st.session_state.get("session_twin_export_path")
    if not path:
        return None
    try:
        payload = load_twin_export(season_key, path=path)
    except Exception:  # noqa: BLE001
        return None
    if _payload_is_proxy(payload):
        return None
    return payload


def _centers_from_row(row: object) -> tuple[float, float] | None:
    """Extract (pre_center_f, event_center_f) from a ranking row for Q-table highlights."""
    if not isinstance(row, dict):
        return None
    action = _parse_action(row.get("action_json"))
    try:
        pre = float(action.get("pre_center_f", row.get("pre_center_f")))
        event = float(action.get("event_center_f", row.get("event_center_f")))
    except (TypeError, ValueError):
        return None
    return (pre, event)


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



def main() -> None:
    _init_state()
    if st.session_state.pop("_pending_clear", False):
        _clear_session()
    session_id = _ensure_session()
    try:
        ensure_demo_assets(download_if_missing=True)
    except FileNotFoundError as exc:
        st.warning(f"Demo IDF/EPW not available yet: {exc}")

    season_key = _season_key()
    _sync_epw_day_defaults(season_key)
    day = _day(season_key)
    rates_native = _rates_for_season(season_key)
    outdoor = st.session_state.outdoor_override or _outdoor(season_key)

    live_ready, live_label = _live_sim_ready()

    units = normalize_units(st.session_state.get("units"))
    t_unit = temp_unit(units)
    a_unit = area_unit(units)
    i_unit = intensity_unit(units)
    prov = equipment_provenance()

    st.title("Vibe 23 — Residential DSM Studio")
    worker_status = _worker_status_cached()
    _render_worker_stoplight(worker_status, compact=True)
    st.caption(
        f"HYPOTHETICAL_GL14_TUNED_DEMO_MODEL · {prov['equipment']} · "
        f"~{display_area(DEMO_FLOOR_FT2, units):,.0f} {a_unit} · "
        f"{'EnergyPlus ready' if live_ready else 'EnergyPlus not ready'} · {units}"
    )
    st.markdown(
        "[AGENTS.md](https://github.com/bbartling/py-bacnet-stacks-playground/blob/develop/vibe_code_apps_23/AGENTS.md)"
        f" · `{MODEL_IDF.name}` · `{DEFAULT_EPW_NAME}` · "
        "[Worker API docs](https://vibe23-energyplus-worker.onrender.com/docs)"
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
            help="Coarsen day replay for DSM viewing when live traces are loaded. Native sim is 5-min / 288.",
        )
        st.caption(
            f"Session `{session_id[:8]}…` · per-browser workspace under temp "
            f"`vibe23/{session_id[:8]}…` (uploads/exports isolated; Clear session rotates id). "
            "Shared Streamlit process — isolation, not a login wall."
        )
        st.radio(
            "Display units",
            ["imperial", "metric"],
            format_func=lambda u: "Imperial (°F, ft²)" if u == "imperial" else "Metric (°C, m²)",
            key="units",
            horizontal=True,
            help="Display only — EnergyPlus traces stay native; charts/metrics convert for viewing.",
        )
        st.divider()
        with st.expander("EnergyPlus worker", expanded=True):
            st.session_state.eplus_backend = "worker"
            os.environ["EPLUS_BACKEND"] = "worker"
            live_ready, live_label = _live_sim_ready()
            worker_status = _worker_status_cached()
            _render_worker_stoplight(worker_status)
            st.caption(
                "Green = live · Yellow = starting · Red = sleeping / missing config"
            )
            st.info(
                "EnergyPlus worker runs on **Render free tier** and sleeps when idle — "
                "use **Wake worker** (cold start ~30–90s). Source: "
                "[vibe23-energyplus-worker](https://github.com/bbartling/vibe23-energyplus-worker)."
            )
            st.markdown(
                "**API UI (Swagger):** "
                "[https://vibe23-energyplus-worker.onrender.com/docs]"
                "(https://vibe23-energyplus-worker.onrender.com/docs)  \n"
                "Health: [ /healthz ](https://vibe23-energyplus-worker.onrender.com/healthz)"
            )
            with st.expander("How to use Swagger /docs", expanded=False):
                st.markdown(
                    "1. Wake the worker (stoplight green) or open `/docs` and wait through cold start.\n"
                    "2. Click **Authorize**, paste the bearer token below (Swagger adds `Bearer`).\n"
                    "3. Try `GET /healthz` (no auth) or `POST /v1/jobs` with an IDF + EPW upload.\n"
                    "4. Poll `GET /v1/jobs/{id}` then download `/v1/jobs/{id}/results`."
                )
                api_key = (os.environ.get("EPLUS_WORKER_API_KEY") or "").strip()
                if api_key:
                    st.caption("Learning hint — worker API key for Authorize (do not share publicly):")
                    st.code(api_key, language=None)
                else:
                    st.warning("EPLUS_WORKER_API_KEY missing — set it in `.env.local` or Streamlit secrets.")
            if os.environ.get("EPLUS_WORKER_URL"):
                st.caption(
                    f"Worker URL configured · API key "
                    f"{'set' if os.environ.get('EPLUS_WORKER_API_KEY') else 'MISSING'} · "
                    "cold start ~30–90s"
                )
                c_wake, c_refresh = st.columns(2)
                with c_refresh:
                    if st.button("Refresh status", key="refresh_worker_status"):
                        st.session_state.pop("_worker_light_override", None)
                        _worker_status_cached(force=True)
                        st.rerun()
                with c_wake:
                    if st.button("Wake worker", key="wake_eplus_worker"):
                        EnergyPlusWorkerError = _eplus_worker.EnergyPlusWorkerError
                        ensure_worker_awake = _eplus_worker.ensure_worker_awake

                        st.session_state._worker_light_override = "yellow"
                        with st.spinner("Waking worker (yellow = starting)…"):
                            try:
                                wake = ensure_worker_awake()
                                health = wake.get("health") or {}
                                st.session_state.pop("_worker_light_override", None)
                                st.session_state._worker_status_cache = {
                                    "light": "green",
                                    "label": "live",
                                    "try_seconds": float(wake.get("try_seconds") or 0.0),
                                    "health": health,
                                    "error": None,
                                }
                                st.session_state._worker_status_at = time.time()
                                if wake.get("woke_from_sleep"):
                                    st.success(
                                        f"Woke in {wake['wall_seconds']}s · "
                                        f"E+ {health.get('energyplus_version', '?')}"
                                    )
                                else:
                                    st.success(
                                        f"Awake ({wake['try_seconds']}s) · "
                                        f"E+ {health.get('energyplus_version', '?')}"
                                    )
                            except EnergyPlusWorkerError as exc:
                                st.session_state.pop("_worker_light_override", None)
                                st.session_state._worker_status_cache = {
                                    "light": "red",
                                    "label": "sleeping",
                                    "try_seconds": 0.0,
                                    "health": None,
                                    "error": str(exc)[:300],
                                }
                                st.session_state._worker_status_at = time.time()
                                st.error(f"Wake failed: {exc}")
            with st.expander("Worker job queue", expanded=False):
                st.caption(
                    "Worker runs **one job at a time** (queued → running → done). "
                    "Campaign cells enqueue sequentially; this session lists recent job ids."
                )
                session_jobs = list(st.session_state.get("worker_jobs") or [])
                if session_jobs:
                    st.dataframe(
                        pd.DataFrame(session_jobs)[["at", "status", "candidate_id", "job_id"]],
                        hide_index=True,
                        width="stretch",
                    )
                else:
                    st.caption("No jobs from this browser session yet.")
                if st.button("Refresh worker queue", key="refresh_worker_jobs"):
                    try:
                        payload = _eplus_worker.list_jobs(limit=15)
                        queue = payload.get("queue") or {}
                        st.session_state._worker_jobs_remote = payload
                        st.info(
                            f"Queue · queued={queue.get('queued')} · running={queue.get('running')} · "
                            f"max={queue.get('max_concurrent')}"
                        )
                    except Exception as exc:  # noqa: BLE001
                        st.warning(
                            f"Could not list remote jobs (worker may need redeploy with GET /v1/jobs): {exc}"
                        )
                remote = st.session_state.get("_worker_jobs_remote") or {}
                remote_jobs = remote.get("jobs") or []
                if remote_jobs:
                    rows = [
                        {
                            "status": j.get("status"),
                            "job_id": str(j.get("job_id") or "")[:8] + "…",
                            "created": str(j.get("created_at") or "")[:19],
                            "wall_s": j.get("wall_seconds"),
                        }
                        for j in remote_jobs[:12]
                    ]
                    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.divider()
        st.header("Demo day")
        st.radio(
            "Season",
            ["Summer hot day (Jul 15)", "Winter design cold (Jan 3)"],
            key="season",
            help="Jul 15 hot-afternoon flex · Jan 3 near-design cold. "
            "Campaign runs the thermostat search; Grid flex replays the day and compares baseline vs winner.",
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
                comfort_wtp_label(units),
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
        with st.expander("Zone drift + catalog size", expanded=True):
            _render_zone_drift_sliders(units=units, t_unit=t_unit)
            st.select_slider(
                "Catalog size (cells)",
                options=[2, 5, 13, 26, 169],
                key="grid_max_candidates",
                help=(
                    "Smoke sizes (2–26) for testing; 169 = full 13×13 grid. "
                    "Each cell is one EnergyPlus day on the worker (+ baseline)."
                ),
            )
            st.caption(
                f"Sidebar smoke button → **{_grid_candidate_count_label()}** candidate day(s) + baseline. "
                "Full-grid button always runs **169**."
            )
        st.divider()
        st.info("Upload IDF / EPW / tariff on **Inputs**.")
        st.caption(
            f"{prov['equipment']} · {prov['nominal_tons']} ton · "
            f"COP {prov['cooling_cop']}/{prov['heating_cop']}"
        )

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

    stale_live_run = _invalidate_stale_live_run(season_key)
    ranking = _load_session_ranking(season_key)
    anim_rows = candidate_rows_for_animation(ranking) if ranking else []
    n_cand = len(anim_rows)
    has_live_ranking = ranking is not None and _is_live_ranking()

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

    # Twin / flex animate only live EnergyPlus twin_export from this session.
    twin_export = _load_session_twin_export(season_key)
    has_live_twin = twin_export is not None and bool(st.session_state.get("session_twin_export_path"))
    winner_trace = (twin_export or {}).get("winner") or {}
    baseline_trace = (twin_export or {}).get("baseline") or {}
    zone_name = "ZONE ONE"
    twin_trace_id: str | None = None
    purchased_trace = None
    soc_trace = None

    if has_live_twin and len(baseline_trace.get("facility_kw") or []) == INTERVALS_PER_DAY:
        house_kw_native = [float(v) for v in baseline_trace["facility_kw"]]
        temps = baseline_trace.get("zone_temp_f") or []
        temp_f_native = (
            [float(v) for v in temps]
            if len(temps) == INTERVALS_PER_DAY
            else list(day["baseline_temp_f"])
        )
    else:
        house_kw_native = list(day["baseline_kw"])
        temp_f_native = list(day["baseline_temp_f"])
    n_native = len(house_kw_native)

    if (
        has_live_twin
        and st.session_state.promoted_has_trace
        and len(winner_trace.get("facility_kw") or []) == n_native
    ):
        house_kw_native = [float(v) for v in winner_trace["facility_kw"]]
        temps = winner_trace.get("zone_temp_f") or []
        if len(temps) == n_native:
            temp_f_native = [float(v) for v in temps]
        twin_trace_id = str(winner_trace.get("candidate_id") or st.session_state.promoted_candidate_id or "winner")
        pk = winner_trace.get("purchased_kw") or []
        sc = winner_trace.get("soc") or []
        if len(pk) == n_native and len(sc) == n_native:
            purchased_trace = [float(v) for v in pk]
            soc_trace = [100.0 * float(s) for s in sc]

    batt = None
    purchased_native = None
    soc_pct_native = None
    if st.session_state.attach_battery:
        if purchased_trace is not None:
            # Prefer the co-optimized dispatch that the search itself scored.
            purchased_native = purchased_trace
            soc_pct_native = soc_trace
        else:
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
    if batt:
        net_bill = float(batt["billing_cost"])
    elif purchased_native is not None:
        net_bill = day_bill(purchased_native, season=season_key)
    else:
        net_bill = house_bill
    intensity = energy_intensity(house_day_kwh, floor_ft2=DEMO_FLOOR_FT2, units=units)
    h_kwh = hourly_kwh(house_kw_native)
    h_cost = hourly_cost(house_kw_native, rates_native)
    outdoor_f = list(outdoor["drybulb_f"])

    idf_text = st.session_state.idf_text or _default_idf_text()
    dashboard = inspect_idf(idf_text, source_name=str(st.session_state.idf_name))
    pf = _preflight(idf_text, str(st.session_state.idf_name))

    tab_inputs, tab_campaign, tab_flex, tab_econ = st.tabs(
        ["Inputs", "Campaign", "Grid flex", "Economics"]
    )

    with tab_inputs:
        st.subheader("Upload model + weather + tariff")
        st.caption(
            f"Demo: `{MODEL_IDF.name}` · `{DEFAULT_EPW_NAME}` · [AGENTS.md]"
            "(https://github.com/bbartling/py-bacnet-stacks-playground/blob/develop/vibe_code_apps_23/AGENTS.md)"
        )
        if st.button("Load package residential demo IDF", key="load_package_idf"):
            st.session_state.idf_text = MODEL_IDF.read_text(encoding="utf-8", errors="replace")
            st.session_state.idf_name = MODEL_IDF.name
            st.session_state.idf_uploaded = True
            st.session_state._last_idf_token = ("package", MODEL_IDF.name, MODEL_IDF.stat().st_size)
            st.rerun()
        if st.session_state.get("idf_uploaded"):
            st.success(f"IDF ready · {st.session_state.idf_name}")
        st.caption("Campaign / Grid flex fill after a live EnergyPlus search finishes.")
        st.markdown(
            "Worker API UI: [Swagger `/docs`](https://vibe23-energyplus-worker.onrender.com/docs) "
            "· wake via sidebar if sleeping · Authorize with the same bearer key as Streamlit secrets "
            "(session workspace isolates uploads per browser — see sidebar caption)."
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
            st.session_state.idf_uploaded = True
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
                    st.session_state.epw_bytes = epw_up.getvalue()
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
            st.session_state.idf_uploaded = False
            st.session_state.outdoor_override = None
            st.session_state.rates_override = None
            st.session_state.epw_upload_name = None
            st.session_state.tariff_upload_name = None
            st.session_state.epw_bytes = None
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
            f"Outdoor {t_unit} and $/kWh refresh immediately after EPW/tariff upload or Apply. "
            "Hourly kWh still comes from the fixture EnergyPlus day and only changes after a re-simulation."
        )
        outdoor_disp = display_temp_series(list(outdoor_f), units)
        st.plotly_chart(
            outdoor_kwh_cost_figure(
                hourly_kwh=h_kwh,
                outdoor_f=outdoor_disp,
                hourly_cost=h_cost,
                title=f"Static extreme-day context · {day.get('label', season_key)}",
                theme="light",
                temp_unit_label=t_unit,
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
        c1.metric("Floor area", f"{display_area(float(e.floor_ft2), units):,.0f} {a_unit}")
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

        st.divider()
        st.subheader("IDF massing (static)")
        if pf.can_visualize:
            geom = _geom_from_text(idf_text)
            mass = idf_massing_figure(geom, zone_temps={}, title=f"IDF massing · {st.session_state.idf_name}", height=480)
            st.plotly_chart(mass, width="stretch")
        else:
            st.warning("Massing unavailable — IDF lacks BuildingSurface:Detailed.")

    with tab_campaign:
        n_run = _grid_candidate_count_label()
        is_smoke = n_run != "169"
        st.subheader("EnergyPlus campaign")
        _eplus_status_banner(live_ready, live_label)
        st.markdown(
            "**Smoke vs full search:** left button runs the **sidebar catalog** "
            f"(now **{n_run}** cells — default **5** for worker testing). "
            "Right button always runs the **full 169-cell** grid search."
        )
        if season_key == "summer":
            st.caption("TOU hours · pre-window 13:00 · event 16–21 · recovery to 23:00.")
        else:
            st.caption("TOU hours · pre-window 05:00 · event 6–9 · recovery to 12:00.")
        with st.expander("Tutorial — what is the 169-cell thermostat search?", expanded=False):
            st.markdown(
                """
Each **cell** is one EnergyPlus weather-day on the worker with a different thermostat
**center** schedule (heat/cool pair around that center, 2°F deadband).

**How 169 is calculated**

1. Centers are **69.0 … 75.0 °F** in **0.5 °F** steps → **13** values (±3 °F from 72 °F).
2. Search dimensions: **pre-event center** × **event center** → **13 × 13 = 169** candidates.
3. Event hours are fixed to the season TOU peak (not searched). Recovery returns toward 72 °F.
4. Plus one **BASELINE** day (default 71/73) for comparison.
5. Each successful day is scored as **$/day purchased from the grid** (optional battery arbitrage with `restore_final_soc=True`). Comfort FAIL if zone drifts outside the sidebar band. Ranking requires **strict** EnergyPlus `ok` (no fatals/severes).

**When to use which button**

| Button | Use |
|--------|-----|
| Sidebar catalog (2 / 5 / 13 / 26) | Smoke / learn the UI; default **5** for Streamlit.io + free Render |
| Full **169** | Complete grid search — slow on free-tier (baseline + 169 jobs, serial) |

Uploads on **Inputs** (IDF required; EPW + tariff optional) and sidebar battery/drift change the fingerprint — re-run after edits.
                """
            )
        if stale_live_run:
            st.info("Sidebar / season / IDF / weather / tariff changed since the last live search — re-run required.")

        idf_path = _live_idf_arg(session_id)
        if not idf_path:
            st.error("Upload an IDF on **Inputs** before running EnergyPlus.")
        if not live_ready:
            st.error(
                "EnergyPlus worker not ready — set EPLUS_WORKER_URL + EPLUS_WORKER_API_KEY "
                "and open [https://vibe23-energyplus-worker.onrender.com/](https://vibe23-energyplus-worker.onrender.com/)."
            )

        b1, b2 = st.columns(2)
        with b1:
            smoke_label = (
                f"Run smoke catalog ({n_run} cells)"
                if is_smoke
                else "Run sidebar catalog (169)"
            )
            if st.button(
                smoke_label,
                type="primary",
                key="grid_run_sidebar",
                help="Uses sidebar Catalog size. Prefer 5 while testing the worker / Streamlit.io.",
            ):
                _run_live_campaign(
                    session_id=session_id,
                    season_key=season_key,
                    live_ready=live_ready,
                    live_label=live_label,
                    max_candidates=_grid_max_candidates(),
                )
        with b2:
            if st.button(
                "Run full grid search (169 cells)",
                key="grid_run_full_169",
                help="Full 13×13 center search — long on free-tier Render (queued one job at a time).",
            ):
                _run_live_campaign(
                    session_id=session_id,
                    season_key=season_key,
                    live_ready=live_ready,
                    live_label=live_label,
                    max_candidates=None,
                )

        if has_live_ranking:
            src = st.session_state.get("session_ranking_path")
            st.success(f"Live EnergyPlus ranking · `{src}` · N = {n_cand}")
            evaluated = int(st.session_state.get("cand_step", 0))
            if evaluated < 0:
                evaluated = 0
            if evaluated > n_cand:
                evaluated = n_cand
                st.session_state.cand_step = n_cand
            _transport(
                "cand",
                n_cand,
                play_label="Reveal results",
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
                        sublabel="EnergyPlus worker",
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
            qt = qtable_matrix(anim_rows, evaluated=evaluated)
            current = _centers_from_row(anim_rows[evaluated - 1]) if evaluated > 0 else None
            best = _centers_from_row(progress.get("best_row"))
            if qt["pre_centers"] and qt["event_centers"]:
                st.plotly_chart(
                    qtable_heatmap_figure(
                        pre_centers=qt["pre_centers"],
                        event_centers=qt["event_centers"],
                        costs=qt["costs"],
                        current=current,
                        best=best,
                        title=f"Search heatmap ($/day) · {evaluated}/{n_cand}",
                    ),
                    width="stretch",
                )
            if progress.get("best_row"):
                br = progress["best_row"]
                st.success(
                    f"Best so far: `{br.get('candidate_id')}` · ${float(br.get('billing_cost')):.2f}/day"
                )
        else:
            st.info("No live ranking yet — run a catalog above after uploading an IDF on **Inputs**.")

    with tab_flex:
        from vibe23.comfort import degree_hours_abs_delta, degree_hours_outside_band, net_welfare_usd
        from vibe23.residential.thermostat import comfort_ok

        flex_export = twin_export or {}
        fx_base = flex_export.get("baseline") or {}
        fx_win = flex_export.get("winner") or {}
        _eplus_status_banner(live_ready, live_label)

        st.subheader("Day replay")
        if not has_live_twin:
            if live_ready:
                st.info(
                    "No live EnergyPlus traces yet. Upload an IDF on **Inputs**, then run a search on **Campaign**."
                )
            else:
                st.error("EnergyPlus not ready — Grid flex stays empty until the worker is configured.")
        else:
            if twin_trace_id:
                st.caption(f"Promoted winner `{twin_trace_id}` EnergyPlus day (playhead below).")
            else:
                st.caption("EnergyPlus baseline day from this session's campaign.")
            _transport("twin", n)
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("House kW", f"{house_kw[step]:.2f}")
            m2.metric("Purchased kW", f"{(purchased or house_kw)[step]:.2f}")
            m3.metric("kWh to now", f"{(purchased_cum_kwh or house_cum_kwh)[step]:.1f}")
            m4.metric("Daily house kWh", f"{house_day_kwh:.1f}")
            m5.metric(f"Zone {t_unit}", f"{display_temp(temp_f[step], units):.2f}")
            m6.metric("Cost to now", f"${bill_series[step]:.2f}", delta=f"day ${net_bill:.2f}")
            outdoor_now = outdoor_f[outdoor_hour_index(step, minutes=minutes)]
            st.caption(
                f"House **{house_day_kwh:.1f} kWh** · purchased **{purchased_day_kwh:.1f} kWh** · "
                f"~{intensity:.3f} {i_unit} · outdoor ~{display_temp(outdoor_now, units):.1f}{t_unit}"
            )
            if st.session_state.promoted_candidate_id:
                action = st.session_state.promoted_action or {}
                st.caption(f"Promoted `{st.session_state.promoted_candidate_id}` · {action}")
            st.plotly_chart(
                playback_figure(
                    hours=hours,
                    house_kw=house_kw,
                    purchased_kw=purchased,
                    temp_f=display_temp_series(list(temp_f), units),
                    price=rates,
                    soc_pct=soc_pct,
                    cumulative_house_kwh=house_cum_kwh,
                    cumulative_purchased_kwh=purchased_cum_kwh,
                    step=step,
                    title=(
                        f"{st.session_state.season} · "
                        f"{('Winner ' + twin_trace_id) if twin_trace_id else 'Baseline'} · "
                        f"{interval_clock(step, intervals=n)}"
                    ),
                    temp_unit_label=t_unit,
                ),
                width="stretch",
            )

        st.divider()
        st.subheader("Baseline vs winner flex")
        use_export = (
            has_live_twin
            and len(fx_base.get("facility_kw") or []) == n_native
            and len(fx_win.get("facility_kw") or []) == n_native
            and len(fx_base.get("zone_temp_f") or []) == n_native
            and len(fx_win.get("zone_temp_f") or []) == n_native
        )
        if not use_export:
            if live_ready:
                st.info("Need a campaign with winner traces before baseline-vs-flex charts appear.")
            else:
                st.error("EnergyPlus worker not ready.")
        else:
            base_kw_native = [float(v) for v in fx_base["facility_kw"]]
            flex_kw_native = [float(v) for v in fx_win["facility_kw"]]
            base_temp_native = [float(v) for v in fx_base["zone_temp_f"]]
            flex_temp_native = [float(v) for v in fx_win["zone_temp_f"]]
            flex_id = str(fx_win.get("candidate_id") or "winner")
            window = "16–21" if season_key == "summer" else "6–9"
            st.caption(f"Winner `{flex_id}` vs baseline · TOU peak **{window}**.")
            _transport("dr", n)
            dr_step = int(st.session_state.dr_step)
            end = dr_step + 1

            base_kwh = daily_kwh(base_kw_native)
            event_kwh = daily_kwh(flex_kw_native)
            base_bill = day_bill(base_kw_native, season=season_key)
            event_bill = day_bill(flex_kw_native, season=season_key)
            bill_savings = base_bill - event_bill
            dh_vs_base = degree_hours_abs_delta(flex_temp_native, base_temp_native)
            comfort_low = float(st.session_state.comfort_low_f)
            comfort_high = float(st.session_state.comfort_high_f)
            band = degree_hours_outside_band(
                flex_temp_native, low_f=comfort_low, high_f=comfort_high
            )
            wtp = float(st.session_state.comfort_wtp)
            welfare = net_welfare_usd(bill_savings_usd=bill_savings, degree_hours=dh_vs_base, wtp_usd_per_f_h=wtp)
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Baseline peak kW", f"{max(base_kw_native):.2f}")
            d2.metric("Flex peak kW", f"{max(flex_kw_native):.2f}")
            d3.metric("Bill savings $/day", f"${bill_savings:.2f}")
            d4.metric(
                "Net welfare $/day",
                f"${welfare['net_welfare_usd']:.2f}",
                delta=f"comfort −${welfare['comfort_cost_usd']:.2f}",
            )
            dh_scale = (5.0 / 9.0) if units == "metric" else 1.0
            wtp_disp = (wtp / dh_scale) if units == "metric" else wtp
            dh_label = f"{t_unit}·h"
            st.caption(
                f"Comfort OK ({display_temp(band['low_f'], units):.1f}–"
                f"{display_temp(band['high_f'], units):.1f}{t_unit}): "
                f"**{comfort_ok(flex_temp_native, low=comfort_low, high=comfort_high)}** · "
                f"|ΔT| = **{dh_vs_base * dh_scale:.2f} {dh_label}** · "
                f"band = **{band['total_degree_hours'] * dh_scale:.2f} {dh_label}** · "
                f"WTP ${wtp_disp:.2f}/{dh_label}."
            )
            d5, d6 = st.columns(2)
            d5.metric("Baseline day kWh", f"{base_kwh:.1f}")
            d6.metric("Flex day kWh", f"{event_kwh:.1f}", delta=f"{event_kwh - base_kwh:+.1f}")
            base_disp = downsample_mean(base_kw_native, block)
            event_disp = downsample_mean(flex_kw_native, block)
            base_temp = downsample_mean(base_temp_native, block)
            event_temp = downsample_mean(flex_temp_native, block)
            base_cum = cumulative_kwh(base_disp, dt_hours=dt_hours)
            event_cum = cumulative_kwh(event_disp, dt_hours=dt_hours)
            hx = hours[:end]
            fig = make_subplots(
                rows=3,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.07,
                subplot_titles=("Power (kW)", "Cumulative energy (kWh)", f"Zone {t_unit}"),
            )
            fig.add_trace(go.Scatter(x=hx, y=base_disp[:end], name="Baseline kW", line=dict(color="#9AA7B8")), row=1, col=1)
            fig.add_trace(go.Scatter(x=hx, y=event_disp[:end], name="Flex kW", line=dict(color="#E8A838")), row=1, col=1)
            fig.add_trace(go.Scatter(x=hx, y=base_cum[:end], name="Baseline kWh", line=dict(color="#9AA7B8")), row=2, col=1)
            fig.add_trace(go.Scatter(x=hx, y=event_cum[:end], name="Flex kWh", line=dict(color="#E8A838")), row=2, col=1)
            fig.add_trace(
                go.Scatter(
                    x=hx,
                    y=display_temp_series(list(base_temp[:end]), units),
                    name=f"Baseline {t_unit}",
                    line=dict(color="#8FB8FF"),
                ),
                row=3,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=hx,
                    y=display_temp_series(list(event_temp[:end]), units),
                    name=f"Flex {t_unit}",
                    line=dict(color="#FF6B6B"),
                ),
                row=3,
                col=1,
            )
            if season_key == "summer":
                fig.add_vrect(x0=16, x1=21, fillcolor="#E8A838", opacity=0.12, line_width=0, row=1, col=1)
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
