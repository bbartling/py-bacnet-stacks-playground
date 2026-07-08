#!/usr/bin/env python3
"""Generate Building 100 / 50 multi-page RCx / FDD dashboard HTML reports."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
_APP19 = ROOT.parent
if str(_APP19) not in sys.path:
    sys.path.insert(0, str(_APP19))

from shared.data_config import get_config  # noqa: E402
from shared.branding import APP_TITLE  # noqa: E402

_cfg = get_config()
DATA = _cfg.building_dir
WEATHER = _cfg.weather_dir
OUT = ROOT

SITE_LABEL = _cfg.site_label()
TZ = _cfg.site_timezone()
POLL_SECONDS = _cfg.poll_seconds()
CONFIRM_ROWS = _cfg.confirm_rows()


_source_paths_cache: tuple[float, list[Path]] | None = None


def refresh_data_paths() -> None:
    """Reload paths from .env / HVAC_DATA_ROOT (call before CSV load)."""
    global _cfg, DATA, WEATHER, SITE_LABEL, TZ, POLL_SECONDS, CONFIRM_ROWS, _source_paths_cache
    get_config.cache_clear()
    _cfg = get_config()
    DATA = _cfg.building_dir
    WEATHER = _cfg.weather_dir
    SITE_LABEL = _cfg.site_label()
    TZ = _cfg.site_timezone()
    POLL_SECONDS = _cfg.poll_seconds()
    CONFIRM_ROWS = _cfg.confirm_rows()
    _source_paths_cache = None

SEASONS = {
    "End of heating season": ("2026-03-16", "2026-04-01"),
    "Spring free-cooling / economizer season": ("2026-04-01", "2026-06-01"),
    "Mechanical cooling season": ("2026-06-01", "2026-07-04"),
}
SEASON_SHORT = {
    "End of heating season": "Heating tail",
    "Spring free-cooling / economizer season": "Spring economizer",
    "Mechanical cooling season": "Mech cooling",
}

MIX_TOL = 1.15
SUPPLY_TOL = 1.15
AHU_MIN_OA_DPR = 0.05
DELTA_SUPPLY_FAN = 0.55
FAN_ON_MIN = 0.01
FAN_HI = 0.87
DUCT_STATIC_ERR = 0.20
FLATLINE_WINDOW = 16  # 4 h @ 15 min
FLATLINE_TOL = 0.10
SPIKE_LIMIT = 5.0  # legacy alias; zone spikes use SPIKE_LIMIT_ZONE
CHW_LOW_DELTA_T = 4.0

# Tunable parameters (defaults; overridden via dashboard_params.apply_to_generate_dashboard)
COMFORT_SETPOINT_F = 72.0
COMFORT_BAND_F = 2.0
COMFORT_LO_F = 70.0
COMFORT_HI_F = 74.0
UNOCC_ZONE_LO_F = 70.0
UNOCC_ZONE_HI_F = 75.0
UNOCC_ZONE_PCT = 0.80
WEATHER_FAULT_DELTA_F = 5.0
FREE_COOL_CHW_MIN = 0.20
FREE_COOL_DP_MAX_F = 60.0
FREE_COOL_OAT_AVAIL_F = 72.0
ECONOMIZER_LOW_LIMIT_F = 35.0
OA_MIN_EXPECTED_PCT = 20.0
OA_MAX_ECONOMIZER_PCT = 95.0
BOILER_WARM_OAT_F = 60.0
FAULT_PERSIST_SEC = 600
ZONE_TEMP_LO_F = 55.0
ZONE_TEMP_HI_F = 90.0
OAT_HARD_LO_F = -40.0
OAT_HARD_HI_F = 130.0
FC23_CONFIRM_SEC = 600
FC813_CONFIRM_SEC = 600
FC4_CONFIRM_SEC = 3600
FC4_REVERSALS = 6
FC4_P2P_PCT = 10.0
FC4_CMD_DEADBAND = 3.0
FC13_SAT_DEADBAND_F = 1.0
CHILLER_ENABLE_DELTA_F = 3.0
HW_LOW_DELTA_F = 10.0
SPIKE_LIMIT_OAT = 16.0
SPIKE_LIMIT_ZONE = 5.0

COLORS = {
    "bg": "#0f1419",
    "card": "#1a2332",
    "text": "#e8edf4",
    "muted": "#8b9cb3",
    "accent": "#3b82f6",
    "good": "#22c55e",
    "warn": "#f59e0b",
    "bad": "#ef4444",
    "chart": ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#06b6d4"],
}

_OCC_SCHEDULE: dict | None = None
SITE_SETTINGS: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def norm_cmd(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    return pd.Series(np.where(x > 1.0, x / 100.0, x), index=s.index)


def confirm_fault(raw: pd.Series, rows: int = CONFIRM_ROWS) -> pd.Series:
    raw = raw.fillna(False).astype(bool)
    groups = (raw != raw.shift()).cumsum()
    streak = raw.groupby(groups).cumcount() + 1
    return raw & (streak >= rows)


def confirm_fault_long(raw: pd.Series, seconds: int | None = None) -> pd.Series:
    if seconds is None:
        seconds = FAULT_PERSIST_SEC
    rows = max(1, int(np.ceil(seconds / POLL_SECONDS)))
    return confirm_fault(raw, rows)


def load_hist(sub: str) -> pd.DataFrame:
    df = pd.read_csv(
        DATA / sub / "history_wide.csv",
        parse_dates=["timestamp_utc"],
        low_memory=False,
    )
    df["timestamp"] = df["timestamp_utc"]
    df["timestamp_local"] = df["timestamp"].dt.tz_convert(TZ)
    return df.sort_values("timestamp").reset_index(drop=True)


def season_label(ts: pd.Series) -> pd.Series:
    d = ts.dt.tz_convert(TZ).dt.date
    out = pd.Series("Outside defined season", index=ts.index, dtype=object)
    for name, (start, end) in SEASONS.items():
        mask = (d >= pd.Timestamp(start).date()) & (d < pd.Timestamp(end).date())
        out.loc[mask] = name
    return out


def is_occupied(ts: pd.Series) -> pd.Series:
    from shared.occupancy import DEFAULT_SCHEDULE, is_occupied as occ_fn

    schedule = _OCC_SCHEDULE or DEFAULT_SCHEDULE
    return occ_fn(ts, schedule, TZ)


def hours_true(mask: pd.Series) -> float:
    return float(mask.fillna(False).sum()) * POLL_SECONDS / 3600.0


def downsample(df: pd.DataFrame, cols: list[str], n: int = 800) -> pd.DataFrame:
    if len(df) <= n:
        return df
    step = max(1, len(df) // n)
    keep = df.iloc[::step].copy()
    return keep


def fig_to_div(fig: go.Figure, height: int = 420) -> str:
    from units import apply_fig_display_units

    apply_fig_display_units(fig)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["card"],
        font=dict(color=COLORS["text"], size=12),
        margin=dict(l=55, r=40, t=72, b=90),
        height=height,
        title=dict(x=0.02, xanchor="left"),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,
            x=0,
            xanchor="left",
            font=dict(size=10),
        ),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": True, "scrollZoom": True})


def nav_html(active: str, *, interactive: bool = False) -> str:
    from page_registry import discover_pages, nav_tree

    discover_pages()
    items: list[str] = []
    for entry in nav_tree(interactive=interactive):
        if entry.get("kind") == "group":
            children = entry.get("children") or []
            inner = []
            for child in children:
                href = child.get("href", f"{child['id']}.html")
                cls = ' class="active"' if href == active else ""
                dis = "" if child.get("available", True) else ' class="disabled"'
                if dis and href != active:
                    inner.append(f'<a href="{href}"{dis}>{child["title"]}</a>')
                else:
                    inner.append(f'<a href="{href}"{cls}>{child["title"]}</a>')
            items.append(
                f'<details class="nav-group"><summary>Air-side Systems</summary>'
                f'<div class="nav-dropdown">{"".join(inner)}</div></details>'
            )
            continue
        href = entry.get("href", f"{entry['id']}.html")
        cls = ' class="active"' if href == active else ""
        if not entry.get("available", True) and href != active:
            items.append(f'<a href="{href}" class="disabled">{entry["title"]}</a>')
        else:
            items.append(f'<a href="{href}"{cls}>{entry["title"]}</a>')
    return "\n".join(items)


def ecm_card(
    ecm_id: str,
    rule: str,
    title: str,
    *,
    chart_html: str = "",
    equation: str = "",
    tune: bool = True,
    analytics_html: str = "",
    note: str = "",
) -> str:
    tune_block = rule_tune_mount(rule) if tune else ""
    eq_block = f'<footer class="ecm-equation">{equation}</footer>' if equation else ""
    note_block = f'<p class="note">{note}</p>' if note else ""
    analytics_block = f'<div class="ecm-analytics" data-analytics-for="{rule}">{analytics_html}</div>' if analytics_html else f'<div class="ecm-analytics" data-analytics-for="{rule}"></div>'
    return f"""<section class="ecm-card" data-ecm="{ecm_id}" data-rule="{rule}">
<header class="ecm-head"><h3>{title}</h3><span class="ecm-rule-id">{rule}</span></header>
{analytics_block}
{tune_block}
{note_block}
<div class="ecm-chart">{chart_html}</div>
{eq_block}
</section>"""


def body_not_in_model(equipment_type: str, expected_roles: list[str] | None = None) -> str:
    roles = ", ".join(expected_roles or [])
    hint = f" Expected point roles: {roles}." if roles else ""
    return f"""<div class="card placeholder-card">
<h2>Not present in data model</h2>
<p class="note">No <strong>{equipment_type}</strong> equipment was discovered in the Haystack RDF model.{hint}
Use <a href="data_model.html">Data Model</a> to bootstrap or import equipment, then refresh.</p></div>"""


def header_meta_html() -> str:
    from shared.occupancy import occupancy_summary
    from units import fmt_temp, is_metric, temp_unit

    created = meta.get("created", "")
    occ = occupancy_summary((_OCC_SCHEDULE or SITE_SETTINGS.get("occupancy")))
    band = COMFORT_BAND_F * (5.0 / 9.0) if is_metric() else COMFORT_BAND_F
    setpoint_meta = f"{fmt_temp(COMFORT_SETPOINT_F)} ±{band:.1f}{temp_unit()}"
    return f"{SITE_LABEL} · Created {created} · Timezone: {TZ} · Setpoint: {setpoint_meta} occupied · {occ}"


def site_settings_panel_html() -> str:
    return """
<details class="site-settings-panel" id="site-settings-panel">
  <summary>Site settings (occupancy & comfort)</summary>
  <form class="site-settings-form">
    <label>Timezone <select id="site-timezone" name="timezone">
      <option value="America/Chicago">America/Chicago</option>
      <option value="America/New_York">America/New_York</option>
      <option value="America/Denver">America/Denver</option>
      <option value="America/Los_Angeles">America/Los_Angeles</option>
    </select></label>
    <label>Comfort setpoint (°F) <input type="number" id="site-comfort-sp" step="0.5" min="68" max="76" value="72"/></label>
    <label>Comfort band ± (°F) <input type="number" id="site-comfort-band" step="0.5" min="1" max="4" value="2"/></label>
    <div class="schedule-row" data-schedule="mon_fri"><span>Mon–Fri</span><input class="sched-start" type="time" value="06:00"/><input class="sched-end" type="time" value="17:00"/><label><input class="sched-enabled" type="checkbox" checked/> On</label></div>
    <div class="schedule-row" data-schedule="sat"><span>Saturday</span><input class="sched-start" type="time" value="07:00"/><input class="sched-end" type="time" value="14:00"/><label><input class="sched-enabled" type="checkbox" checked/> On</label></div>
    <div class="schedule-row" data-schedule="sun"><span>Sunday</span><input class="sched-start" type="time" value="08:00"/><input class="sched-end" type="time" value="12:00"/><label><input class="sched-enabled" type="checkbox"/> On</label></div>
    <button type="submit" class="btn primary">Save site settings</button>
  </form>
</details>"""


def rule_tune_mount(rule: str) -> str:
    """Placeholder filled by dashboard_tune.js with sliders for this FDD rule."""
    return f'<div class="rule-tune-mount" data-rule="{rule}"></div>'


def analyst_banner_html(
    notes: str = "",
    params_block: str = "",
    analyst_name: str = "",
    interactive: bool = False,
    page_id: str = "",
) -> str:
    tune_block = params_block or ""
    if interactive:
        return f"""
<div class="analyst-panel" id="analyst-panel" data-page="{page_id}">
  <div class="analyst-panel-head">
    <strong>Analyst workspace</strong>
    {f'<span class="analyst-tag">Prepared by {analyst_name}</span>' if analyst_name else ''}
    <span class="tune-status" id="tune-live-status">Adjust rule sliders below charts — auto-refresh on change</span>
    <div class="analyst-actions">
      <button type="button" class="btn primary" id="btn-refresh-page">Refresh now</button>
      <button type="button" class="btn" id="btn-save-session">Save settings</button>
      <button type="button" class="btn accent" id="btn-export-package">Export client package</button>
    </div>
  </div>
  {site_settings_panel_html()}
  {tune_block}
</div>"""
    if tune_block:
        return f'<div class="analyst-delivered">{tune_block}</div>'
    return ""


def page_html(
    title: str,
    active: str,
    body: str,
    *,
    notes: str = "",
    params_block: str = "",
    analyst_name: str = "",
    interactive: bool = False,
    page_id: str = "",
) -> str:
    banner = analyst_banner_html(notes, params_block, analyst_name, interactive, page_id)
    extra_js = ""
    if interactive:
        extra_js = f"""
<script src="/static/dashboard_tune.js"></script>
<script src="/static/dashboard_auth.js"></script>
<script src="/static/dashboard_settings.js"></script>
<script src="/static/dashboard_units.js"></script>
<script src="/static/dashboard_notes.js"></script>
<script src="/static/dashboard_rules.js"></script>
<script src="/static/dashboard_cookbook.js"></script>
<script>window.DASHBOARD_PAGE = "{page_id}";</script>
"""
    readonly_banner = (
        '<div id="readonly-banner" class="readonly-banner" hidden>Package locked — engineer login required.</div>'
        if interactive
        else ""
    )
    auth_chip = ""
    if interactive:
        auth_chip = """
<div class="auth-chip" id="auth-chip">
  <input type="password" id="engineer-pin" placeholder="Engineer PIN" autocomplete="off"/>
  <button type="button" class="btn btn-link" id="btn-engineer-login">Login</button>
  <button type="button" class="btn btn-link" id="btn-engineer-logout" hidden>Logout</button>
</div>"""
    unit_toggle = ""
    if interactive:
        unit_toggle = '<button type="button" class="unit-toggle" id="unit-toggle" aria-label="Toggle units">°F / Imperial</button>'
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title} — {APP_TITLE}</title>
<link rel="stylesheet" href="/static/dashboard.css"/>
<script src="plotly.min.js"></script>
</head>
<body>
{readonly_banner}
<header>
  <div class="brand">
    <h1>{APP_TITLE}</h1>
    <div class="meta" id="header-meta">{header_meta_html()}</div>
  </div>
  <div class="header-actions">
    {unit_toggle}
    <button type="button" class="theme-toggle" id="theme-toggle" aria-label="Toggle theme">Light mode</button>
    {auth_chip}
  </div>
</header>
<nav>{nav_html(active, interactive=interactive)}</nav>
<main>{banner}
<div class="page-main"><div id="page-content">{body}</div>
<section class="cookbook-section" id="cookbook-mount" data-page="{page_id}" hidden></section>
<section class="notes-feed" id="page-notes-section" data-page="{page_id}">
  <header class="notes-feed-head"><h2>Engineer notes</h2><p class="note">Findings for this page — saved in session and client package.</p></header>
  <div id="notes-post-list" class="notes-post-list"></div>
  <div class="notes-compose" id="notes-compose">
    <textarea id="notes-draft" rows="5" placeholder="Key findings, caveats, recommended actions…"></textarea>
    <button type="button" class="btn primary" id="btn-post-note">Post note</button>
  </div>
</section>
</div>
</main>
<script src="/static/dashboard_theme.js"></script>
{extra_js}
</body>
</html>"""


meta: dict = {}

