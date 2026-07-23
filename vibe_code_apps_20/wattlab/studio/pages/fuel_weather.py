"""Fuel Weather — campus bills × Open-Meteo HDD/CDD dashboard.

Data-model driven: any ``campus.json`` + meter CSVs. Example campuses
(``examples/liberty``, CI fixture) are practice data only — lat/lon and
ids come from the JSON, never from hardcoded production building logic.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from wattlab.benchmarks.fuel_weather import (
    align_fuel_and_degree_days,
    bill_overlap_months,
    build_fuel_weather_report,
    campus_fuel_totals,
    demand_heatmap_frame,
    fit_weather_responses,
    fit_window_choices,
    intensity_heatmap_frame,
    meter_monthly_long,
    months_for_fit_years,
    residual_frame,
)
from wattlab.benchmarks.meters import Campus
from wattlab.config import ARTIFACTS
from wattlab.contracts import WeatherRequest
from wattlab.weather.degree_days import DD_BASE_F
from wattlab.weather.open_meteo import download_archive_weather

ROOT = Path(__file__).resolve().parents[3]
# CI / AppTest default — privacy-safe fixture, not a named customer site.
DEFAULT_CAMPUS = ROOT / "tests" / "fixtures" / "shared_meter_campus" / "campus.json"
# Optional practice example path (gitignored CSVs); only used when loadable.
EXAMPLE_CAMPUS = ROOT / "examples" / "liberty" / "campus.json"


def resolve_default_campus_path() -> Path:
    """Default to the checked-in fixture; use a local example campus only if complete."""
    if EXAMPLE_CAMPUS.is_file():
        try:
            Campus.from_json(EXAMPLE_CAMPUS)
            return EXAMPLE_CAMPUS
        except FileNotFoundError:
            pass
    return DEFAULT_CAMPUS


def _coords_from_campus(campus: Campus) -> tuple[float | None, float | None]:
    return campus.lat, campus.lon


def _synthetic_hourly_for_campus(campus: Campus) -> pd.Series:
    """Offline seasonal OAT for AppTest / no-network demos (not site-specific climate)."""
    months = sorted(set.intersection(*(m.months() for m in campus.meters)))
    if not months:
        months = sorted({m for meter in campus.meters for m in meter.months()})
    start = datetime.fromisoformat(f"{months[0]}-01")
    y, mo = map(int, months[-1].split("-"))
    end = datetime(y + (1 if mo == 12 else 0), 1 if mo == 12 else mo + 1, 1)
    hours = max(int((end - start).total_seconds() // 3600), 24)
    idx = pd.date_range(start, periods=hours, freq="h")
    temps = [
        float(35.0 + 30.0 * np.sin(2 * np.pi * (ts.timetuple().tm_yday - 80) / 365.0))
        for ts in idx
    ]
    return pd.Series(temps, index=idx, name="dry_bulb_f")


def _fetch_open_meteo(campus: Campus, lat: float, lon: float) -> tuple[pd.DataFrame, dict[str, Any]]:
    months = sorted(set.intersection(*(m.months() for m in campus.meters)))
    if not months:
        raise ValueError("Campus has no overlapping bill months")
    start = date.fromisoformat(f"{months[0]}-01")
    y, mo = map(int, months[-1].split("-"))
    if mo == 12:
        end = date(y, 12, 31)
    else:
        end = date(y, mo + 1, 1) - timedelta(days=1)
    today = date.today()
    if end >= today:
        end = today - timedelta(days=2)
    if end < start:
        raise ValueError(f"Bill window {start}→{end} is not fetchable yet from Open-Meteo")
    req = WeatherRequest(
        latitude=lat,
        longitude=lon,
        start_date=start,
        end_date=end,
        allow_partial=True,
    )
    cache = ARTIFACTS / "open_meteo_cache"
    df, meta = download_archive_weather(req, cache_dir=cache)
    return df, meta.model_dump(mode="json")


def render(*, campus: Campus | None = None) -> None:
    import plotly.express as px
    import plotly.graph_objects as go

    st.header("Fuel Weather — bills × degree days")
    st.caption(
        "Monthly utility summaries via **campus.json** (any site) with Open-Meteo "
        f"HDD/CDD (base {DD_BASE_F:g}°F). Lat/lon come from the campus file or the "
        "form — never from hard-coded project cities. Interval meters use vibe19 "
        "Haystack ``column_map`` (Phase 2); monthly ``bill_columns`` maps are supported now."
    )

    default = resolve_default_campus_path()
    path = st.text_input(
        "campus.json path (buildings + meter bill CSVs)",
        value=str(st.session_state.get("fuel_weather_campus_path", default)),
        key="fuel_weather_campus_path_input",
        help=(
            "Schema-driven: any campus.json + sibling CSVs. "
            "CI default is tests/fixtures/shared_meter_campus/. "
            "examples/liberty/ is a practice example when local CSVs exist."
        ),
    )

    campus_preview_lat = None
    campus_preview_lon = None
    existing = campus or st.session_state.get("fuel_weather_campus")
    if existing is not None:
        campus_preview_lat, campus_preview_lon = _coords_from_campus(existing)

    c_load, c_lat, c_lon = st.columns([2, 1, 1])
    with c_load:
        load = st.button("Load campus bills", key="fuel_weather_load_campus")
    with c_lat:
        lat_str = st.text_input(
            "Latitude",
            value="" if campus_preview_lat is None else str(campus_preview_lat),
            key="fuel_weather_lat",
            help="From campus.json lat/latitude, or type a value. No city hardcodes.",
        )
    with c_lon:
        lon_str = st.text_input(
            "Longitude",
            value="" if campus_preview_lon is None else str(campus_preview_lon),
            key="fuel_weather_lon",
            help="From campus.json lon/longitude, or type a value. No city hardcodes.",
        )

    if load:
        try:
            loaded = Campus.from_json(path.strip())
            st.session_state["fuel_weather_campus"] = loaded
            st.session_state["fuel_weather_campus_path"] = path.strip()
            st.session_state.pop("fuel_weather_hourly", None)
            st.session_state.pop("fuel_weather_meta", None)
            st.success(
                f"Loaded {loaded.label} (id={loaded.campus_id}"
                + (f", siteRef={loaded.site_ref}" if loaded.site_ref else "")
                + f"): {len(loaded.buildings)} buildings, {len(loaded.meters)} meters."
            )
            if loaded.lat is None or loaded.lon is None:
                st.warning(
                    "campus.json has no lat/lon — enter coordinates before Fetch Open-Meteo, "
                    "or add \"lat\"/\"lon\" (or latitude/longitude) to the campus file."
                )
        except Exception as exc:
            st.error(f"Could not load campus: {exc}")

    campus = campus or st.session_state.get("fuel_weather_campus")
    if campus is None:
        st.info(
            "Load any campus.json to start. Practice examples: "
            "`examples/liberty/campus.json` (local CSVs) or the checked-in fixture. "
            "Production sites: ship your own campus.json + bill CSVs + coords."
        )
        return

    st.subheader("Meters")
    meter_rows = [
        {
            "meter_id": m.meter_id,
            "fuel": m.fuel,
            "unit": m.unit,
            "shared": m.shared,
            "serves": ", ".join(m.serves),
            "months": len(m.bills),
            "first": m.bills["month"].iloc[0] if len(m.bills) else "—",
            "last": m.bills["month"].iloc[-1] if len(m.bills) else "—",
        }
        for m in campus.meters
    ]
    st.dataframe(pd.DataFrame(meter_rows), width="stretch", hide_index=True)

    wx_col1, wx_col2 = st.columns(2)
    with wx_col1:
        fetch = st.button("Fetch Open-Meteo (live)", key="fuel_weather_fetch")
    with wx_col2:
        synth = st.button("Use synthetic seasonal OAT (offline)", key="fuel_weather_synth")

    if fetch:
        lat_use = lon_use = None
        try:
            if str(lat_str).strip():
                lat_use = float(lat_str)
            elif campus.lat is not None:
                lat_use = float(campus.lat)
            if str(lon_str).strip():
                lon_use = float(lon_str)
            elif campus.lon is not None:
                lon_use = float(campus.lon)
        except ValueError:
            st.error("lat/lon must be numeric.")
            lat_use = lon_use = None
        if lat_use is None or lon_use is None:
            st.error(
                "lat/lon required — put them on campus.json (`lat`/`lon`) or the form. "
                "Never rely on a hard-coded city."
            )
        else:
            try:
                with st.spinner("Downloading Open-Meteo archive…"):
                    df, meta = _fetch_open_meteo(campus, float(lat_use), float(lon_use))
                st.session_state["fuel_weather_hourly"] = df
                st.session_state["fuel_weather_meta"] = meta
                st.success(
                    f"Open-Meteo OK — {meta.get('rows')} hourly rows, "
                    f"sha {str(meta.get('sha256', ''))[:12]}…"
                )
            except Exception as exc:
                st.error(f"Open-Meteo fetch failed: {exc}")

    if synth:
        s = _synthetic_hourly_for_campus(campus)
        st.session_state["fuel_weather_hourly"] = s.to_frame(name="dry_bulb_f")
        st.session_state["fuel_weather_meta"] = {
            "source": "synthetic_seasonal",
            "rows": int(len(s)),
            "note": "Offline demo OAT — not measured weather",
        }
        st.warning("Using synthetic seasonal OAT (offline). Prefer Open-Meteo for real R².")

    hourly = st.session_state.get("fuel_weather_hourly")
    meta = st.session_state.get("fuel_weather_meta") or {}

    st.subheader("Fuel timeline")
    totals = campus_fuel_totals(campus)
    if totals.empty:
        st.warning("No bill rows to plot.")
        return
    for fuel, g in totals.groupby("fuel"):
        unit = str(g["unit"].iloc[0])
        fig = px.line(
            g, x="month", y="usage", markers=True,
            title=f"{fuel.title()} usage ({unit})",
            labels={"usage": unit, "month": "Bill month"},
        )
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, width="stretch")

    long = meter_monthly_long(campus)
    if "demand_kw" in long.columns and long["demand_kw"].notna().any():
        elec_d = long[long["fuel"] == "electricity"].dropna(subset=["demand_kw"])
        if not elec_d.empty:
            fig_d = px.line(
                elec_d, x="month", y="demand_kw", color="meter_id", markers=True,
                title="Billed demand (kW)",
            )
            fig_d.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_d, width="stretch")

    st.subheader("Intensity & demand heatmaps")
    from wattlab.studio.eui_charts import month_abbrev_columns

    h1, h2, h3 = st.columns(3)
    with h1:
        mat_e = month_abbrev_columns(intensity_heatmap_frame(campus, fuel="electricity"))
        if not mat_e.empty:
            fig = px.imshow(
                mat_e, aspect="auto", color_continuous_scale="YlOrRd",
                labels=dict(color="kBtu/ft²", x="Month", y="Year"),
                title="Electric intensity",
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.caption("No electric intensity matrix.")
    with h2:
        mat_g = month_abbrev_columns(intensity_heatmap_frame(campus, fuel="gas"))
        if not mat_g.empty:
            fig = px.imshow(
                mat_g, aspect="auto", color_continuous_scale="Blues",
                labels=dict(color="kBtu/ft²", x="Month", y="Year"),
                title="Gas intensity",
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.caption("No gas intensity matrix.")
    with h3:
        mat_d = month_abbrev_columns(demand_heatmap_frame(campus))
        if not mat_d.empty:
            fig = px.imshow(
                mat_d, aspect="auto", color_continuous_scale="Viridis",
                labels=dict(color="kW", x="Month", y="Year"),
                title="Billed demand",
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.caption("No demand_kw in bill CSVs.")

    st.subheader("Weather response (HDD / CDD)")
    available = bill_overlap_months(campus)
    choices = fit_window_choices(available)
    use_all = False
    years_fit = int(choices["default_years"]) or 1
    if available:
        st.caption(
            f"Open-Meteo pulls all bill years ({choices['first']}→{choices['last']}). "
            "Fit window only changes the OLS months."
        )
        max_y = max(1, int(choices["max_years"]))
        if choices["available_n"] > max_y * 12:
            use_all = st.checkbox(
                f"Use all {choices['available_n']} overlapping months",
                value=True,
                key="fuel_weather_fit_all",
            )
        years_fit = st.slider(
            "Fit window: last N years",
            min_value=1,
            max_value=max_y,
            value=int(choices["default_years"]),
            key="fuel_weather_fit_years",
            disabled=bool(use_all and choices["available_n"] > max_y * 12),
        )
    fit_months = months_for_fit_years(available, years_fit, use_all=use_all)

    if hourly is None:
        st.info("Fetch Open-Meteo or use synthetic OAT to compute HDD/CDD regressions.")
        return

    if meta:
        st.caption(
            f"Weather: {meta.get('source', '?')} · rows={meta.get('rows', '?')} · "
            f"base {DD_BASE_F:g}°F"
        )

    aligned, window = align_fuel_and_degree_days(campus, hourly, months=fit_months)
    if not window:
        st.warning("No overlapping months between bills and weather.")
        return
    st.caption(f"Fit window: {window[0]} → {window[-1]} ({len(window)} months)")

    fits = fit_weather_responses(aligned)
    if not fits:
        st.warning(f"Need ≥6 overlapping months for R² fits (have aligned rows={len(aligned)}).")
        return

    mcols = st.columns(len(fits))
    for col, fit in zip(mcols, fits):
        col.metric(
            f"{fit.fuel} R² ({fit.x_name.upper()})",
            f"{fit.r2:.3f}",
            help=f"y = {fit.slope:.4g}·{fit.x_name} + {fit.intercept:.4g} ({fit.unit}), n={fit.n}",
        )

    for fit in fits:
        sub = aligned[aligned["fuel"] == fit.fuel]
        fig = go.Figure()
        fig.add_scatter(
            x=sub[fit.x_name], y=sub["usage"], mode="markers",
            name="Bills", text=sub["month"],
            hovertemplate="%{text}: %{y:.1f} @ %{x:.1f}<extra></extra>",
        )
        x_line = np.linspace(float(sub[fit.x_name].min()), float(sub[fit.x_name].max()), 50)
        fig.add_scatter(
            x=x_line, y=fit.slope * x_line + fit.intercept, mode="lines",
            name=f"Fit R²={fit.r2:.3f}",
        )
        fig.update_layout(
            title=f"{fit.fuel.title()} vs {fit.x_name.upper()} (base {fit.base_f:g}°F)",
            xaxis_title=fit.x_name.upper(),
            yaxis_title=fit.unit,
            height=360,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig, width="stretch")
        res = residual_frame(aligned, fit)
        fig_r = px.bar(res, x="month", y="residual", title=f"{fit.fuel.title()} residuals")
        fig_r.update_layout(height=240, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_r, width="stretch")

    report = build_fuel_weather_report(
        campus, hourly,
        weather_source=str(meta.get("source") or "unknown"),
        months=fit_months,
    )
    with st.expander("Fuel weather report JSON"):
        st.json(report)

    st.caption(
        "Haystack (vibe19): interval meters use `equip`/`points` maps "
        "(`elec-power`/`gas-flow` → CSV headers) — see "
        "`vibe_code_apps_19/docs/COLUMN_MAP_JSON.md`. "
        "Monthly bills use campus `bill_columns` or header heuristics. "
        "Interval Fuel Weather UI is Phase 2."
    )