FAULT_EQUATIONS = {
    "COMFORT": "Occupied zone temperature outside comfort setpoint ± band",
    "FC1": "Fan ≥87% AND duct static &lt; setpoint − 0.20 in. w.c. (10 min persist)",
    "FC2": "Fan on AND MAT &lt; min(RAT, OAT) − 1.15°F (10 min)",
    "FC3": "Fan on AND MAT &gt; max(RAT, OAT) + 1.15°F (10 min)",
    "FC4": "Command hunting: ≥6 reversals/hr AND peak-to-peak ≥10% on CHW, economizer, or fan (1 hr)",
    "FC8": "Economizer open, CHW &lt;10%, SAT−MAT error &gt; √(MIX²+SUPPLY²) tolerance",
    "FC9": "Economizer open, CHW &lt;10%, OAT too warm vs SAT setpoint for free cooling",
    "FC10": "CHW &gt;1%, economizer &gt;90%, |MAT−OAT| &gt; √2×MIX tolerance (mech cool)",
    "FC11": "CHW &gt;1%, economizer &gt;90%, OAT favorable but economizer not reducing load",
    "FC12": "CHW &gt;1%, SAT &gt; MAT blend tolerance at min/max economizer",
    "FC13": "CHW &gt;1%, SAT &gt; SAT setpoint + 1°F at full cooling",
    "Free cool opp.": "CHW &gt;20% while Open-Meteo economizer OK but OA damper below full economizer (~100% OA expected)",
    "ECON-2": "Open-Meteo economizer NOT OK but OA damper above assumed minimum (~20%)",
    "ECON-3 mech": "Mech cooling while Open-Meteo economizer OK but OA damper not at full economizer",
    "Unocc. run satisfied": "Fan on outside lease hours AND ≥80% zones 70–75°F",
    "SV2 OAT range": "OAT outside −40 to 140°F",
    "SV6 flatline": "Temperature unchanged ≤0.10°F over 4 h",
    "SV7 spike": "Temperature step &gt;16°F in 15 min",
    "Chiller free-cool": "Chiller running while Open-Meteo OAT &lt; 55°F",
    "Open-Meteo econ OK": "Open-Meteo dew point &lt; 60°F AND dry bulb &lt; 72°F AND dry bulb ≥ 35°F",
}


def fault_equations_html(codes: list[str] | None = None) -> str:
    from units import substitute_temp_text

    items = FAULT_EQUATIONS if codes is None else {k: v for k, v in FAULT_EQUATIONS.items() if k in codes}
    rows = "".join(
        f"<tr><td><strong>{k}</strong></td><td>{substitute_temp_text(v)}</td></tr>"
        for k, v in items.items()
    )
    return f"<table><thead><tr><th>Code</th><th>Rule (plain language)</th></tr></thead><tbody>{rows}</tbody></table>"


PAGE_FAULT_CODES: dict[str, list[str]] = {
    "index": [],
    "zones": ["COMFORT", "SV6 flatline", "SV7 spike"],
    "weather": ["SV2 OAT range", "SV6 flatline", "SV7 spike"],
    "ahu_1": ["FC1", "FC2", "FC3", "FC4", "SV2 OAT range", "SV6 flatline", "SV7 spike"],
    "ahu_2": ["FC1", "FC2", "FC3", "FC4", "SV2 OAT range", "SV6 flatline", "SV7 spike"],
    "economizer": [
        "FC8", "FC9", "FC10", "FC11", "FC12", "FC13",
        "Free cool opp.", "ECON-2", "ECON-3 mech", "Open-Meteo econ OK",
    ],
    "chiller_plant": ["Chiller free-cool", "Open-Meteo econ OK"],
    "central_plant": ["Chiller free-cool", "Open-Meteo econ OK"],
    "boiler_plant": [],
    "excess_runtime": ["Unocc. run satisfied"],
    "motor_runtime": [],
    "custom_rules": [],
}


def page_fault_equations_block(page_id: str) -> str:
    codes = PAGE_FAULT_CODES.get(page_id, [])
    if not codes:
        return ""
    return f'<div class="card fault-equations-card"><h2>Fault equations</h2>{fault_equations_html(codes)}</div>'


# ---------------------------------------------------------------------------
# Zone mapping
# ---------------------------------------------------------------------------
def load_zone_map() -> pd.DataFrame:
    zm = pd.read_csv(DATA / "vav_to_ahu_simple.csv")
    zm = zm[zm["history_column"].str.startswith("zone_t")].copy()
    # Exclude AHU ZN-T points, duplicate columns, and mis-mapped alarm-limit sensors
    zm = zm[~zm["history_column"].str.contains(
        r"_2$|nan_pt|fourth_floor_vav_7|fourth_floor_vav_32", regex=True
    )]
    zm = zm.drop_duplicates(subset=["history_column"])
    return zm


def week_start(ts: pd.Series) -> pd.Series:
    """Monday week start, timezone preserved."""
    local = ts.dt.tz_convert(TZ)
    return (local - pd.to_timedelta(local.dt.dayofweek, unit="D")).dt.normalize()


def add_season_shading(fig: go.Figure) -> None:
    """Highlight the three analysis seasons on time-series charts."""
    bands = [
        ("Heating tail", "2026-03-16", "2026-04-01", "rgba(239,68,68,0.07)"),
        ("Spring economizer", "2026-04-01", "2026-06-01", "rgba(34,197,94,0.10)"),
        ("Mech cooling", "2026-06-01", "2026-07-04", "rgba(59,130,246,0.07)"),
    ]
    for label, start, end, color in bands:
        fig.add_vrect(x0=start, x1=end, fillcolor=color, line_width=0)


def zone_columns(ahu_df: pd.DataFrame, ahu: str) -> list[str]:
    zm = load_zone_map()
    cols = zm.loc[zm["parent_ahu"] == ahu, "history_column"].tolist()
    return [c for c in cols if c in ahu_df.columns]


def attach_open_meteo(df: pd.DataFrame, wx: pd.DataFrame) -> pd.DataFrame:
    """Join Open-Meteo reference weather (always used for economizer / plant scatter analysis)."""
    w = wx[["timestamp", "dry_bulb_f", "dew_point_f"]].copy()
    w["web_oat"] = pd.to_numeric(w["dry_bulb_f"], errors="coerce")
    w["web_dp"] = pd.to_numeric(w["dew_point_f"], errors="coerce")
    return df.merge(w[["timestamp", "web_oat", "web_dp"]], on="timestamp", how="left")


def open_meteo_econ_ok(d: pd.DataFrame) -> pd.Series:
    """Economizer OK per Open-Meteo dew point + dry bulb (not BAS OAT)."""
    return (
        d["fan_on"]
        & d["web_oat"].notna()
        & d["web_dp"].notna()
        & (d["web_dp"] < FREE_COOL_DP_MAX_F)
        & (d["web_oat"] < FREE_COOL_OAT_AVAIL_F)
        & (d["web_oat"] >= ECONOMIZER_LOW_LIMIT_F)
    )


# ---------------------------------------------------------------------------
# Sensor validation
# ---------------------------------------------------------------------------
def sv_flatline(s: pd.Series) -> pd.Series:
    roll_min = s.rolling(FLATLINE_WINDOW, min_periods=FLATLINE_WINDOW).min()
    roll_max = s.rolling(FLATLINE_WINDOW, min_periods=FLATLINE_WINDOW).max()
    return confirm_fault(s.notna() & ((roll_max - roll_min) <= FLATLINE_TOL))


def sv_spike(s: pd.Series, limit: float | None = None) -> pd.Series:
    lim = SPIKE_LIMIT_OAT if limit is None else limit
    return confirm_fault(s.notna() & (s.diff().abs() > lim))


def sv1_out_of_range(s: pd.Series, lo: float | None = None, hi: float | None = None) -> pd.Series:
    lo_v = ZONE_TEMP_LO_F if lo is None else lo
    hi_v = ZONE_TEMP_HI_F if hi is None else hi
    return confirm_fault(s.notna() & ((s < lo_v) | (s > hi_v)))


def sv2_oa_out_of_range(s: pd.Series) -> pd.Series:
    return confirm_fault(s.notna() & ((s < OAT_HARD_LO_F) | (s > OAT_HARD_HI_F)))


# ---------------------------------------------------------------------------
# AHU fault rules
# ---------------------------------------------------------------------------
def prep_ahu(df: pd.DataFrame, mad_col: str) -> pd.DataFrame:
    d = df.copy()
    d["season"] = season_label(d["timestamp"])
    d["occupied"] = is_occupied(d["timestamp"])
    d["fan"] = norm_cmd(d["supply_fan_speed_pct"])
    d["fan_on"] = d["fan"] > 0.05
    d["clg"] = norm_cmd(d["chw_valve_pct"])
    d["htg"] = 0.0  # no heating coils on these AHUs
    d["econ"] = norm_cmd(d["ex_dmpr_pos_fan_enable_pct"])
    d["mad_pct"] = norm_cmd(d[mad_col]) if mad_col in d.columns else np.nan
    d["sat"] = pd.to_numeric(d["discharge_air_temp_f"], errors="coerce")
    d["mat"] = pd.to_numeric(d["mixed_air_temp_f"], errors="coerce")
    d["oat"] = pd.to_numeric(d["outside_air_temp_f"], errors="coerce")
    d["rat"] = pd.to_numeric(d["return_air_temp_f"], errors="coerce")
    d["sat_sp"] = pd.to_numeric(d["dat_reset_f"], errors="coerce")
    d["duct_sp"] = pd.to_numeric(d["da_p_setpoint_inwc"], errors="coerce")
    d["duct_static"] = pd.to_numeric(d["da_p_inwc"], errors="coerce")
    return d


def compute_ahu_faults(d: pd.DataFrame, zone_cols: list[str]) -> pd.DataFrame:
    out = d.copy()

    # FC1
    raw = (
        out["duct_static"].notna() & out["duct_sp"].notna()
        & (out["fan"] >= FAN_HI)
        & (out["duct_static"] < out["duct_sp"] - DUCT_STATIC_ERR)
    )
    out["fc1_duct_static"] = confirm_fault(raw)

    # FC2 / FC3 MAT envelope (SV-4)
    out["fc2_mat_below"] = confirm_fault_long(
        out["fan_on"] & out["mat"].notna() & out["oat"].notna() & out["rat"].notna()
        & ((out["mat"] - MIX_TOL) < np.minimum(out["rat"] - MIX_TOL, out["oat"] - MIX_TOL)),
        FC23_CONFIRM_SEC,
    )
    out["fc3_mat_above"] = confirm_fault_long(
        out["fan_on"] & out["mat"].notna() & out["oat"].notna() & out["rat"].notna()
        & ((out["mat"] - MIX_TOL) > np.maximum(out["rat"] + MIX_TOL, out["oat"] + MIX_TOL)),
        FC23_CONFIRM_SEC,
    )

    # FC4 hunting — command oscillation (no heating mode)
    fc4_window = max(4, int(round(FC4_CONFIRM_SEC / POLL_SECONDS)))
    for col, name in [
        ("chw_valve_pct", "chw"),
        ("ex_dmpr_pos_fan_enable_pct", "econ"),
        ("supply_fan_speed_pct", "sf"),
    ]:
        x = pd.to_numeric(out[col], errors="coerce")
        dx = x.diff()
        db = FC4_CMD_DEADBAND
        direction = pd.Series(np.where(dx > db, 1, np.where(dx < -db, -1, 0)), index=out.index)
        nonzero = direction.replace(0, np.nan).ffill().fillna(0)
        reversal = (nonzero != nonzero.shift()) & (nonzero != 0) & (nonzero.shift().fillna(0) != 0)
        rev_count = reversal.rolling(fc4_window, min_periods=fc4_window).sum()
        p2p = x.rolling(fc4_window, min_periods=fc4_window).max() - x.rolling(fc4_window, min_periods=fc4_window).min()
        out[f"hunting_{name}"] = confirm_fault_long((rev_count >= FC4_REVERSALS) & (p2p >= FC4_P2P_PCT), FC4_CONFIRM_SEC)

    # FC8–FC13 economizer diagnostics
    econ = out["econ"]
    clg = out["clg"]
    out["sat_mat_err"] = (out["sat"] - DELTA_SUPPLY_FAN - out["mat"]).abs()
    sqrt_tol = float(np.sqrt(SUPPLY_TOL**2 + MIX_TOL**2))

    out["fc8_sat_above_blend_econ"] = confirm_fault_long(
        out["sat"].notna() & out["mat"].notna()
        & (econ > AHU_MIN_OA_DPR) & (clg < 0.1)
        & (out["sat_mat_err"] > sqrt_tol),
        FC813_CONFIRM_SEC,
    )
    out["fc9_oat_too_warm_free_cool"] = confirm_fault_long(
        out["oat"].notna() & out["sat_sp"].notna()
        & (econ > AHU_MIN_OA_DPR) & (clg < 0.1)
        & ((out["oat"] - MIX_TOL) > (out["sat_sp"] - DELTA_SUPPLY_FAN + MIX_TOL)),
        FC813_CONFIRM_SEC,
    )
    out["abs_mat_oat"] = (out["mat"] - out["oat"]).abs()
    out["fc10_oat_mat_mismatch_mech"] = confirm_fault_long(
        out["mat"].notna() & out["oat"].notna()
        & (clg > 0.01) & (econ > 0.9)
        & (out["abs_mat_oat"] > np.sqrt(2) * MIX_TOL),
        FC813_CONFIRM_SEC,
    )
    out["fc11_oat_mat_mismatch_econ"] = confirm_fault_long(
        out["oat"].notna() & out["sat_sp"].notna()
        & (clg > 0.01) & (econ > 0.9)
        & ((out["oat"] + MIX_TOL) < (out["sat_sp"] - DELTA_SUPPLY_FAN - MIX_TOL)),
        FC813_CONFIRM_SEC,
    )
    sat_check = out["sat"] - SUPPLY_TOL - DELTA_SUPPLY_FAN
    mat_check = out["mat"] + MIX_TOL
    econ_min = np.isclose(econ, AHU_MIN_OA_DPR, atol=0.02) | (econ > 0.9)
    out["fc12_sat_above_blend_cool"] = confirm_fault_long(
        out["sat"].notna() & out["mat"].notna() & (clg > 0.01)
        & (sat_check > mat_check) & econ_min,
        FC813_CONFIRM_SEC,
    )
    out["fc13_sat_above_sp_full_cool"] = confirm_fault_long(
        out["sat"].notna() & out["sat_sp"].notna() & (clg > 0.01)
        & (out["sat"] > out["sat_sp"] + FC13_SAT_DEADBAND_F) & econ_min,
        FC813_CONFIRM_SEC,
    )

    # Open-Meteo economizer rules (reference weather — not BAS OAT)
    out["econ_ok_meteo"] = open_meteo_econ_ok(out)
    oa_min = OA_MIN_EXPECTED_PCT / 100.0
    oa_full = OA_MAX_ECONOMIZER_PCT / 100.0
    oa_db = 0.08

    out["econ2_unfavorable"] = confirm_fault_long(
        out["fan_on"] & ~out["econ_ok_meteo"] & (out["econ"] > oa_min + oa_db),
    )
    out["econ3_mech_not_full_oa"] = confirm_fault_long(
        out["econ_ok_meteo"] & (out["clg"] > FREE_COOL_CHW_MIN) & (out["econ"] < oa_full - oa_db),
    )
    out["free_cool_opp"] = confirm_fault_long(
        out["econ_ok_meteo"] & (out["clg"] > FREE_COOL_CHW_MIN) & (out["econ"] < oa_full - oa_db),
    )

    # Unoccupied run with satisfied zones
    if zone_cols:
        zt = out[zone_cols].apply(pd.to_numeric, errors="coerce")
        satisfied = ((zt >= UNOCC_ZONE_LO_F) & (zt <= UNOCC_ZONE_HI_F)).mean(axis=1) >= UNOCC_ZONE_PCT
    else:
        satisfied = pd.Series(False, index=out.index)
    out["unocc_run_satisfied"] = confirm_fault(
        (~out["occupied"]) & out["fan_on"] & satisfied
    )

    # Sensor validation on AHU temps
    out["sv2_oat"] = sv2_oa_out_of_range(out["oat"])
    out["sv6_oat_flat"] = sv_flatline(out["oat"])
    out["sv7_oat_spike"] = sv_spike(out["oat"], SPIKE_LIMIT_OAT)
    out["sv6_mat_flat"] = sv_flatline(out["mat"])
    out["sv7_mat_spike"] = sv_spike(out["mat"], SPIKE_LIMIT_OAT)

    return out


# ---------------------------------------------------------------------------
# Zone analytics
# ---------------------------------------------------------------------------
def _zone_stats_ahu_context(df: pd.DataFrame) -> dict:
    """Precompute occupancy + season masks once per AHU (not per zone × season)."""
    ts = df["timestamp"]
    local_dates = ts.dt.tz_convert(TZ).dt.date
    occ = is_occupied(ts)
    season_masks = {
        season: (local_dates >= pd.Timestamp(start).date()) & (local_dates < pd.Timestamp(end).date())
        for season, (start, end) in SEASONS.items()
    }
    return {"df": df, "occ": occ, "season_masks": season_masks}


def compute_zone_stats(ahu1: pd.DataFrame, ahu2: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    zm = load_zone_map()
    ahu_ctx = {
        "AHU_1": _zone_stats_ahu_context(ahu1),
        "AHU_2": _zone_stats_ahu_context(ahu2),
    }
    rows = []
    for _, z in zm.iterrows():
        ahu = z["parent_ahu"]
        col = z["history_column"]
        ctx = ahu_ctx.get(ahu)
        if ctx is None:
            continue
        src = ctx["df"]
        if col not in src.columns:
            continue
        s = pd.to_numeric(src[col], errors="coerce")
        occ = ctx["occ"]
        sv1 = sv1_out_of_range(s)
        sv6 = sv_flatline(s)
        for season, sm in ctx["season_masks"].items():
            occ_s = occ & sm
            occ_vals = s[occ_s].dropna()
            occ_vals = occ_vals[(occ_vals >= 50) & (occ_vals <= 95)]
            if len(occ_vals) == 0:
                pct72 = np.nan
            else:
                pct72 = float(((occ_vals >= COMFORT_LO_F) & (occ_vals <= COMFORT_HI_F)).mean() * 100)
            rows.append({
                "season": season,
                "parent_ahu": ahu,
                "floor": z["floor"],
                "vav_id": z["vav_id"],
                "history_column": col,
                "pct_within_72_occupied": round(pct72, 1) if pd.notna(pct72) else np.nan,
                "avg_temp_occupied_f": round(float(occ_vals.mean()), 2) if len(occ_vals) else np.nan,
                "sv1_hours": round(hours_true(sv1 & sm), 1),
                "sv6_hours": round(hours_true(sv6 & sm), 1),
            })

    zone_df = pd.DataFrame(rows)

    floor_rows = []
    for season in SEASONS:
        for floor in zone_df["floor"].dropna().unique():
            sub = zone_df[(zone_df["season"] == season) & (zone_df["floor"] == floor)]
            if sub.empty:
                continue
            floor_rows.append({
                "season": season,
                "floor": floor,
                "pct_within_72": round(sub["pct_within_72_occupied"].mean(), 1),
                "zone_count": len(sub),
            })
    floor_df = pd.DataFrame(floor_rows)

    # Weekly avg zone temps by floor (occupied only)
    weekly_rows = []
    for ahu, df in [("AHU_1", ahu1), ("AHU_2", ahu2)]:
        cols = zone_columns(df, ahu)
        if not cols:
            continue
        zt = df[cols].apply(pd.to_numeric, errors="coerce").mean(axis=1)
        tmp = pd.DataFrame({
            "week": df["timestamp_local"].dt.to_period("W").astype(str),
            "month": df["timestamp_local"].dt.strftime("%Y-%m"),
            "temp": zt,
            "occupied": is_occupied(df["timestamp"]),
        })
        tmp = tmp[tmp["occupied"] & tmp["temp"].notna()]
        for month, g in tmp.groupby("month"):
            weekly_rows.append({"month": month, "ahu": ahu, "avg_zone_temp_f": round(g["temp"].mean(), 1)})
    weekly_df = pd.DataFrame(weekly_rows)

    return zone_df, floor_df, weekly_df


def compute_comfort_weekly_ts(ahu1: pd.DataFrame, ahu2: pd.DataFrame) -> pd.DataFrame:
    """Weekly % of occupied zone samples within 72°F ±2°F, building-wide and by floor."""
    zm = load_zone_map()
    parts = []
    for ahu, df in [("AHU_1", ahu1), ("AHU_2", ahu2)]:
        for _, z in zm[zm["parent_ahu"] == ahu].iterrows():
            col = z["history_column"]
            if col not in df.columns:
                continue
            temp = pd.to_numeric(df[col], errors="coerce")
            occ = is_occupied(df["timestamp"])
            valid = occ & temp.notna() & (temp >= 50) & (temp <= 95)  # drop alarm-limit garbage
            parts.append(pd.DataFrame({
                "week": week_start(df.loc[valid, "timestamp"]),
                "floor": z["floor"],
                "in_comfort": ((temp[valid] >= COMFORT_LO_F) & (temp[valid] <= COMFORT_HI_F)).astype(float),
            }))
    if not parts:
        return pd.DataFrame()
    long = pd.concat(parts, ignore_index=True).dropna(subset=["week"])
    bldg = long.groupby("week", as_index=False).agg(pct_comfort=("in_comfort", lambda x: round(x.mean() * 100, 1)))
    bldg["series"] = "Building (all zones)"
    floor = long.groupby(["week", "floor"], as_index=False).agg(
        pct_comfort=("in_comfort", lambda x: round(x.mean() * 100, 1))
    )
    floor["series"] = floor["floor"]
    floor["series"] = floor["floor"]
    out = pd.concat([
        bldg[["week", "series", "pct_comfort"]],
        floor[["week", "series", "pct_comfort"]],
    ], ignore_index=True)
    return out.sort_values("week")


def compute_chiller_fc_weekly(plant: dict) -> pd.DataFrame:
    """Weekly chiller run vs avoidable run (free-cooling opportunity) hours."""
    rows = []
    for key, label in [("CHILLER_1", "Chiller 1"), ("CHILLER_2", "Chiller 2")]:
        d = plant[key].copy()
        d["week"] = week_start(d["timestamp"])
        d["timestamp_local"] = d["timestamp"].dt.tz_convert(TZ)
        for week, g in d.groupby("week"):
            if pd.isna(week):
                continue
            rows.append({
                "week": week,
                "chiller": label,
                "run_h": round(hours_true(g["run"]), 2),
                "free_cool_opp_h": round(hours_true(g["free_cool_opp"]), 2),
                "below_enable_h": round(hours_true(g["below_enable"]), 2),
                "avg_oat_f": round(float(g["oat"].mean()), 1) if g["oat"].notna().any() else None,
            })
    return pd.DataFrame(rows).sort_values("week")


def fc_hours_breakdown(ahu1, ahu2, plant) -> dict:
    ahu1_h = hours_true(ahu1["free_cool_opp"])
    ahu2_h = hours_true(ahu2["free_cool_opp"])
    ch1_h = hours_true(plant["CHILLER_1"]["free_cool_opp"])
    ch2_h = hours_true(plant["CHILLER_2"]["free_cool_opp"])
    return {
        "ahu1_h": ahu1_h,
        "ahu2_h": ahu2_h,
        "ch1_h": ch1_h,
        "ch2_h": ch2_h,
        "ahu_total": ahu1_h + ahu2_h,
        "chiller_total": ch1_h + ch2_h,
        "total": ahu1_h + ahu2_h + ch1_h + ch2_h,
    }


def compute_free_cool_weekly(ahu1: pd.DataFrame, ahu2: pd.DataFrame, plant: dict) -> pd.DataFrame:
    """Weekly free-cooling opportunity hours by equipment."""
    rows = []
    for df, source in [
        (ahu1, "AHU 1"),
        (ahu2, "AHU 2"),
        (plant["CHILLER_2"], "Chiller 2"),
        (plant["CHILLER_1"], "Chiller 1"),
    ]:
        d = df.copy()
        d["week"] = week_start(d["timestamp"])
        for week, g in d.groupby("week"):
            if pd.isna(week):
                continue
            rows.append({
                "week": week,
                "source": source,
                "hours": round(hours_true(g["free_cool_opp"]), 2),
            })
    return pd.DataFrame(rows).sort_values("week")


def compute_free_cool_daily_ts(ahu1: pd.DataFrame, ahu2: pd.DataFrame, wx: pd.DataFrame) -> pd.DataFrame:
    """Daily rollup for free-cooling time series with OAT context."""
    wx_oat = wx[["timestamp", "dry_bulb_f"]].copy()
    wx_oat["day"] = wx_oat["timestamp"].dt.tz_convert(TZ).dt.normalize()

    def daily_ahu(d: pd.DataFrame, name: str) -> pd.DataFrame:
        tmp = d[["timestamp", "free_cool_opp", "clg", "oat"]].copy()
        tmp["day"] = tmp["timestamp"].dt.tz_convert(TZ).dt.normalize()
        agg = tmp.groupby("day").agg(
            opp_h=("free_cool_opp", lambda x: hours_true(x)),
            avg_chw_pct=("clg", lambda x: float(norm_cmd(x).mean() * 100)),
            avg_oat=("oat", "mean"),
        ).reset_index()
        agg["source"] = name
        return agg

    d1 = daily_ahu(ahu1, "AHU 1")
    d2 = daily_ahu(ahu2, "AHU 2")
    oat = wx_oat.groupby("day")["dry_bulb_f"].mean().reset_index().rename(columns={"dry_bulb_f": "web_oat"})
    out = d1.merge(d2, on="day", how="outer", suffixes=("_ahu1", "_ahu2"))
    out = out.merge(oat, on="day", how="left")
    out["total_opp_h"] = out["opp_h_ahu1"].fillna(0) + out["opp_h_ahu2"].fillna(0)
    return out.sort_values("day")


def compute_excess_weekly_detailed(ahu1: pd.DataFrame, ahu2: pd.DataFrame) -> pd.DataFrame:
    """Weekly fan hours split into occupied, unoccupied (zones not satisfied), and excess."""
    rows = []
    for df, name in [(ahu1, "AHU 1"), (ahu2, "AHU 2")]:
        d = df.copy()
        d["week"] = week_start(d["timestamp"])
        d["excess"] = d["unocc_run_satisfied"] & d["fan_on"]
        d["occ_fan"] = d["occupied"] & d["fan_on"]
        d["unocc_other"] = (~d["occupied"]) & d["fan_on"] & ~d["excess"]
        for week, g in d.groupby("week"):
            if pd.isna(week):
                continue
            rows.append({
                "week": week,
                "ahu": name,
                "occupied_fan_h": round(hours_true(g["occ_fan"]), 2),
                "excess_fan_h": round(hours_true(g["excess"]), 2),
                "unocc_other_fan_h": round(hours_true(g["unocc_other"]), 2),
            })
    return pd.DataFrame(rows).sort_values("week")


def compute_floor_weekly_temp(ahu1: pd.DataFrame, ahu2: pd.DataFrame) -> pd.DataFrame:
    """Weekly average occupied zone temperature °F by floor."""
    zm = load_zone_map()
    parts = []
    for ahu, df in [("AHU_1", ahu1), ("AHU_2", ahu2)]:
        for _, z in zm[zm["parent_ahu"] == ahu].iterrows():
            col = z["history_column"]
            if col not in df.columns:
                continue
            temp = pd.to_numeric(df[col], errors="coerce")
            occ = is_occupied(df["timestamp"])
            valid = occ & temp.notna() & (temp >= 50) & (temp <= 95)
            parts.append(pd.DataFrame({
                "week": week_start(df.loc[valid, "timestamp"]),
                "floor": z["floor"],
                "temp_f": temp[valid],
            }))
    if not parts:
        return pd.DataFrame()
    long = pd.concat(parts, ignore_index=True).dropna(subset=["week"])
    return long.groupby(["week", "floor"], as_index=False).agg(avg_temp_f=("temp_f", "mean")).sort_values("week")


def compute_floor_rank_by_season(zone_df: pd.DataFrame) -> pd.DataFrame:
    """Rank floors by comfort % each season (1 = best)."""
    rows = []
    for season in SEASONS:
        sub = zone_df.groupby(["season", "floor"], as_index=False).agg(
            pct=("pct_within_72_occupied", "mean"),
            avg_temp=("avg_temp_occupied_f", "mean"),
        )
        sub = sub[sub["season"] == season].dropna(subset=["pct"])
        sub = sub.sort_values("pct", ascending=False).reset_index(drop=True)
        sub["rank"] = sub.index + 1
        sub["season_short"] = SEASON_SHORT[season]
        rows.append(sub)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def compute_mech_cool_oat_bins(plant: dict, wx: pd.DataFrame) -> pd.DataFrame:
    """Chiller run hours binned by Open-Meteo OAT (5°F bins); pump_on + command per chiller."""
    wx = wx[["timestamp", "dry_bulb_f"]].copy()
    wx["oat"] = pd.to_numeric(wx["dry_bulb_f"], errors="coerce")
    wx["oat_clamped"] = wx["oat"].clip(40, 110)
    wx["bin_start"] = (np.floor(wx["oat_clamped"] / 5) * 5).astype("Int64")

    rows = []
    for key, label in [("CHILLER_1", "Chiller 1"), ("CHILLER_2", "Chiller 2")]:
        d = plant[key][["timestamp", "pump_on"]].merge(wx[["timestamp", "bin_start"]], on="timestamp", how="inner")
        for bin_start, g in d[d["pump_on"]].groupby("bin_start"):
            if pd.isna(bin_start):
                continue
            rows.append({
                "bin_start": int(bin_start),
                "bin_label": f"{int(bin_start)}-{int(bin_start)+4}",
                "source": label,
                "hours": round(hours_true(g["pump_on"]), 2),
            })
    return pd.DataFrame(rows).sort_values(["source", "bin_start"])


def compute_open_meteo_free_cool(ahu1: pd.DataFrame, ahu2: pd.DataFrame, wx: pd.DataFrame) -> pd.DataFrame:
    """Daily Open-Meteo free-cooling availability vs AHU mechanical cooling hours."""
    wx = wx.copy()
    wx["web_oat"] = pd.to_numeric(wx["dry_bulb_f"], errors="coerce")
    wx["dew_point_f"] = pd.to_numeric(wx.get("dew_point_f"), errors="coerce")
    wx["free_cool_avail"] = (wx["dew_point_f"] < FREE_COOL_DP_MAX_F) & (wx["web_oat"] < FREE_COOL_OAT_AVAIL_F)
    wx["day"] = wx["timestamp"].dt.tz_convert(TZ).dt.normalize()
    avail = wx.groupby("day").agg(
        avail_h=("free_cool_avail", lambda x: hours_true(x)),
        avg_oat=("web_oat", "mean"),
        avg_dp=("dew_point_f", "mean"),
    ).reset_index()

    def daily_mech(d: pd.DataFrame, name: str) -> pd.DataFrame:
        tmp = d[["timestamp", "clg"]].merge(
            wx[["timestamp", "free_cool_avail"]], on="timestamp", how="inner",
        )
        tmp["mech"] = norm_cmd(tmp["clg"]) > FREE_COOL_CHW_MIN
        tmp["wasted"] = tmp["mech"] & tmp["free_cool_avail"].fillna(False)
        tmp["day"] = tmp["timestamp"].dt.tz_convert(TZ).dt.normalize()
        agg = tmp.groupby("day").apply(
            lambda g: pd.Series({
                "mech_h": hours_true(g["mech"]),
                "wasted_mech_h": hours_true(g["wasted"]),
            }),
            include_groups=False,
        ).reset_index()
        agg["source"] = name
        return agg

    m1 = daily_mech(ahu1, "AHU 1")
    m2 = daily_mech(ahu2, "AHU 2")
    out = avail.merge(
        m1.rename(columns={"mech_h": "mech_h_ahu1", "wasted_mech_h": "wasted_ahu1"}),
        on="day", how="outer",
    ).merge(
        m2.rename(columns={"mech_h": "mech_h_ahu2", "wasted_mech_h": "wasted_ahu2"}),
        on="day", how="outer",
    )
    out["mech_h_total"] = out["mech_h_ahu1"].fillna(0) + out["mech_h_ahu2"].fillna(0)
    out["wasted_mech_h"] = out["wasted_ahu1"].fillna(0) + out["wasted_ahu2"].fillna(0)
    return out.sort_values("day")


def compute_weather_fault_by_hour(wx_df: pd.DataFrame) -> pd.DataFrame:
    """Fault sample counts by season and hour-of-day (local)."""
    rows = []
    for ahu in ("ahu1", "ahu2"):
        col = f"fault_{ahu}"
        sub = wx_df[wx_df[col].fillna(False)].copy()
        if sub.empty:
            continue
        sub["hour"] = sub["timestamp_local"].dt.hour
        for season, g in sub.groupby("season"):
            for hour, h in g.groupby("hour"):
                rows.append({
                    "season": SEASON_SHORT.get(season, season),
                    "ahu": f"AHU {ahu[-1]}",
                    "hour": int(hour),
                    "fault_samples": len(h),
                    "fault_h": round(len(h) * POLL_SECONDS / 3600, 2),
                })
    return pd.DataFrame(rows)


def compute_chiller_daily_weekly(plant: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Daily and weekly chiller run hours time series."""
    daily_rows, weekly_rows = [], []
    for key, label in [("CHILLER_1", "Chiller 1"), ("CHILLER_2", "Chiller 2")]:
        d = plant[key].copy()
        d["day"] = d["timestamp"].dt.tz_convert(TZ).dt.normalize()
        d["week"] = week_start(d["timestamp"])
        for day, g in d.groupby("day"):
            daily_rows.append({"day": day, "chiller": label, "run_h": round(hours_true(g["run"]), 2)})
        for week, g in d.groupby("week"):
            weekly_rows.append({"week": week, "chiller": label, "run_h": round(hours_true(g["run"]), 2)})
    return pd.DataFrame(daily_rows), pd.DataFrame(weekly_rows)


def ahu_season_summary(d: pd.DataFrame) -> pd.DataFrame:
    """Full fault rollup by season with weekday/weekend fan hours."""
    local = d["timestamp"].dt.tz_convert(TZ)
    is_we = local.dt.dayofweek >= 5
    fault_cols = [
        ("fc1_duct_static", "FC1"),
        ("fc2_mat_below", "FC2"),
        ("fc3_mat_above", "FC3"),
        ("hunting_chw", "FC4 CHW hunt"),
        ("hunting_econ", "FC4 econ hunt"),
        ("hunting_sf", "FC4 fan hunt"),
        ("fc8_sat_above_blend_econ", "FC8"),
        ("fc9_oat_too_warm_free_cool", "FC9"),
        ("fc10_oat_mat_mismatch_mech", "FC10"),
        ("fc11_oat_mat_mismatch_econ", "FC11"),
        ("fc12_sat_above_blend_cool", "FC12"),
        ("fc13_sat_above_sp_full_cool", "FC13"),
        ("free_cool_opp", "Free cool opp."),
        ("unocc_run_satisfied", "Unocc. run"),
        ("sv2_oat", "SV2 OAT range"),
        ("sv6_oat_flat", "SV6 OAT flat"),
        ("sv7_oat_spike", "SV7 OAT spike"),
        ("sv6_mat_flat", "SV6 MAT flat"),
        ("sv7_mat_spike", "SV7 MAT spike"),
    ]
    rows = []
    for season in SEASONS:
        m = d["season"] == season
        row = {
            "season": SEASON_SHORT[season],
            "fan_run_h": round(hours_true(d.loc[m, "fan_on"]), 1),
            "fan_wd_h": round(hours_true(d.loc[m, "fan_on"] & ~is_we[m]), 1),
            "fan_we_h": round(hours_true(d.loc[m, "fan_on"] & is_we[m]), 1),
        }
        for col, label in fault_cols:
            if col in d.columns:
                row[label] = round(hours_true(d.loc[m, col]), 1)
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------
def compute_weather(ahu1: pd.DataFrame, ahu2: pd.DataFrame, wx: pd.DataFrame) -> pd.DataFrame:
    wx = wx.copy()
    wx["web_oat"] = pd.to_numeric(wx["dry_bulb_f"], errors="coerce")
    m1 = ahu1[["timestamp", "outside_air_temp_f"]].rename(columns={"outside_air_temp_f": "bas_oat"})
    m2 = ahu2[["timestamp", "outside_air_temp_f"]].rename(columns={"outside_air_temp_f": "bas_oat"})
    out = wx[["timestamp", "web_oat"]].merge(m1, on="timestamp", how="inner")
    out = out.merge(m2, on="timestamp", how="inner", suffixes=("_ahu1", "_ahu2"))
    out["timestamp_local"] = out["timestamp"].dt.tz_convert(TZ)
    out["season"] = season_label(out["timestamp"])
    for ahu in ("ahu1", "ahu2"):
        col = f"bas_oat_{ahu}"
        out[f"delta_{ahu}"] = out[col] - out["web_oat"]
        out[f"fault_{ahu}"] = confirm_fault(out[f"delta_{ahu}"].abs() > WEATHER_FAULT_DELTA_F)
    return out


# ---------------------------------------------------------------------------
# Central plant
# ---------------------------------------------------------------------------
def compute_plant(ch1: pd.DataFrame, ch2: pd.DataFrame, blr: pd.DataFrame, wx: pd.DataFrame) -> dict:
    pumps = blr[["timestamp", "hwp1_s", "hwp2_s", "hwp3_s"]].copy()
    pumps["any_pump_on"] = (
        pd.to_numeric(pumps["hwp1_s"], errors="coerce").fillna(0)
        + pd.to_numeric(pumps["hwp2_s"], errors="coerce").fillna(0)
        + pd.to_numeric(pumps["hwp3_s"], errors="coerce").fillna(0)
    ) > 0

    results = {}
    for name, df, cmd_col, pwr_col in [
        ("CHILLER_1", ch1, "chiller_1_command", "meter_power_sum_kw"),
        ("CHILLER_2", ch2, "chiller_2_command", "meter_power_sum_kw"),
    ]:
        d = df.merge(wx[["timestamp", "dry_bulb_f"]], on="timestamp", how="left")
        d = d.merge(pumps[["timestamp", "any_pump_on"]], on="timestamp", how="left")
        d["season"] = season_label(d["timestamp"])
        d["run"] = pd.to_numeric(d[cmd_col], errors="coerce").fillna(0) > 0
        d["power_kw"] = pd.to_numeric(d.get(pwr_col), errors="coerce").fillna(0)
        d["pump_on"] = d["run"] & (d["power_kw"] > 0.5)
        d["chws"] = pd.to_numeric(d["chws_t_f"], errors="coerce")
        d["chwr"] = pd.to_numeric(d["chwr_t_f"], errors="coerce")
        d["delta_t"] = d["chwr"] - d["chws"]
        d["oat"] = pd.to_numeric(d["dry_bulb_f"], errors="coerce")
        d["enable_sp"] = pd.to_numeric(d.get("oat_chiller_enable_setpoint_f"), errors="coerce")
        d["low_delta_t"] = confirm_fault_long(d["run"] & (d["delta_t"] < CHW_LOW_DELTA_T), 600)
        d["free_cool_opp"] = confirm_fault_long(d["run"] & (d["oat"] < FREE_COOL_OAT_AVAIL_F))
        d["below_enable"] = confirm_fault_long(
            d["run"] & d["enable_sp"].notna() & (d["oat"] < d["enable_sp"] - CHILLER_ENABLE_DELTA_F), 600
        )
        results[name] = d

    blr_d = blr.copy()
    blr_d["season"] = season_label(blr_d["timestamp"])
    blr_d = blr_d.merge(wx[["timestamp", "dry_bulb_f"]], on="timestamp", how="left")
    blr_d["boiler_run"] = (
        pd.to_numeric(blr_d["boiler1"], errors="coerce").fillna(0)
        + pd.to_numeric(blr_d["boiler2"], errors="coerce").fillna(0)
    ) > 0
    blr_d["hws"] = pd.to_numeric(blr_d["hws_t_f"], errors="coerce")
    blr_d["hwr"] = pd.to_numeric(blr_d["hwr_t_f"], errors="coerce")
    blr_d["hw_delta"] = blr_d["hws"] - blr_d["hwr"]
    blr_d["oat"] = pd.to_numeric(blr_d["dry_bulb_f"], errors="coerce")
    blr_d["warm_weather_run"] = confirm_fault_long(blr_d["boiler_run"] & (blr_d["oat"] > BOILER_WARM_OAT_F))
    blr_d["low_hw_delta"] = confirm_fault_long(blr_d["boiler_run"] & (blr_d["hw_delta"] < HW_LOW_DELTA_F), 600)
    blr_d["pump_on"] = (
        pd.to_numeric(blr_d["hwp1_s"], errors="coerce").fillna(0)
        + pd.to_numeric(blr_d["hwp2_s"], errors="coerce").fillna(0)
        + pd.to_numeric(blr_d["hwp3_s"], errors="coerce").fillna(0)
    ) > 0
    results["BOILERS_PUMPS"] = blr_d
    return results


# ---------------------------------------------------------------------------
# Excess fan runtime
# ---------------------------------------------------------------------------
def compute_excess_runtime(ahu_faults: pd.DataFrame, ahu_name: str) -> pd.DataFrame:
    d = ahu_faults.copy()
    d["excess"] = d["unocc_run_satisfied"] & d["fan_on"]
    d["week"] = week_start(d["timestamp"])
    weekly = d.groupby("week").agg(
        total_fan_h=("fan_on", lambda x: hours_true(x)),
        excess_h=("excess", lambda x: hours_true(x)),
    ).reset_index()
    weekly["week"] = weekly["week"].astype(str).str[:10]
    weekly["ahu"] = ahu_name
    return weekly


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------
def chart_floor_weekly_temp(ts_df: pd.DataFrame) -> str:
    """Weekly average occupied zone temp °F — one line per floor."""
    fig = go.Figure()
    floor_order = ["First Floor", "Second Floor", "Fifth Floor", "Sixth Floor"]
    for i, fl in enumerate(floor_order):
        sub = ts_df[ts_df["floor"] == fl]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["week"], y=sub["avg_temp_f"], name=fl,
            mode="lines+markers", line=dict(width=2, color=COLORS["chart"][i % len(COLORS["chart"])]),
        ))
    fig.add_hline(y=COMFORT_SETPOINT_F, line_dash="dot", line_color=COLORS["accent"], annotation_text=f"{COMFORT_SETPOINT_F:g}°F target")
    fig.add_hrect(y0=COMFORT_LO_F, y1=COMFORT_HI_F, fillcolor=COLORS["good"], opacity=0.12, line_width=0)
    add_season_shading(fig)
    fig.update_layout(
        title="Weekly average zone temperature by floor (occupied hours, °F)",
        xaxis_title="Week starting",
        yaxis_title="Average zone temp °F",
        hovermode="x unified",
    )
    return fig_to_div(fig, 440)


def chart_floor_rank(floor_rank: pd.DataFrame) -> str:
    fig = go.Figure()
    for season in [SEASON_SHORT[s] for s in SEASONS]:
        sub = floor_rank[floor_rank["season_short"] == season].sort_values("rank")
        if sub.empty:
            continue
        fig.add_trace(go.Bar(
            x=sub["floor"].astype(str), y=sub["pct"],
            name=season, text=sub["rank"].apply(lambda r: f"#{int(r)}"), textposition="outside",
        ))
    fig.update_layout(
        title="Floor comfort ranking by season (% occupied hours within 72°F ±2°F — higher is better)",
        barmode="group", yaxis_title="Comfort %", xaxis_title="Floor",
    )
    fig.add_hline(y=90, line_dash="dot", line_color=COLORS["good"])
    return fig_to_div(fig, 420)


def chart_oat_binned_mech(bins_df: pd.DataFrame) -> str:
    """Chiller run hours by Open-Meteo OAT bin (pump_on + command per chiller)."""
    if bins_df.empty:
        return "<p class='note'>No bin data.</p>"
    fig = go.Figure()
    colors = {
        "Chiller 1": COLORS["chart"][0],
        "Chiller 2": COLORS["chart"][1],
    }
    for src in bins_df["source"].unique():
        sub = bins_df[bins_df["source"] == src]
        fig.add_trace(go.Bar(
            x=sub["bin_label"], y=sub["hours"], name=src,
            marker_color=colors.get(src, COLORS["accent"]),
        ))
    fig.update_layout(
        title="Chiller run hours by Open-Meteo outdoor air temperature (5°F bins)",
        xaxis_title="Open-Meteo OAT bin °F",
        yaxis_title="Run hours (command + meter kW > 0.5)",
        barmode="group",
    )
    return fig_to_div(fig, 440)


def chart_open_meteo_free_cool(daily: pd.DataFrame) -> str:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=daily["day"], y=daily["avail_h"], name="Free-cool hours available (DP<60, OAT<72)",
        marker_color=COLORS["good"], opacity=0.7,
    ), secondary_y=False)
    fig.add_trace(go.Bar(
        x=daily["day"], y=daily["wasted_mech_h"], name="Mech cooling during available free-cool",
        marker_color=COLORS["bad"],
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=daily["day"], y=daily["avg_oat"], name="Open-Meteo OAT °F",
        mode="lines", line=dict(color=COLORS["chart"][4], width=1.5),
    ), secondary_y=True)
    add_season_shading(fig)
    fig.update_layout(
        title="Daily free-cooling availability (Open-Meteo) vs wasted AHU mechanical cooling",
        hovermode="x unified", barmode="overlay",
    )
    fig.update_yaxes(title_text="Hours", secondary_y=False)
    fig.update_yaxes(title_text="°F", secondary_y=True)
    return fig_to_div(fig, 460)


def chart_weather_fault_by_hour(hour_df: pd.DataFrame) -> str:
    if hour_df.empty:
        return "<p class='note'>No weather fault hours in period.</p>"
    fig = go.Figure()
    for ahu in hour_df["ahu"].unique():
        sub = hour_df[hour_df["ahu"] == ahu]
        for season in sub["season"].unique():
            s = sub[sub["season"] == season]
            fig.add_trace(go.Bar(
                x=s["hour"], y=s["fault_h"], name=f"{ahu} {season}",
            ))
    fig.update_layout(
        title="OAT sensor fault hours by time of day (local hour, |BAS−Open-Meteo| > 5°F)",
        xaxis_title="Hour of day", yaxis_title="Fault hours",
        barmode="stack",
    )
    return fig_to_div(fig, 420)


def chart_ahu_fc1_season(d: pd.DataFrame, title: str) -> str:
    seasons = [SEASON_SHORT[s] for s in SEASONS]
    hours = [hours_true(d.loc[d["season"] == s, "fc1_duct_static"]) for s in SEASONS]
    fig = go.Figure(go.Bar(x=seasons, y=hours, marker_color=COLORS["bad"], name="FC1 hours"))
    fig.update_layout(
        title=f"{title} — FC1 duct static fault hours by season",
        yaxis_title="Fault hours",
    )
    return fig_to_div(fig, 360)


def chart_ahu_temp_faults_season(d: pd.DataFrame, title: str) -> str:
    """Temperature-related fault hours — hours only, grouped bars."""
    rules = [
        ("fc2_mat_below", "FC2 MAT low"), ("fc3_mat_above", "FC3 MAT high"),
        ("fc8_sat_above_blend_econ", "FC8"), ("fc9_oat_too_warm_free_cool", "FC9"),
        ("fc10_oat_mat_mismatch_mech", "FC10"), ("fc11_oat_mat_mismatch_econ", "FC11"),
        ("fc12_sat_above_blend_cool", "FC12"), ("fc13_sat_above_sp_full_cool", "FC13"),
        ("free_cool_opp", "Free cool opp."), ("econ2_unfavorable", "ECON-2"),
        ("econ3_mech_not_full_oa", "ECON-3 mech"),
        ("sv2_oat", "SV2 OAT"), ("sv6_oat_flat", "SV6 OAT flat"),
        ("sv7_oat_spike", "SV7 OAT spike"), ("sv6_mat_flat", "SV6 MAT flat"), ("sv7_mat_spike", "SV7 MAT spike"),
    ]
    seasons = [SEASON_SHORT[s] for s in SEASONS]
    fig = go.Figure()
    for col, label in rules:
        if col not in d.columns:
            continue
        y = [hours_true(d.loc[d["season"] == s, col]) for s in SEASONS]
        if sum(y) == 0:
            continue
        fig.add_trace(go.Bar(name=label, x=seasons, y=y))
    fig.update_layout(
        title=f"{title} — temperature & economizer fault hours by season",
        barmode="group", yaxis_title="Hours",
    )
    return fig_to_div(fig, 480)


def chart_ahu_hunting_season(d: pd.DataFrame, title: str) -> str:
    seasons = [SEASON_SHORT[s] for s in SEASONS]
    fig = go.Figure()
    for col, label in [("hunting_chw", "FC4 CHW"), ("hunting_econ", "FC4 econ"), ("hunting_sf", "FC4 fan")]:
        if col not in d.columns:
            continue
        y = [hours_true(d.loc[d["season"] == s, col]) for s in SEASONS]
        fig.add_trace(go.Bar(name=label, x=seasons, y=y))
    fig.update_layout(title=f"{title} — FC4 hunting fault hours", barmode="group", yaxis_title="Hours")
    return fig_to_div(fig, 360)


def chart_chiller_weekly_run(ch_daily: pd.DataFrame, ch_weekly: pd.DataFrame) -> str:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.12,
                        row_heights=[0.55, 0.45], subplot_titles=("Weekly chiller run hours", "Daily chiller run hours"))
    for label, color in [("Chiller 1", COLORS["chart"][0]), ("Chiller 2", COLORS["chart"][1])]:
        w = ch_weekly[ch_weekly["chiller"] == label]
        if not w.empty:
            fig.add_trace(go.Bar(x=w["week"], y=w["run_h"], name=f"{label} weekly", marker_color=color), row=1, col=1)
        dy = ch_daily[ch_daily["chiller"] == label]
        if not dy.empty:
            fig.add_trace(go.Scatter(x=dy["day"], y=dy["run_h"], name=f"{label} daily", mode="lines", line=dict(color=color)), row=2, col=1)
    add_season_shading(fig)
    fig.update_layout(title="Chiller run time — weekly totals and daily trend", hovermode="x unified", showlegend=True)
    fig.update_yaxes(title_text="Hours", row=1, col=1)
    fig.update_yaxes(title_text="Hours", row=2, col=1)
    return fig_to_div(fig, 520)


def chart_chiller_oat_bins(bins_df: pd.DataFrame) -> str:
    sub = bins_df[bins_df["source"].str.contains("Chiller")]
    if sub.empty:
        return "<p class='note'>No chiller bin data.</p>"
    fig = go.Figure()
    for src in sub["source"].unique():
        s = sub[sub["source"] == src]
        fig.add_trace(go.Bar(x=s["bin_label"], y=s["hours"], name=src))
    fig.update_layout(
        title="Chiller run hours by Open-Meteo OAT bin (5°F) — excess run below 55°F is RCx target",
        xaxis_title="Open-Meteo OAT bin °F", yaxis_title="Run hours", barmode="group",
    )
    return fig_to_div(fig, 400)


def chart_comfort_weekly_ts(ts_df: pd.DataFrame, spring_pct: float) -> str:
    fig = go.Figure()
    bldg = ts_df[ts_df["series"] == "Building (all zones)"]
    fig.add_trace(go.Scatter(
        x=bldg["week"], y=bldg["pct_comfort"], name="Building average",
        mode="lines+markers", line=dict(color=COLORS["accent"], width=3),
        marker=dict(size=6),
    ))
    floor_order = ["First Floor", "Second Floor", "Fifth Floor", "Sixth Floor"]
    for i, fl in enumerate(floor_order):
        sub = ts_df[ts_df["series"] == fl]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["week"], y=sub["pct_comfort"], name=fl,
            mode="lines", line=dict(width=1.5, dash="dot"), opacity=0.85,
        ))
    fig.add_hrect(y0=70, y1=74, fillcolor=COLORS["good"], opacity=0.12, line_width=0)
    fig.add_hline(y=90, line_dash="dot", line_color=COLORS["good"], annotation_text="90% target")
    add_season_shading(fig)
    fig.update_layout(
        title=f"ECM — Spring occupied comfort within 72°F ±2°F (avg {spring_pct:.1f}%)",
        xaxis_title="Week starting",
        yaxis_title="% of occupied zone samples in band",
        yaxis=dict(range=[0, 105]),
        hovermode="x unified",
    )
    return fig_to_div(fig, 400)


def chart_ecm_free_cool_ahu(fc_weekly: pd.DataFrame, ahu_total: float) -> str:
    fig = go.Figure()
    for src, color in [("AHU 1", COLORS["chart"][0]), ("AHU 2", COLORS["chart"][1])]:
        sub = fc_weekly[fc_weekly["source"] == src]
        if sub.empty:
            continue
        fig.add_trace(go.Bar(x=sub["week"], y=sub["hours"], name=src, marker_color=color))
    add_season_shading(fig)
    fig.update_layout(
        title=f"ECM — AHU free-cooling opportunity ({ahu_total:.0f} h total: CHW active when OAT allows economizer)",
        xaxis_title="Week starting", yaxis_title="Hours per week", barmode="stack",
    )
    return fig_to_div(fig, 380)


def chart_ecm_chiller_excess(ch_weekly: pd.DataFrame, ch2_h: float) -> str:
    sub = ch_weekly[ch_weekly["chiller"] == "Chiller 2"]
    if sub.empty:
        return "<p class='note'>No chiller data.</p>"
    ok = (sub["run_h"] - sub["free_cool_opp_h"]).clip(lower=0)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=sub["week"], y=ok, name="Expected run (OAT ≥ 55°F)", marker_color=COLORS["chart"][0], opacity=0.5))
    fig.add_trace(go.Bar(x=sub["week"], y=sub["free_cool_opp_h"], name="Excess run (OAT < 55°F)", marker_color=COLORS["bad"]))
    add_season_shading(fig)
    fig.update_layout(
        title=f"ECM — Chiller 2 excess runtime when Open-Meteo OAT < 55°F ({ch2_h:.0f} h total)",
        barmode="stack", xaxis_title="Week starting", yaxis_title="Run hours",
    )
    return fig_to_div(fig, 380)


def chart_ecm_excess_fan(excess_det: pd.DataFrame, total: float) -> str:
    fig = go.Figure()
    for ahu, color in [("AHU 1", COLORS["chart"][0]), ("AHU 2", COLORS["chart"][1])]:
        sub = excess_det[excess_det["ahu"] == ahu]
        fig.add_trace(go.Bar(x=sub["week"], y=sub["excess_fan_h"], name=f"{ahu} excess", marker_color=color))
    add_season_shading(fig)
    fig.update_layout(
        title=f"ECM — Excess unoccupied fan runtime ({total:.0f} h: zones 70–75°F, outside lease hours)",
        xaxis_title="Week starting", yaxis_title="Excess fan hours per week",
    )
    return fig_to_div(fig, 380)


def chart_free_cool_weekly(fc_weekly: pd.DataFrame, breakdown: dict) -> str:
    total = breakdown["total"]
    fig = go.Figure()
    colors = {"AHU 1": COLORS["chart"][0], "AHU 2": COLORS["chart"][1], "Chiller 2": COLORS["chart"][2], "Chiller 1": COLORS["chart"][3]}
    for src in ["AHU 1", "AHU 2", "Chiller 2", "Chiller 1"]:
        sub = fc_weekly[fc_weekly["source"] == src]
        if sub.empty or sub["hours"].sum() == 0:
            continue
        fig.add_trace(go.Bar(
            x=sub["week"], y=sub["hours"], name=src,
            marker_color=colors.get(src, COLORS["accent"]),
        ))
    totals = fc_weekly.groupby("week")["hours"].sum().reset_index()
    fig.add_trace(go.Scatter(
        x=totals["week"], y=totals["hours"].cumsum(), name="Cumulative total",
        mode="lines", line=dict(color=COLORS["warn"], width=2, dash="dash"),
        yaxis="y2",
    ))
    add_season_shading(fig)
    fig.update_layout(
        title=(
            f"Weekly free-cooling opportunity — {total:.0f} h total "
            f"(AHU CHW {breakdown['ahu_total']:.0f} h + chiller {breakdown['chiller_total']:.0f} h)"
        ),
        xaxis_title="Week starting",
        yaxis_title="Avoidable mech. cooling hours this week",
        barmode="stack",
        hovermode="x unified",
        yaxis2=dict(title="Cumulative hours", overlaying="y", side="right", showgrid=False),
    )
    return fig_to_div(fig, 480)


def chart_chiller_free_cool_weekly(ch_weekly: pd.DataFrame, ch2_total_opp: float) -> str:
    """Chiller run hours vs hours running when OAT supports free cooling instead."""
    sub = ch_weekly[ch_weekly["chiller"] == "Chiller 2"]
    if sub.empty:
        return "<p class='note'>No chiller data.</p>"
    avoidable = sub["free_cool_opp_h"]
    ok_run = (sub["run_h"] - sub["free_cool_opp_h"]).clip(lower=0)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=sub["week"], y=ok_run, name="Chiller 2 run (OAT ≥ 55°F)",
        marker_color=COLORS["chart"][0], opacity=0.5,
    ), secondary_y=False)
    fig.add_trace(go.Bar(
        x=sub["week"], y=avoidable, name="Excess chiller run (OAT < 55°F — use economizer)",
        marker_color=COLORS["bad"],
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=sub["week"], y=sub["avg_oat_f"], name="Avg OAT °F",
        mode="lines+markers", line=dict(color=COLORS["chart"][4], width=2),
    ), secondary_y=True)
    fig.add_hline(y=55, line_dash="dot", line_color=COLORS["good"],
                  annotation_text="55°F chiller enable / free-cool threshold", secondary_y=True)
    add_season_shading(fig)
    fig.update_layout(
        title=f"Chiller 2 weekly runtime — {ch2_total_opp:.0f} h excess run when outdoor air allows free cooling",
        barmode="stack", hovermode="x unified",
        xaxis_title="Week starting",
    )
    fig.update_yaxes(title_text="Chiller run hours", secondary_y=False)
    fig.update_yaxes(title_text="Outdoor air °F", secondary_y=True)
    return fig_to_div(fig, 480)


def chart_free_cool_daily_ts(daily: pd.DataFrame) -> str:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=daily["day"], y=daily["opp_h_ahu1"], name="AHU 1 opp. h",
        marker_color=COLORS["chart"][0], opacity=0.85,
    ), secondary_y=False)
    fig.add_trace(go.Bar(
        x=daily["day"], y=daily["opp_h_ahu2"], name="AHU 2 opp. h",
        marker_color=COLORS["chart"][1], opacity=0.85,
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=daily["day"], y=daily["web_oat"], name="Open-Meteo OAT",
        line=dict(color=COLORS["chart"][4], width=1.5),
    ), secondary_y=True)
    fig.add_hline(y=60, line_dash="dot", line_color=COLORS["good"],
                  annotation_text="60°F economizer threshold", secondary_y=True)
    add_season_shading(fig)
    fig.update_layout(
        title="Daily free-cooling opportunity hours vs outdoor temperature",
        barmode="stack", hovermode="x unified",
    )
    fig.update_yaxes(title_text="Opportunity hours", secondary_y=False)
    fig.update_yaxes(title_text="°F", secondary_y=True)
    return fig_to_div(fig, 460)


def chart_excess_weekly_stacked(detailed: pd.DataFrame, total_excess: float) -> str:
    fig = go.Figure()
    for ahu, color in [("AHU 1", COLORS["chart"][0]), ("AHU 2", COLORS["chart"][1])]:
        sub = detailed[detailed["ahu"] == ahu]
        fig.add_trace(go.Bar(
            x=sub["week"], y=sub["excess_fan_h"], name=f"{ahu} excess (unocc.)",
            marker_color=color,
        ))
        fig.add_trace(go.Bar(
            x=sub["week"], y=sub["occupied_fan_h"], name=f"{ahu} occupied",
            marker_color=color, opacity=0.35,
        ))
    cum = detailed.groupby("week")["excess_fan_h"].sum().cumsum().reset_index()
    fig.add_trace(go.Scatter(
        x=cum["week"], y=cum["excess_fan_h"], name="Cumulative excess",
        mode="lines+markers", line=dict(color=COLORS["bad"], width=2.5),
        yaxis="y2",
    ))
    add_season_shading(fig)
    fig.update_layout(
        title=f"Weekly fan runtime — excess unoccupied total {total_excess:.0f} h (zones 70–75°F satisfied)",
        barmode="group", hovermode="x unified",
        xaxis_title="Week starting",
        yaxis_title="Fan hours per week",
        yaxis2=dict(title="Cumulative excess h", overlaying="y", side="right", showgrid=False),
    )
    return fig_to_div(fig, 480)


def chart_excess_daily_ts(ahu1: pd.DataFrame, ahu2: pd.DataFrame) -> str:
    """Daily excess fan hours time series for both AHUs."""
    rows = []
    for df, name in [(ahu1, "AHU 1"), (ahu2, "AHU 2")]:
        d = df.copy()
        d["day"] = d["timestamp"].dt.tz_convert(TZ).dt.normalize()
        d["excess"] = d["unocc_run_satisfied"] & d["fan_on"]
        for day, g in d.groupby("day"):
            rows.append({"day": day, "ahu": name, "excess_h": hours_true(g["excess"])})
    daily = pd.DataFrame(rows)
    fig = go.Figure()
    for name, color in [("AHU 1", COLORS["chart"][0]), ("AHU 2", COLORS["chart"][1])]:
        sub = daily[daily["ahu"] == name]
        fig.add_trace(go.Scatter(
            x=sub["day"], y=sub["excess_h"], name=name,
            mode="lines", stackgroup="one", fillcolor=color, line=dict(width=0.5, color=color),
        ))
    add_season_shading(fig)
    fig.update_layout(
        title="Daily excess fan runtime (unoccupied, zones comfortable)",
        xaxis_title="Date", yaxis_title="Excess fan hours",
        hovermode="x unified",
    )
    return fig_to_div(fig, 420)


def chart_floor_comfort(floor_df: pd.DataFrame) -> str:
    fig = go.Figure()
    seasons = list(SEASONS.keys())
    floors = sorted(floor_df["floor"].dropna().unique(), key=lambda x: str(x))
    for i, fl in enumerate(floors):
        y = []
        for s in seasons:
            v = floor_df[(floor_df["season"] == s) & (floor_df["floor"] == fl)]["pct_within_72"]
            y.append(float(v.iloc[0]) if len(v) else 0)
        fig.add_trace(go.Bar(name=str(fl), x=[SEASON_SHORT[s] for s in seasons], y=y))
    fig.update_layout(barmode="group", title="Occupied hours within 72°F ±2°F by floor (%)", yaxis_title="% of time")
    fig.add_hline(y=90, line_dash="dot", line_color=COLORS["good"], annotation_text="90% target")
    return fig_to_div(fig)


def chart_monthly_zone_temp(weekly_df: pd.DataFrame) -> str:
    fig = go.Figure()
    for ahu in weekly_df["ahu"].unique():
        sub = weekly_df[weekly_df["ahu"] == ahu]
        fig.add_trace(go.Bar(name=ahu, x=sub["month"], y=sub["avg_zone_temp_f"]))
    fig.update_layout(barmode="group", title="Average zone temperature by month (occupied hours)", yaxis_title="°F")
    fig.add_hline(y=72, line_dash="dot", line_color=COLORS["accent"])
    fig.add_hrect(y0=70, y1=74, fillcolor=COLORS["good"], opacity=0.15, line_width=0)
    return fig_to_div(fig)


def chart_worst_vav(zone_df: pd.DataFrame, season: str, n: int = 15) -> str:
    sub = zone_df[zone_df["season"] == season].dropna(subset=["pct_within_72_occupied"])
    sub = sub.sort_values("pct_within_72_occupied").head(n)
    labels = sub.apply(lambda r: f"{r['floor']} {r['vav_id']}", axis=1)
    fig = go.Figure(go.Bar(
        x=sub["pct_within_72_occupied"], y=labels, orientation="h",
        marker_color=COLORS["warn"],
    ))
    fig.update_layout(
        title=f"Lowest comfort — {SEASON_SHORT[season]}",
        xaxis_title="% occupied hours within 72°F ±2°F",
        yaxis=dict(autorange="reversed"),
    )
    return fig_to_div(fig, 480)


def chart_weather(wx_df: pd.DataFrame, ahu: str) -> str:
    sub = downsample(wx_df, ["web_oat", f"bas_oat_{ahu}", f"fault_{ahu}"])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=sub["timestamp_local"], y=sub["web_oat"], name="Open-Meteo dry bulb", line=dict(color=COLORS["chart"][0])), secondary_y=False)
    fig.add_trace(go.Scatter(x=sub["timestamp_local"], y=sub[f"bas_oat_{ahu}"], name=f"AHU {ahu[-1]} BAS OAT", line=dict(color=COLORS["chart"][1])), secondary_y=False)
    fault = sub[f"fault_{ahu}"].astype(float) * (sub[[f"bas_oat_{ahu}", "web_oat"]].max(axis=1) + 5)
    fig.add_trace(go.Scatter(x=sub["timestamp_local"], y=fault, name="Fault |Δ|>5°F", mode="lines", line=dict(color=COLORS["bad"], width=1), fill="tozeroy", opacity=0.35), secondary_y=True)
    fig.update_yaxes(title_text="°F", secondary_y=False)
    fig.update_yaxes(title_text="Fault flag", secondary_y=True, range=[0, 120], showgrid=False)
    fig.update_layout(title=f"AHU {ahu[-1]} outdoor air vs web weather (fault when |Δ| > 5°F)")
    return fig_to_div(fig, 460)


def chart_weather_hist(wx_df: pd.DataFrame) -> str:
    fig = go.Figure()
    clip = 15.0
    for ahu, color in [("ahu1", COLORS["chart"][0]), ("ahu2", COLORS["chart"][1])]:
        vals = wx_df[f"delta_{ahu}"].dropna().clip(-clip, clip)
        fig.add_trace(go.Histogram(x=vals, name=f"AHU {ahu[-1]}", opacity=0.65, nbinsx=30))
    fig.update_layout(
        title="BAS minus Open-Meteo OAT delta (outliers clipped to ±15°F for readability)",
        xaxis_title="°F", barmode="overlay",
    )
    fig.add_vline(x=-5, line_dash="dash", line_color=COLORS["bad"])
    fig.add_vline(x=5, line_dash="dash", line_color=COLORS["bad"])
    return fig_to_div(fig)


    return fig_to_div(fig)


def chart_web_oat_vs_sat(d: pd.DataFrame, title: str) -> str:
    """Scatter: Open-Meteo dry bulb vs AHU supply air temp (fan on)."""
    sub = d[d["fan_on"] & d["web_oat"].notna() & d["sat"].notna()].copy()
    if sub.empty:
        return "<p class='note'>No overlapping Open-Meteo and SAT data.</p>"
    sub = downsample(sub, ["web_oat", "sat"], n=1200)
    fig = go.Figure(go.Scatter(
        x=sub["web_oat"], y=sub["sat"], mode="markers", name="Samples (fan on)",
        marker=dict(size=5, opacity=0.35, color=COLORS["chart"][0]),
    ))
    lo = float(min(sub["web_oat"].min(), sub["sat"].min()) - 2)
    hi = float(max(sub["web_oat"].max(), sub["sat"].max()) + 2)
    fig.add_trace(go.Scatter(
        x=[lo, hi], y=[lo, hi], mode="lines", name="1:1 line",
        line=dict(color=COLORS["muted"], dash="dash"),
    ))
    fig.update_layout(
        title=f"{title} — Open-Meteo OAT vs supply air temperature (fan on)",
        xaxis_title="Open-Meteo dry bulb °F",
        yaxis_title="Supply air temp °F",
    )
    return fig_to_div(fig, 440)


def chart_duct_static_violin(d: pd.DataFrame, title: str) -> str:
    """Violin/box of duct static when supply fan is running — static reset check."""
    sub = d[d["fan_on"] & d["duct_static"].notna()].copy()
    if sub.empty:
        return "<p class='note'>No duct static data when fan running.</p>"
    fig = go.Figure()
    fig.add_trace(go.Violin(
        y=sub["duct_static"], name="Duct static (fan on)",
        box_visible=True, meanline_visible=True,
        fillcolor=COLORS["chart"][0], line_color=COLORS["accent"], opacity=0.75,
    ))
    if sub["duct_sp"].notna().any():
        sp_med = float(sub["duct_sp"].median())
        fig.add_hline(
            y=sp_med, line_dash="dot", line_color=COLORS["warn"],
            annotation_text=f"Median SP {sp_med:.2f} in.w.c.",
        )
    fig.update_layout(
        title=f"{title} — duct static pressure distribution (fan running)",
        yaxis_title="Duct static in. w.c.",
    )
    return fig_to_div(fig, 400)


def chart_chws_vs_web_oat(d: pd.DataFrame, title: str) -> str:
    sub = d[d["pump_on"] & d["oat"].notna() & d["chws"].notna()].copy()
    if sub.empty:
        return "<p class='note'>No chiller pump-on samples with CHWS and Open-Meteo OAT.</p>"
    sub = downsample(sub, ["oat", "chws"], n=1000)
    fig = go.Figure(go.Scatter(
        x=sub["oat"], y=sub["chws"], mode="markers", name="Pump on",
        marker=dict(size=5, opacity=0.35, color=COLORS["chart"][2]),
    ))
    fig.update_layout(
        title=f"{title} — Open-Meteo OAT vs chilled-water supply (pump on)",
        xaxis_title="Open-Meteo dry bulb °F", yaxis_title="CHWS °F",
    )
    return fig_to_div(fig, 420)


def chart_hws_vs_web_oat(d: pd.DataFrame, title: str) -> str:
    sub = d[d["boiler_run"] & d["oat"].notna() & d["hws"].notna()].copy()
    if sub.empty:
        return "<p class='note'>No boiler run samples with HWS and Open-Meteo OAT.</p>"
    sub = downsample(sub, ["oat", "hws"], n=1000)
    fig = go.Figure(go.Scatter(
        x=sub["oat"], y=sub["hws"], mode="markers", name="Boiler run",
        marker=dict(size=5, opacity=0.35, color=COLORS["chart"][4]),
    ))
    fig.update_layout(
        title=f"{title} — Open-Meteo OAT vs hot-water supply (boiler run)",
        xaxis_title="Open-Meteo dry bulb °F", yaxis_title="HWS °F",
    )
    return fig_to_div(fig, 420)


def chart_ahu_trend(d: pd.DataFrame, ahu_label: str) -> str:
    sub = downsample(d, ["sat", "mat", "oat", "rat", "mad_pct", "clg", "econ"])
    fault_cols = [c for c in d.columns if c.startswith(("fc", "free_cool", "unocc", "hunting")) and d[c].dtype == bool]
    sub = sub.copy()
    sub["any_fault"] = d.loc[sub.index, fault_cols].any(axis=1).astype(float) * (sub["sat"].max() + 10)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.65, 0.35], vertical_spacing=0.06)
    for col, name in [("sat", "SAT"), ("mat", "MAT"), ("oat", "OAT"), ("rat", "RAT")]:
        fig.add_trace(go.Scatter(x=sub["timestamp_local"], y=sub[col], name=name, line=dict(width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=sub["timestamp_local"], y=sub["mad_pct"] * 100, name="MAD %", line=dict(color=COLORS["chart"][4])), row=1, col=1)
    fig.add_trace(go.Scatter(x=sub["timestamp_local"], y=sub["clg"] * 100, name="CHW valve %", line=dict(color=COLORS["chart"][2])), row=2, col=1)
    fig.add_trace(go.Scatter(x=sub["timestamp_local"], y=sub["econ"] * 100, name="Economizer %", line=dict(color=COLORS["chart"][3])), row=2, col=1)
    fig.add_trace(go.Scatter(x=sub["timestamp_local"], y=sub["any_fault"], name="Any fault", fill="tozeroy", line=dict(color=COLORS["bad"], width=0.5), opacity=0.4), row=2, col=1)
    fig.update_yaxes(title_text="°F / %", row=1, col=1)
    fig.update_yaxes(title_text="Commands / fault", row=2, col=1)
    fig.update_layout(title=f"{ahu_label} operating trends with fault overlay")
    return fig_to_div(fig, 520)


def chart_econ_summary(ahu1: pd.DataFrame, ahu2: pd.DataFrame, ahu_names: tuple[str, str]) -> str:
    rules = [
        ("fc8_sat_above_blend_econ", "FC8 SAT>blend econ"),
        ("fc9_oat_too_warm_free_cool", "FC9 OAT warm econ"),
        ("fc10_oat_mat_mismatch_mech", "FC10 OAT/MAT mech"),
        ("fc11_oat_mat_mismatch_econ", "FC11 OAT/MAT econ"),
        ("fc12_sat_above_blend_cool", "FC12 SAT>blend cool"),
        ("fc13_sat_above_sp_full_cool", "FC13 SAT>SP cool"),
        ("free_cool_opp", "Free cool opportunity"),
    ]
    seasons = list(SEASONS.keys())
    fig = go.Figure()
    for df, name in [(ahu1, ahu_names[0]), (ahu2, ahu_names[1])]:
        for rule, label in rules:
            y = []
            for s in seasons:
                m = df["season"] == s
                y.append(hours_true(df.loc[m, rule]))
            fig.add_trace(go.Bar(name=f"{name} {label}", x=[SEASON_SHORT[s] for s in seasons], y=y))
    fig.update_layout(barmode="group", title="Economizer & free-cooling fault hours by season", yaxis_title="Hours")
    return fig_to_div(fig, 500)


def chart_plant_trend(d: pd.DataFrame, title: str, run_col: str, fault_cols: list[str]) -> str:
    ts = d["timestamp_local"]
    sub_idx = downsample(d, [c for c in d.columns if c in (
        "chws", "chwr", "hws", "hwr", "oat", "power_kw", "delta_t", "hw_delta", "any_pump_on"
    )]).index
    sub = d.loc[sub_idx].copy()
    sub["fault_f"] = sub[fault_cols].any(axis=1).astype(float) * 15
    if "any_pump_on" in sub.columns:
        sub["pump_f"] = sub["any_pump_on"].astype(float) * 5
    elif "pump_on" in sub.columns:
        sub["pump_f"] = sub["pump_on"].astype(float) * 5

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if "chws" in sub.columns:
        fig.add_trace(go.Scatter(x=ts.loc[sub_idx], y=sub["chws"], name="CHWS °F"), secondary_y=False)
        fig.add_trace(go.Scatter(x=ts.loc[sub_idx], y=sub["chwr"], name="CHWR °F"), secondary_y=False)
    if "hws" in sub.columns:
        fig.add_trace(go.Scatter(x=ts.loc[sub_idx], y=sub["hws"], name="HWS °F"), secondary_y=False)
        fig.add_trace(go.Scatter(x=ts.loc[sub_idx], y=sub["hwr"], name="HWR °F"), secondary_y=False)
    if "power_kw" in sub.columns:
        fig.add_trace(go.Scatter(x=ts.loc[sub_idx], y=sub["power_kw"], name="kW"), secondary_y=False)
    if "pump_f" in sub.columns:
        fig.add_trace(go.Scatter(x=ts.loc[sub_idx], y=sub["pump_f"], name="Pump on", line=dict(dash="dot")), secondary_y=True)
    fig.add_trace(go.Scatter(x=ts.loc[sub_idx], y=sub["fault_f"], name="Fault", fill="tozeroy", opacity=0.35, line=dict(color=COLORS["bad"])), secondary_y=True)
    fig.update_layout(title=title)
    fig.update_yaxes(title_text="Temperature / Power", secondary_y=False)
    fig.update_yaxes(title_text="Status / fault", secondary_y=True, showgrid=False)
    return fig_to_div(fig, 460)


def chart_excess_runtime(w1: pd.DataFrame, w2: pd.DataFrame) -> str:
    fig = go.Figure()
    for wdf, name in [(w1, "AHU 1"), (w2, "AHU 2")]:
        fig.add_trace(go.Bar(name=f"{name} total fan h", x=wdf["week"], y=wdf["total_fan_h"]))
        fig.add_trace(go.Bar(name=f"{name} excess unocc h", x=wdf["week"], y=wdf["excess_h"]))
    fig.update_layout(barmode="group", title="Weekly supply fan runtime — excess = unoccupied with zones 70–75°F satisfied", yaxis_title="Hours")
    return fig_to_div(fig, 460)


def table_html(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "<p class='note'>No data.</p>"
    show = df.head(max_rows)
    hdr = "".join(f"<th>{c}</th>" for c in show.columns)
    body = ""
    for _, row in show.iterrows():
        body += "<tr>" + "".join(f"<td>{row[c]}</td>" for c in show.columns) + "</tr>"
    return f"<table><thead><tr>{hdr}</tr></thead><tbody>{body}</tbody></table>"


# ---------------------------------------------------------------------------
# Page bodies
# ---------------------------------------------------------------------------
def body_index(ctx: dict) -> str:
    zone_df = ctx["zone_df"]
    ahu1 = ctx["ahu1"]
    comfort_ts = ctx["comfort_ts"]
    fc_weekly = ctx["fc_weekly"]
    excess_det = ctx["excess_det"]
    fc_bd = ctx["fc_bd"]
    ch_fc_weekly = ctx["ch_fc_weekly"]
    oat_bins = ctx["oat_bins"]
    om_fc = ctx["om_fc"]
    t0 = ahu1["timestamp_local"].min()
    t1 = ahu1["timestamp_local"].max()
    spring = "Spring free-cooling / economizer season"
    spring_sub = zone_df[zone_df["season"] == spring]
    spring_pct = float(spring_sub["pct_within_72_occupied"].mean()) if len(spring_sub) else 0.0
    fc_hours = fc_bd["total"]
    unocc = float(excess_det["excess_fan_h"].sum())
    chw_pct = int(FREE_COOL_CHW_MIN * 100)

    kpis = f"""
<div class="grid">
  <div class="kpi"><div class="val">{len(load_zone_map())}</div><div class="lbl">Zone temperature sensors</div></div>
  <div class="kpi"><div class="val">{t0.strftime('%b %d')}</div><div class="lbl">First sample</div></div>
  <div class="kpi"><div class="val">{t1.strftime('%b %d')}</div><div class="lbl">Last sample</div></div>
  <div class="kpi"><div class="val">{spring_pct:.1f}%</div><div class="lbl">Spring economizer season comfort</div></div>
  <div class="kpi"><div class="val">{fc_hours:.0f}</div><div class="lbl">Free-cooling opportunity (AHU {fc_bd['ahu_total']:.0f} + chiller {fc_bd['chiller_total']:.0f} h)</div></div>
  <div class="kpi"><div class="val">{unocc:.0f}</div><div class="lbl">Excess unoccupied fan hours</div></div>
</div>"""
    return kpis


def body_zones(ctx: dict) -> str:
    from units import fmt_temp

    zone_df = ctx["zone_df"]
    floor_temp_ts = ctx["floor_temp_ts"]
    floor_rank = ctx["floor_rank"]
    comfort_ts = ctx.get("comfort_ts")
    spring_pct = ctx.get("spring_pct", 0.0)
    rank_table = zone_df.sort_values(["season", "pct_within_72_occupied"]).groupby("season").head(10)
    season_cards = "".join(
        f'<div class="card"><h2>{SEASON_SHORT[s]}</h2><div class="chart">{chart_worst_vav(zone_df, s)}</div></div>'
        for s in SEASONS
    )
    ecm1 = ""
    if comfort_ts is not None:
        ecm1 = ecm_card(
            "ECM-1",
            "COMFORT",
            "ECM 1 — Zone comfort",
            chart_html=chart_comfort_weekly_ts(comfort_ts, float(spring_pct)),
        )
    lo = fmt_temp(COMFORT_LO_F)
    hi = fmt_temp(COMFORT_HI_F)
    return f"""{ecm1}
<div class="card" data-rule="COMFORT"><h2>Weekly zone temperature by floor</h2>{rule_tune_mount("COMFORT")}
<p class="note">Average occupied zone temp — one line per floor. Green band = {lo}–{hi}.</p>
<div class="chart">{chart_floor_weekly_temp(floor_temp_ts)}</div></div>
<div class="card" data-rule="SV-1"><h2>Floor comfort ranking by season</h2>{rule_tune_mount("SV-1")}
<div class="chart">{chart_floor_rank(floor_rank)}</div></div>
{season_cards}
<div class="card"><h2>Worst zones — detail table</h2>{table_html(rank_table)}</div>"""


def body_weather(ctx: dict) -> str:
    wx_df = ctx["wx_df"]
    wx_hour = ctx["wx_hour"]
    s1 = wx_df.groupby("season").agg(
        ahu1_fault_h=("fault_ahu1", lambda x: hours_true(x)),
        ahu2_fault_h=("fault_ahu2", lambda x: hours_true(x)),
        ahu1_mean_abs=("delta_ahu1", lambda x: float(x.abs().mean())),
        ahu2_mean_abs=("delta_ahu2", lambda x: float(x.abs().mean())),
    ).round(2).reset_index()
    s1["season"] = s1["season"].map(lambda s: SEASON_SHORT.get(s, s))
    return f"""
<div class="card" data-rule="WS-OAT"><h2>What this shows</h2>{rule_tune_mount("WS-OAT")}
<p class="note">BAS OAT vs Open-Meteo. Fault when |Δ| &gt; {WEATHER_FAULT_DELTA_F:g}°F for 15 min. Use Open-Meteo for OAT bins — BAS sensors appear biased.</p>
</div>
<div class="card" data-rule="SV-2"><h2>AHU 1 OAT validation</h2>{rule_tune_mount("SV-2")}<div class="chart">{chart_weather(wx_df, 'ahu1')}</div></div>
<div class="card" data-rule="SV-2"><h2>AHU 2 OAT validation</h2><div class="chart">{chart_weather(wx_df, 'ahu2')}</div></div>
<div class="card"><h2>Temperature delta histogram</h2>
<p class="note">Outliers clipped ±15°F.</p><div class="chart">{chart_weather_hist(wx_df)}</div></div>
<div class="card"><h2>Fault hours by season</h2>{table_html(s1)}</div>
<div class="card"><h2>Fault hours by time of day</h2><div class="chart">{chart_weather_fault_by_hour(wx_hour)}</div></div>"""


def body_ahu(d: pd.DataFrame, title: str) -> str:
    summary = ahu_season_summary(d)
    return f"""
<div class="card"><h2>Operating trend</h2><div class="chart">{chart_ahu_trend(d, title)}</div></div>
<div class="card"><h2>Open-Meteo OAT vs supply air</h2>
<p class="note">Reference weather from Open-Meteo — not BAS outdoor-air sensors.</p>
<div class="chart">{chart_web_oat_vs_sat(d, title)}</div></div>
<div class="card"><h2>Duct static reset check</h2>
<p class="note">Violin plot of duct static when supply fan is running — tight distribution suggests active static reset.</p>
<div class="chart">{chart_duct_static_violin(d, title)}</div></div>
<div class="card" data-rule="FC1"><h2>FC1 — duct static fault</h2>{rule_tune_mount("FC1")}<p class="note">{FAULT_EQUATIONS['FC1']}</p>
<div class="chart">{chart_ahu_fc1_season(d, title)}</div></div>
<div class="card" data-rule="FC2"><h2>FC2 / FC3 — temperature & economizer faults</h2>{rule_tune_mount("FC2")}{rule_tune_mount("SV-4")}
<div class="chart">{chart_ahu_temp_faults_season(d, title)}</div></div>
<div class="card" data-rule="FC4"><h2>FC4 — hunting</h2>{rule_tune_mount("FC4")}<div class="chart">{chart_ahu_hunting_season(d, title)}</div></div>
<div class="card" data-rule="SV-6"><h2>Sensor validation (SV-2, SV-6, SV-7)</h2>{rule_tune_mount("SV-6")}{rule_tune_mount("SV-7")}
<p class="note">Flatline and spike checks on OAT/MAT — see fault table for hours.</p></div>
<div class="card"><h2>Full fault table (incl. fan wd/we)</h2>{table_html(summary, max_rows=50)}</div>"""


def body_economizer(ctx: dict) -> str:
    from units import fmt_temp

    ahu1 = ctx["ahu1"]
    ahu2 = ctx["ahu2"]
    fc_weekly = ctx["fc_weekly"]
    fc_bd = ctx["fc_bd"]
    om_fc = ctx["om_fc"]
    chw_pct = int(FREE_COOL_CHW_MIN * 100)
    oat_avail = fmt_temp(FREE_COOL_OAT_AVAIL_F)
    dp_max = fmt_temp(FREE_COOL_DP_MAX_F)
    econ_min = fmt_temp(ECONOMIZER_LOW_LIMIT_F)

    body = (
        ecm_card(
            "ECM-2",
            "ECON-3",
            "ECM 2 — AHU free-cooling opportunity",
            chart_html=chart_ecm_free_cool_ahu(fc_weekly, fc_bd["ahu_total"]),
            note=f"CHW &gt;{chw_pct}% while OAT favors economizer.",
        )
        + ecm_card(
            "ECM-6",
            "ECON-AVAIL",
            "ECM 6 — Free-cool weather availability",
            chart_html=chart_open_meteo_free_cool(om_fc),
            note=f"DP &lt; {dp_max} and OAT &lt; {oat_avail} (Open-Meteo).",
        )
        + f"""<div class="card" data-rule="FC8"><h2>FC8–FC13 season summary</h2>{rule_tune_mount("FC8")}{rule_tune_mount("ECON-3")}
<p class="note"><strong>{fc_bd['total']:.0f} h</strong> total opportunity — AHU 1: {fc_bd['ahu1_h']:.0f} · AHU 2: {fc_bd['ahu2_h']:.0f} · Chiller 2: {fc_bd['ch2_h']:.0f} h (Open-Meteo OAT &lt; {oat_avail})</p>
<p class="note">Free-cool availability: Open-Meteo dew point &lt; {dp_max} AND dry bulb &lt; {oat_avail} AND dry bulb ≥ {econ_min}. Min OA assumed {OA_MIN_EXPECTED_PCT:g}% · full economizer {OA_MAX_ECONOMIZER_PCT:g}%.</p></div>"""
    )
    for season in SEASONS:
        rows = []
        for df, name in [(ahu1, "AHU 1"), (ahu2, "AHU 2")]:
            m = df["season"] == season
            rows.append({
                "ahu": name,
                "fan_h": round(hours_true(df.loc[m, "fan_on"]), 1),
                "econ_avg_pct": round(float(df.loc[m, "econ"].mean() * 100), 1),
                "chw_avg_pct": round(float(df.loc[m, "clg"].mean() * 100), 1),
                "free_cool_opp_h": round(hours_true(df.loc[m, "free_cool_opp"]), 1),
                "fc8_h": round(hours_true(df.loc[m, "fc8_sat_above_blend_econ"]), 1),
                "fc9_h": round(hours_true(df.loc[m, "fc9_oat_too_warm_free_cool"]), 1),
            })
        body += f'<div class="card"><h2>{SEASON_SHORT[season]}</h2>{table_html(pd.DataFrame(rows))}</div>'
    body += _economizer_diagnostics_snippet()
    return body


def body_plant(ctx: dict) -> str:
    plant = ctx["plant"]
    fc_bd = ctx["fc_bd"]
    ch_fc_weekly = ctx["ch_fc_weekly"]
    ch_daily = ctx["ch_daily"]
    ch_weekly = ctx["ch_weekly"]
    oat_bins = ctx["oat_bins"]
    body = f"""
<div class="card" data-rule="CHILLER-DT"><h2>Central plant — chiller runtime</h2>{rule_tune_mount("CHILLER-DT")}{rule_tune_mount("ECON-AVAIL")}
<p class="note">Open-Meteo OAT bins. Chiller 2 excess below {FREE_COOL_OAT_AVAIL_F:g}°F: <strong>{fc_bd['ch2_h']:.0f} h</strong>.</p>
<div class="chart">{chart_chiller_weekly_run(ch_daily, ch_weekly)}</div>
<div class="chart">{chart_chiller_oat_bins(oat_bins)}</div>
<div class="chart">{chart_ecm_chiller_excess(ch_fc_weekly, fc_bd['ch2_h'])}</div>
</div>
<div class="card"><h2>Chiller supply vs Open-Meteo OAT</h2>
<p class="note">Scatter when chiller pump_on (command + kW &gt; 0.5). Reference weather is Open-Meteo.</p>
<div class="chart">{chart_chws_vs_web_oat(plant['CHILLER_1'], 'Chiller 1')}</div>
<div class="chart">{chart_chws_vs_web_oat(plant['CHILLER_2'], 'Chiller 2')}</div>
</div>
<div class="card"><h2>Boiler hot-water supply vs Open-Meteo OAT</h2>
<div class="chart">{chart_hws_vs_web_oat(plant['BOILERS_PUMPS'], 'Boilers')}</div>
</div>"""
    for key, title, run_col, faults in [
        ("CHILLER_1", "Chiller 1", "run", ["low_delta_t", "free_cool_opp", "below_enable"]),
        ("CHILLER_2", "Chiller 2", "run", ["low_delta_t", "free_cool_opp", "below_enable"]),
        ("BOILERS_PUMPS", "Boilers & HW Pumps", "boiler_run", ["warm_weather_run", "low_hw_delta"]),
    ]:
        d = plant[key]
        body += f'<div class="card"><h2>{title}</h2><div class="chart">{chart_plant_trend(d, title, run_col, faults)}</div></div>'
        rows = []
        for season in SEASONS:
            m = d["season"] == season
            row = {"season": SEASON_SHORT[season]}
            if "run" in d.columns:
                row["run_h"] = round(hours_true(d.loc[m, "run"]), 1)
                row["low_delta_t_h"] = round(hours_true(d.loc[m, "low_delta_t"]), 1)
                row["free_cool_opp_h"] = round(hours_true(d.loc[m, "free_cool_opp"]), 1)
            if "boiler_run" in d.columns:
                row["boiler_run_h"] = round(hours_true(d.loc[m, "boiler_run"]), 1)
                row["pump_run_h"] = round(hours_true(d.loc[m, "pump_on"]), 1)
            rows.append(row)
        body += f'<div class="card"><h3>{title} — season summary</h3>{table_html(pd.DataFrame(rows))}</div>'
    return body


def body_chiller_plant(ctx: dict) -> str:
    if ctx.get("missing"):
        return body_not_in_model("chiller", ["chiller_cmd", "chw_supply_temp"])
    from units import fmt_temp

    plant = ctx["plant"]
    fc_bd = ctx["fc_bd"]
    ch_fc_weekly = ctx["ch_fc_weekly"]
    ch_daily = ctx["ch_daily"]
    ch_weekly = ctx["ch_weekly"]
    oat_bins = ctx["oat_bins"]
    oat_avail = fmt_temp(FREE_COOL_OAT_AVAIL_F)
    body = (
        ecm_card(
            "ECM-3",
            "ECON-AVAIL",
            "ECM 3 — Chiller excess runtime",
            chart_html=chart_ecm_chiller_excess(ch_fc_weekly, fc_bd["ch2_h"]),
            note=f"Chiller run when Open-Meteo OAT &lt; {oat_avail} (free-cool availability gate).",
        )
        + ecm_card(
            "ECM-5",
            "CHILLER-DT",
            "ECM 5 — Chiller run by Open-Meteo OAT bin (5°F)",
            chart_html=chart_oat_binned_mech(oat_bins),
            tune=False,
            note="Chiller 1 &amp; 2 only — hours when command on and meter kW &gt; 0.5 (pump_on proxy).",
        )
        + f"""
<div class="card" data-rule="CHILLER-DT"><h2>Chiller plant detail</h2>{rule_tune_mount("CHILLER-DT")}{rule_tune_mount("ECON-AVAIL")}
<p class="note">Open-Meteo OAT bins. Chiller 2 excess below {oat_avail}: <strong>{fc_bd['ch2_h']:.0f} h</strong>.</p>
<div class="chart">{chart_chiller_weekly_run(ch_daily, ch_weekly)}</div>
<div class="chart">{chart_chiller_oat_bins(oat_bins)}</div>
</div>"""
    )
    for key in ("CHILLER_1", "CHILLER_2"):
        if key not in plant:
            continue
        d = plant[key]
        body += f'<div class="card"><h2>{key.replace("_", " ")}</h2><div class="chart">{chart_plant_trend(d, key, "run", ["low_delta_t", "free_cool_opp", "below_enable"])}</div></div>'
        body += f'<div class="card"><h2>{key} vs Open-Meteo OAT</h2><div class="chart">{chart_chws_vs_web_oat(d, key)}</div></div>'
    return body


def body_boiler_plant(ctx: dict) -> str:
    if ctx.get("missing"):
        return body_not_in_model("boiler", ["boiler_cmd", "hws_temp"])
    plant = ctx["plant"]
    body = f'<div class="card"><h2>Boiler plant</h2>{rule_tune_mount("BOILER-WARM")}{rule_tune_mount("BOILER-DT")}'
    if "BOILERS_PUMPS" in plant:
        body += f'<div class="chart">{chart_hws_vs_web_oat(plant["BOILERS_PUMPS"], "Boilers")}</div>'
        d = plant["BOILERS_PUMPS"]
        body += f'<div class="chart">{chart_plant_trend(d, "Boilers", "boiler_run", ["warm_weather_run", "low_hw_delta"])}</div>'
    body += "</div>"
    return body


def _economizer_diagnostics_snippet() -> str:
    path = OUT / "economizer_diagnostics.html"
    if path.is_file():
        html = path.read_text(encoding="utf-8")
        start = html.find("<main>")
        end = html.find("</main>")
        if start >= 0 and end > start:
            return f'<div class="card"><h2>Economizer diagnostics (FC engine)</h2>{html[start + 6 : end]}</div>'
    return ""


def body_motor_runtime(ctx: dict) -> str:
    from analytics_motors import MOTOR_POINT_ROLES

    motors = ctx.get("motors") or []
    if not motors:
        return body_not_in_model("motor/fan/pump", list(MOTOR_POINT_ROLES))
    rows = []
    for m in motors:
        rows.append({
            "equipment": m["label"],
            "role": m["point_role"],
            "total_h": m["total_hours"],
            "unocc_h": m["unoccupied_hours"],
            "excess_h": m["excess_hours"],
        })
    table = table_html(pd.DataFrame(rows))
    charts = ""
    excess_det = ctx.get("excess_det")
    if excess_det is not None and not getattr(excess_det, "empty", True):
        total_excess = excess_det["excess_fan_h"].sum()
        charts = f'<div class="chart">{chart_excess_weekly_stacked(excess_det, total_excess)}</div>'
    return f"""<div class="card" data-rule="EXCESS-FAN"><h2>Motor runtime — all modeled equipment</h2>
{rule_tune_mount("EXCESS-FAN")}
<p class="note">Motors discovered from Haystack point roles (fan %, pump_on, chiller_cmd, etc.). Excess = unoccupied runtime.</p>
{table}
{charts}
</div>"""


def rule_equipment_ids() -> list[str]:
    """AHU-like equipment available to the custom/ML rule lab."""
    try:
        from haystack_rdf.resolver import get_resolver

        return sorted(get_resolver().list_ahus())
    except Exception:
        return ["AHU_1", "AHU_2"]


def rule_ahu_frame(raw: dict, equipment_id: str) -> pd.DataFrame:
    """Normalized AHU frame (sat/mat/oat/rat/fan_on/…) for a rule context."""
    wx = raw["wx"]
    if equipment_id in raw.get("ahu_raw", {}):
        return _compute_ahu_for(raw, wx, equipment_id)
    if raw.get("ahu1_raw") is not None:
        return _compute_ahu1(raw, wx)
    raise KeyError(f"No AHU history available for {equipment_id}")


def rule_result_chart(plot_series: dict, fault_series, title: str) -> str:
    """Themed Plotly div for a rule plugin result — signals + fault overlay."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    x = None
    for name, series in (plot_series or {}).items():
        if series is None:
            continue
        s = pd.to_numeric(series, errors="coerce")
        x = s.index if x is None else x
        fig.add_trace(go.Scatter(y=s.values, x=list(range(len(s))), name=name, mode="lines"), secondary_y=False)
    if fault_series is not None:
        mask = fault_series.fillna(False).astype(bool).astype(int)
        fig.add_trace(
            go.Scatter(
                y=mask.values,
                x=list(range(len(mask))),
                name="Confirmed fault",
                fill="tozeroy",
                line=dict(color=COLORS["bad"]),
                opacity=0.4,
            ),
            secondary_y=True,
        )
    fig.update_layout(title=title)
    fig.update_yaxes(title_text="Signal", secondary_y=False)
    fig.update_yaxes(title_text="Fault (0/1)", secondary_y=True, showgrid=False, range=[0, 1.1])
    return fig_to_div(fig, 420)


def body_custom_rules(ctx: dict) -> str:
    """Shell for the custom / ML rule lab — populated by dashboard_rules.js."""
    return """
<div class="card">
  <h2>Custom &amp; ML rule lab</h2>
  <p class="note">Author faults as Python plugins in <code>rules/plugins/</code>. Each plugin declares a
  Pydantic manifest and a <code>compute(ctx)</code> function. The API only runs registered rule ids with
  validated numeric params — never arbitrary code over HTTP. ML rules follow the same pipeline
  (features → model → mask → confirm → hours).</p>
  <div id="rule-lab-errors" class="rule-lab-errors" hidden></div>
  <div class="rule-lab-controls">
    <label>Rule
      <select id="rule-select"></select>
    </label>
    <label>Equipment
      <select id="rule-equipment"></select>
    </label>
    <button type="button" class="btn primary" id="btn-run-rule">Run rule</button>
    <span class="tune-status" id="rule-run-status"></span>
  </div>
  <p class="note" id="rule-description"></p>
  <div id="rule-params" class="rule-lab-params"></div>
  <div class="rule-lab-controls" style="margin-top:.6rem">
    <button type="button" class="btn" id="btn-persist-fault" title="Write the confirmed fault series to .cache/feather/faults/">Persist fault &rarr; Feather store</button>
    <span class="tune-status" id="rule-persist-status"></span>
  </div>
</div>
<div id="rule-result"></div>

<div class="card ml-lab">
  <h2>ML lab &mdash; upload plugin &amp; install packages</h2>
  <p class="note"><strong>Local dev only.</strong> Uploading a Python rule and running
  <code>pip install</code> execute code on this host by design. Uploaded files land in
  <code>rules/plugins/</code> and must define a <code>RULE</code> manifest + <code>compute(ctx)</code>.</p>

  <div class="ml-grid">
    <div class="ml-panel">
      <h3>Upload a rule plugin (.py)</h3>
      <div class="rule-lab-controls">
        <input type="file" id="ml-upload-file" accept=".py" />
        <button type="button" class="btn primary" id="btn-ml-upload">Upload</button>
        <span class="tune-status" id="ml-upload-status"></span>
      </div>
      <label style="display:block;margin-top:.5rem">View plugin (read-only)
        <select id="ml-file-select"></select>
      </label>
      <pre class="ml-code" id="ml-file-view" aria-readonly="true">Select a plugin to view its source…</pre>
    </div>

    <div class="ml-panel">
      <h3>Install Python packages</h3>
      <div class="rule-lab-controls">
        <input type="text" id="ml-pip-input" placeholder="scikit-learn pandas==2.2.*" style="flex:1;min-width:12rem" />
        <button type="button" class="btn" id="btn-ml-pip">pip install</button>
        <span class="tune-status" id="ml-pip-status"></span>
      </div>
      <pre class="ml-code" id="ml-pip-output">pip output appears here…</pre>
      <h3 style="margin-top:1rem">Feather fault stores</h3>
      <p class="note">Persisted ML/rule faults (<code>.cache/feather/faults/</code>). Proof that
      pandas &rarr; model &rarr; fault mask round-trips to disk.</p>
      <div id="ml-fault-stores" class="ml-fault-stores"></div>
    </div>
  </div>
</div>"""


def body_excess(ctx: dict) -> str:
    from units import fmt_temp

    w1 = ctx["w1"]
    w2 = ctx["w2"]
    ahu1 = ctx["ahu1"]
    ahu2 = ctx["ahu2"]
    excess_det = ctx["excess_det"]
    total_excess = excess_det["excess_fan_h"].sum()
    pct = int(UNOCC_ZONE_PCT * 100)
    lo = fmt_temp(UNOCC_ZONE_LO_F)
    hi = fmt_temp(UNOCC_ZONE_HI_F)
    return (
        ecm_card(
            "ECM-4",
            "EXCESS-FAN",
            "ECM 4 — Excess unoccupied fan",
            chart_html=chart_ecm_excess_fan(excess_det, float(total_excess)),
        )
        + f"""
<div class="card"><h2>Excess fan runtime detail</h2>
<p class="note">Counts supply fan hours <strong>outside</strong> the lease schedule when at least {pct}% of mapped zones read {lo}–{hi}. Total: <strong>{total_excess:.0f} hours</strong> across both AHUs.</p>
<div class="chart">{chart_excess_weekly_stacked(excess_det, total_excess)}</div>
<div class="chart">{chart_excess_daily_ts(ahu1, ahu2)}</div></div>
<div class="card"><h2>Weekly detail — AHU 1</h2>{table_html(w1)}</div>
<div class="card"><h2>Weekly detail — AHU 2</h2>{table_html(w2)}</div>"""
    )


PAGE_BODY_BUILDERS = {
    "index": body_index,
    "zones": body_zones,
    "weather": body_weather,
    "ahu_1": lambda ctx: body_ahu(ctx["ahu1"], "AHU 1"),
    "ahu_2": lambda ctx: body_ahu(ctx["ahu2"], "AHU 2"),
    "economizer": body_economizer,
    "central_plant": body_plant,
    "chiller_plant": body_chiller_plant,
    "boiler_plant": body_boiler_plant,
    "motor_runtime": body_motor_runtime,
    "custom_rules": body_custom_rules,
    "excess_runtime": body_excess,
}


def load_raw_data() -> dict:
    """Load historian CSVs via Haystack SPARQL-resolved equipment paths."""
    refresh_data_paths()
    from haystack_rdf.data_loader import load_history_wide
    from haystack_rdf.resolver import get_resolver

    resolver = get_resolver()
    resolver.ensure_model()

    wx = load_history_wide("WEATHER", resolver)
    wx["timestamp"] = wx["timestamp_utc"]

    raw: dict = {"wx": wx, "ahu_raw": {}}
    ahus = sorted(resolver.list_ahus())
    for eq_id in ahus:
        raw["ahu_raw"][eq_id] = load_history_wide(eq_id, resolver)
    if len(ahus) >= 1:
        raw["ahu1_raw"] = raw["ahu_raw"][ahus[0]]
    if len(ahus) >= 2:
        raw["ahu2_raw"] = raw["ahu_raw"][ahus[1]]

    chillers = sorted(e["id"] for e in resolver.list_equipment(haystack_tag="chiller"))
    if len(chillers) >= 1:
        raw["ch1"] = load_history_wide(chillers[0], resolver)
    if len(chillers) >= 2:
        raw["ch2"] = load_history_wide(chillers[1], resolver)

    plant = [
        e["id"]
        for e in resolver.list_equipment()
        if e["id"].upper().startswith("BOILER") or "BOILER" in e["id"].upper()
    ]
    if plant:
        raw["blr"] = load_history_wide(plant[0], resolver)

    return raw


def raw_data_source_paths() -> list[Path]:
    """CSV files that invalidate in-memory cache — fast filesystem discovery (no SPARQL)."""
    global _source_paths_cache
    from haystack_rdf.auto_sync import csv_tree_mtime
    from haystack_rdf.csv_discovery import discover_historian_bundles

    tree_mtime = csv_tree_mtime()
    if _source_paths_cache is not None and _source_paths_cache[0] == tree_mtime:
        return _source_paths_cache[1]

    paths: list[Path] = []
    if DATA.is_dir():
        for bundle in discover_historian_bundles(DATA, building_dir=DATA):
            if bundle.history_path.is_file():
                paths.append(bundle.history_path)
    if WEATHER.is_dir():
        for bundle in discover_historian_bundles(WEATHER):
            if bundle.history_path.is_file():
                paths.append(bundle.history_path)
    wx = WEATHER / "history_wide.csv"
    if wx.is_file() and wx not in paths:
        paths.append(wx)

    result = paths or [wx]
    _source_paths_cache = (tree_mtime, result)
    return result


def _spring_comfort_pct(zone_df: pd.DataFrame) -> float:
    spring = "Spring free-cooling / economizer season"
    sub = zone_df[zone_df["season"] == spring]
    if sub.empty:
        return 0.0
    return float(sub["pct_within_72_occupied"].mean())


def _compute_ahu1(raw: dict, wx: pd.DataFrame) -> pd.DataFrame:
    z1 = zone_columns(raw["ahu1_raw"], "AHU_1")
    return compute_ahu_faults(prep_ahu(attach_open_meteo(raw["ahu1_raw"], wx), "mad_c"), z1)


def _compute_ahu2(raw: dict, wx: pd.DataFrame) -> pd.DataFrame:
    z2 = zone_columns(raw["ahu2_raw"], "AHU_2")
    return compute_ahu_faults(prep_ahu(attach_open_meteo(raw["ahu2_raw"], wx), "mad_c_pct"), z2)


def _mad_col(df: pd.DataFrame) -> str:
    return "mad_c_pct" if "mad_c_pct" in df.columns else "mad_c"


def _compute_ahu_for(raw: dict, wx: pd.DataFrame, equip_id: str) -> pd.DataFrame:
    df_raw = raw.get("ahu_raw", {}).get(equip_id)
    if df_raw is None:
        if equip_id and raw.get("ahu1_raw") is not None:
            df_raw = raw["ahu1_raw"]
        else:
            raise KeyError(f"No raw data for {equip_id}")
    zones = zone_columns(df_raw, equip_id.replace("-", "_").upper())
    return compute_ahu_faults(prep_ahu(attach_open_meteo(df_raw, wx), _mad_col(df_raw)), zones)


def _compute_economizer_metrics(
    ahu1: pd.DataFrame, ahu2: pd.DataFrame, plant: dict, wx: pd.DataFrame,
) -> dict[str, Any]:
    return {
        "fc_weekly": compute_free_cool_weekly(ahu1, ahu2, plant),
        "fc_daily": compute_free_cool_daily_ts(ahu1, ahu2, wx),
        "ch_fc_weekly": compute_chiller_fc_weekly(plant),
        "fc_bd": fc_hours_breakdown(ahu1, ahu2, plant),
        "oat_bins": compute_mech_cool_oat_bins(plant, wx),
        "om_fc": compute_open_meteo_free_cool(ahu1, ahu2, wx),
    }


def _compute_zones_bundle(raw: dict) -> dict[str, Any]:
    ahu1_raw = raw["ahu1_raw"]
    ahu2_raw = raw["ahu2_raw"]
    zone_df, floor_df, weekly_df = compute_zone_stats(ahu1_raw, ahu2_raw)
    return {
        "zone_df": zone_df,
        "floor_df": floor_df,
        "weekly_df": weekly_df,
        "floor_temp_ts": compute_floor_weekly_temp(ahu1_raw, ahu2_raw),
        "floor_rank": compute_floor_rank_by_season(zone_df),
        "comfort_ts": compute_comfort_weekly_ts(ahu1_raw, ahu2_raw),
        "spring_pct": _spring_comfort_pct(zone_df),
    }


def _compute_full_context(raw: dict) -> dict:
    wx = raw["wx"]
    ahu1 = _compute_ahu1(raw, wx)
    ahu2 = _compute_ahu2(raw, wx)
    plant = compute_plant(raw["ch1"], raw["ch2"], raw["blr"], wx)
    wx_df = compute_weather(raw["ahu1_raw"], raw["ahu2_raw"], wx)
    zones = _compute_zones_bundle(raw)
    econ = _compute_economizer_metrics(ahu1, ahu2, plant, wx)
    ch_daily, ch_weekly = compute_chiller_daily_weekly(plant)
    excess_det = compute_excess_weekly_detailed(ahu1, ahu2)
    return {
        "ahu1": ahu1,
        "ahu2": ahu2,
        "wx_df": wx_df,
        "wx_hour": compute_weather_fault_by_hour(wx_df),
        "plant": plant,
        "ch_daily": ch_daily,
        "ch_weekly": ch_weekly,
        "excess_det": excess_det,
        "w1": compute_excess_runtime(ahu1, "AHU_1"),
        "w2": compute_excess_runtime(ahu2, "AHU_2"),
        **zones,
        **econ,
    }


def compute_context(raw: dict, page_id: str | None = None) -> dict:
    """Build page context. When page_id is set, skip unrelated heavy work."""
    if page_id is None:
        return _compute_full_context(raw)

    wx = raw["wx"]

    if page_id == "weather":
        wx_df = compute_weather(raw["ahu1_raw"], raw["ahu2_raw"], wx)
        return {"wx_df": wx_df, "wx_hour": compute_weather_fault_by_hour(wx_df)}

    if page_id == "zones":
        return _compute_zones_bundle(raw)

    if page_id == "ahu_1":
        return {"ahu1": _compute_ahu1(raw, wx)}

    if page_id == "ahu_2":
        return {"ahu2": _compute_ahu2(raw, wx)}

    from page_registry import get_page, resolve_ahu_equipment

    eq = resolve_ahu_equipment(page_id)
    if eq and page_id.startswith("ahu_"):
        if eq not in raw.get("ahu_raw", {}):
            return {"missing": True, "equipment_id": eq}
        df = _compute_ahu_for(raw, wx, eq)
        if page_id == "ahu_1":
            return {"ahu1": df}
        if page_id == "ahu_2":
            return {"ahu2": df}
        title = get_page(page_id).title if get_page(page_id) else eq.replace("_", " ")
        return {"ahu_df": df, "title": title}

    if page_id == "motor_runtime":
        from analytics_motors import compute_motor_runtime, discover_motors
        from haystack_rdf.data_loader import load_history_wide
        from haystack_rdf.resolver import get_resolver

        resolver = get_resolver()
        motor_rows: list[dict] = []
        for spec in discover_motors(resolver):
            try:
                df = load_history_wide(spec.equipment_id, resolver)
                col = spec.column
                if not col or col not in df.columns:
                    continue
                ts = df["timestamp_utc"] if "timestamp_utc" in df.columns else df["timestamp"]
                occ = is_occupied(ts)
                stats = compute_motor_runtime(df, col, role=spec.point_role, occupied=occ, poll_seconds=POLL_SECONDS)
                motor_rows.append({
                    "equipment_id": spec.equipment_id,
                    "label": spec.label,
                    "point_role": spec.point_role,
                    **stats,
                })
            except Exception:
                continue
        ctx_out: dict = {"motors": motor_rows}
        if raw.get("ahu1_raw") is not None and raw.get("ahu2_raw") is not None:
            ahu1 = _compute_ahu1(raw, wx)
            ahu2 = _compute_ahu2(raw, wx)
            ctx_out["excess_det"] = compute_excess_weekly_detailed(ahu1, ahu2)
        return ctx_out

    if page_id == "chiller_plant":
        if "ch1" not in raw and "ch2" not in raw:
            return {"missing": True}
        plant = compute_plant(raw.get("ch1"), raw.get("ch2"), raw.get("blr"), wx)
        ahu1 = _compute_ahu1(raw, wx) if raw.get("ahu1_raw") is not None else None
        ahu2 = _compute_ahu2(raw, wx) if raw.get("ahu2_raw") is not None else None
        ch_daily, ch_weekly = compute_chiller_daily_weekly(plant)
        if ahu1 is not None and ahu2 is not None:
            econ = _compute_economizer_metrics(ahu1, ahu2, plant, wx)
        else:
            econ = {
                "fc_bd": {"ch2_h": 0, "total": 0, "ahu_total": 0, "ahu1_h": 0, "ahu2_h": 0, "chiller_total": 0},
                "ch_fc_weekly": pd.DataFrame(),
                "oat_bins": compute_mech_cool_oat_bins(plant, wx),
            }
        return {
            "plant": plant,
            "fc_bd": econ["fc_bd"],
            "ch_fc_weekly": econ["ch_fc_weekly"],
            "oat_bins": econ["oat_bins"],
            "ch_daily": ch_daily,
            "ch_weekly": ch_weekly,
        }

    if page_id == "boiler_plant":
        if "blr" not in raw:
            return {"missing": True}
        plant = compute_plant(raw.get("ch1"), raw.get("ch2"), raw["blr"], wx)
        return {"plant": plant}

    if page_id == "excess_runtime":
        ahu1 = _compute_ahu1(raw, wx)
        ahu2 = _compute_ahu2(raw, wx)
        return {
            "ahu1": ahu1,
            "ahu2": ahu2,
            "excess_det": compute_excess_weekly_detailed(ahu1, ahu2),
            "w1": compute_excess_runtime(ahu1, "AHU_1"),
            "w2": compute_excess_runtime(ahu2, "AHU_2"),
        }

    if page_id == "economizer":
        ahu1 = _compute_ahu1(raw, wx)
        ahu2 = _compute_ahu2(raw, wx)
        plant = compute_plant(raw["ch1"], raw["ch2"], raw["blr"], wx)
        return {"ahu1": ahu1, "ahu2": ahu2, "plant": plant, **_compute_economizer_metrics(ahu1, ahu2, plant, wx)}

    if page_id == "central_plant":
        plant = compute_plant(raw["ch1"], raw["ch2"], raw["blr"], wx)
        ahu1 = _compute_ahu1(raw, wx)
        ahu2 = _compute_ahu2(raw, wx)
        ch_daily, ch_weekly = compute_chiller_daily_weekly(plant)
        econ = _compute_economizer_metrics(ahu1, ahu2, plant, wx)
        return {
            "plant": plant,
            "fc_bd": econ["fc_bd"],
            "ch_fc_weekly": econ["ch_fc_weekly"],
            "oat_bins": econ["oat_bins"],
            "ch_daily": ch_daily,
            "ch_weekly": ch_weekly,
        }

    if page_id in ("economizer_diagnostics", "custom_rules"):
        return {}

    # index and unknown pages — full pipeline
    return _compute_full_context(raw)


def body_for_page(page_id: str, ctx: dict) -> str:
    if ctx.get("missing"):
        from page_registry import get_page

        spec = get_page(page_id)
        label = spec.title if spec else page_id.replace("_", " ")
        return body_not_in_model(label, spec.equipment_ids if spec else None)
    if "ahu_df" in ctx:
        body = body_ahu(ctx["ahu_df"], ctx.get("title", page_id))
    elif page_id in PAGE_BODY_BUILDERS:
        body = PAGE_BODY_BUILDERS[page_id](ctx)
    elif page_id == "economizer_diagnostics":
        body = _economizer_diagnostics_snippet() or "<p class='note'>Economizer diagnostics page not generated yet.</p>"
    else:
        raise KeyError(f"Unknown page: {page_id}")
    return body + page_fault_equations_block(page_id)


def render_page_html(
    page_id: str,
    ctx: dict,
    *,
    body_html: str | None = None,
    params: dict | None = None,
    notes: str = "",
    analyst_name: str = "",
    interactive: bool = False,
) -> str:
    from page_registry import page_titles as registry_titles

    fname = f"{page_id}.html"
    titles = registry_titles()
    title = titles.get(page_id, page_id)
    body = body_html if body_html is not None else body_for_page(page_id, ctx)
    params_block = ""
    if params and not interactive:
        from dashboard_params import params_summary_html

        params_block = params_summary_html(params, page_id)
    return page_html(
        title,
        fname,
        body,
        notes=notes,
        params_block=params_block,
        analyst_name=analyst_name,
        interactive=interactive,
        page_id=page_id,
    )


def export_csv_summaries(ctx: dict) -> None:
    ctx["oat_bins"].to_csv(OUT / "mech_cooling_oat_bins_open_meteo.csv", index=False)
    ctx["om_fc"].to_csv(OUT / "open_meteo_free_cool_daily.csv", index=False)
    ctx["zone_df"].to_csv(OUT / "zone_comfort_by_season.csv", index=False)
    ctx["floor_df"].to_csv(OUT / "floor_comfort_by_season.csv", index=False)


def write_all_pages(
    ctx: dict,
    *,
    params: dict | None = None,
    notes: dict | None = None,
    analyst_name: str = "",
    interactive: bool = False,
    include_economizer_diagnostics: bool = True,
) -> list[str]:
    notes = notes or {}
    pages = list(PAGE_BODY_BUILDERS.keys())
    if include_economizer_diagnostics:
        pages.append("economizer_diagnostics")
    for page_id in pages:
        html = render_page_html(
            page_id,
            ctx,
            params=params,
            notes=notes.get(page_id, ""),
            analyst_name=analyst_name,
            interactive=interactive,
        )
        (OUT / f"{page_id}.html").write_text(html, encoding="utf-8")
    return [f"{p}.html" for p in pages]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(params: dict | None = None) -> None:
    global meta
    from dashboard_params import apply_to_generate_dashboard, default_params, validate_params, write_defaults_file

    write_defaults_file()
    meta["created"] = pd.Timestamp.now(tz=TZ).strftime("%Y-%m-%d %H:%M")
    merge_params = validate_params(params or default_params())
    apply_to_generate_dashboard(__import__(__name__), merge_params)

    import plotly
    src_js = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
    shutil.copy(src_js, OUT / "plotly.min.js")

    raw = load_raw_data()
    ctx = compute_context(raw)
    export_csv_summaries(ctx)

    from economizer_diagnostics_page import build_page
    build_page(meta["created"])

    pages = write_all_pages(ctx, params=merge_params, interactive=False)

    summary = {
        "created": meta["created"],
        "pages": pages,
        "data_range": [
            str(ctx["ahu1"]["timestamp_local"].min()),
            str(ctx["ahu1"]["timestamp_local"].max()),
        ],
        "tune_params": merge_params,
    }
    (OUT / "report_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Generated", len(pages), "HTML pages in", OUT)


if __name__ == "__main__":
    main()
