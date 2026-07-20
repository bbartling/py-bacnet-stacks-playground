"""ESCO fuel dashboard — bills × Open-Meteo × peers (Excel-grade density)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from wattlab.benchmarks import Campus, annual_summary, compare_eui
from wattlab.benchmarks.fuel_weather import (
    align_fuel_and_degree_days,
    build_fuel_weather_report,
    campus_fuel_totals,
    demand_heatmap_frame,
    fit_weather_responses,
    intensity_heatmap_frame,
    residual_frame,
)
from wattlab.benchmarks.meters import ALLOCATION_METHODS, year_month_matrix
from wattlab.config import ARTIFACTS
from wattlab.contracts import WeatherRequest
from wattlab.weather.degree_days import DD_BASE_F
from wattlab.weather.open_meteo import download_archive_weather


def _continuous_months(start: str, end: str) -> list[str]:
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out: list[str] = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _fill_month_gaps(df: pd.DataFrame, month_col: str = "month") -> pd.DataFrame:
    if df.empty:
        return df
    months = _continuous_months(str(df[month_col].min()), str(df[month_col].max()))
    idx = pd.DataFrame({month_col: months})
    return idx.merge(df, on=month_col, how="left")


def _synthetic_hourly(campus: Campus) -> pd.Series:
    months = sorted(set.intersection(*(m.months() for m in campus.meters)))
    if not months:
        months = sorted({mo for meter in campus.meters for mo in meter.months()})
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
        raise ValueError("No overlapping bill months")
    start = date.fromisoformat(f"{months[0]}-01")
    y, mo = map(int, months[-1].split("-"))
    end = date(y, 12, 31) if mo == 12 else date(y, mo + 1, 1) - timedelta(days=1)
    today = date.today()
    if end >= today:
        end = today - timedelta(days=2)
    if end < start:
        raise ValueError(f"Bill window {start}→{end} not fetchable from Open-Meteo yet")
    req = WeatherRequest(
        latitude=lat, longitude=lon, start_date=start, end_date=end, allow_partial=True
    )
    df, meta = download_archive_weather(req, cache_dir=ARTIFACTS / "open_meteo_cache")
    return df, meta.model_dump(mode="json")


def render(*, campus: Campus | None = None) -> None:
    import plotly.express as px
    import plotly.graph_objects as go

    st.header("Fuel dashboard — ESCO energy use")
    st.caption(
        f"Monthly bills, Open-Meteo HDD/CDD (base {DD_BASE_F:g}°F), peer EUI bands. "
        "Load energy package on **Uploads**. Missing months stay blank — no fake continuity."
    )

    campus = campus or st.session_state.get("studio_campus") or st.session_state.get("fuel_weather_campus")
    if campus is None:
        energy = st.session_state.get("studio_energy")
        if energy is not None and getattr(energy, "campus", None) is not None:
            campus = energy.campus
            st.session_state["studio_campus"] = campus
    if campus is None:
        st.info("Load an energy-use package on **Uploads** first (campus.json + bill CSVs).")
        return

    shared = [m.meter_id for m in campus.meters if m.shared]
    if shared:
        st.caption(f"Shared meter(s): {', '.join(shared)} — allocation is a scenario, not truth.")

    alloc = st.selectbox(
        "Shared-meter allocation",
        list(ALLOCATION_METHODS[:3]),
        format_func=lambda m: {
            "area_weighted": "Area-weighted",
            "equal": "Equal",
            "gas_share": "Gas-share proxy",
        }.get(m, m),
        key="fuel_dash_allocation",
    )

    try:
        summary = annual_summary(campus, allocation=alloc)
    except ValueError as exc:
        st.error(f"Could not annualize: {exc}")
        return
    st.session_state["studio_benchmark_summary"] = summary

    w = summary["window"]
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Campus site EUI", f"{summary['campus']['site_eui_kbtu_ft2']} kBtu/ft²")
    a2.metric("Electric", f"{summary['campus']['kwh']:,.0f} kWh")
    a3.metric("Gas", f"{summary['campus']['mcf']:,.0f} Mcf")
    a4.metric("Window", f"{w['start']} → {w['end']}")

    # Peer strip — explicit typical / band metrics (spreadsheet-style)
    st.subheader("Site EUI vs peers (same property type)")
    st.caption(
        "Peer p20 / p50 (typical) / p80 from public EPA Portfolio Manager / CBECS-style "
        "registry (kBtu/ft²-yr). Twin page adds EnergyPlus model EUI beside these bands."
    )
    rows = []
    for b in summary["buildings"]:
        cmp = compare_eui(b["site_eui_kbtu_ft2"], b["property_type"])
        rows.append({**b, **{f"peer_{k}": cmp[k] for k in ("p20", "p50", "p80", "band", "vs_median_pct")}})
    dfb = pd.DataFrame(rows)
    b0 = rows[0]
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Bill site EUI", f"{b0['site_eui_kbtu_ft2']} kBtu/ft²")
    p2.metric("Peer typical (p50)", f"{b0['peer_p50']} kBtu/ft²")
    p3.metric("Peer p20–p80", f"{b0['peer_p20']} – {b0['peer_p80']}")
    p4.metric("vs median", f"{b0['peer_vs_median_pct']:+.1f}% · {b0['peer_band']}")
    st.dataframe(
        dfb[
            [
                "label",
                "floor_area_ft2",
                "kwh",
                "mcf",
                "site_eui_kbtu_ft2",
                "peer_p20",
                "peer_p50",
                "peer_p80",
                "peer_band",
                "peer_vs_median_pct",
            ]
        ],
        width="stretch",
        hide_index=True,
    )
    p20 = float(dfb["peer_p20"].iloc[0])
    p50 = float(dfb["peer_p50"].iloc[0])
    p80 = float(dfb["peer_p80"].iloc[0])
    fig_peer = go.Figure()
    fig_peer.add_shape(
        type="rect", x0=p20, x1=p80, y0=-0.5, y1=0.5,
        fillcolor="rgba(44,160,44,0.18)", line_width=0,
    )
    fig_peer.add_vline(x=p50, line_dash="dash", line_color="#2ca02c")
    for _, r in dfb.iterrows():
        fig_peer.add_scatter(
            x=[r["site_eui_kbtu_ft2"]], y=[0], mode="markers+text",
            marker=dict(symbol="diamond", size=16),
            text=[r["label"]], textposition="top center", name=r["label"],
        )
    fig_peer.update_layout(
        height=180, margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(visible=False), xaxis_title="Site EUI (kBtu/ft²-yr)",
        showlegend=False,
    )
    st.plotly_chart(fig_peer, width="stretch", key="fuel_peer_eui_chart")

    # Monthly tables + gap-aware charts
    st.subheader("Monthly fuel (gaps shown as blanks)")
    totals = campus_fuel_totals(campus)
    for fuel, g in totals.groupby("fuel"):
        unit = str(g["unit"].iloc[0])
        filled = _fill_month_gaps(g[["month", "usage", "kbtu"]].copy())
        st.markdown(f"**{fuel.title()}** ({unit})")
        st.dataframe(filled, width="stretch", hide_index=True, height=220)
        fig = go.Figure()
        fig.add_scatter(
            x=filled["month"], y=filled["usage"], mode="lines+markers",
            connectgaps=False, name=fuel,
        )
        fig.update_layout(
            height=300, margin=dict(l=10, r=10, t=30, b=10),
            title=f"{fuel.title()} — connectgaps=False",
            yaxis_title=unit,
        )
        st.plotly_chart(fig, width="stretch", key=f"fuel_monthly_{fuel}_chart")

    # Heatmaps
    st.subheader("Intensity & demand calendars")
    h1, h2, h3 = st.columns(3)
    with h1:
        mat = intensity_heatmap_frame(campus, fuel="electricity")
        if not mat.empty:
            st.plotly_chart(
                px.imshow(mat, aspect="auto", color_continuous_scale="YlOrRd", title="Elec kBtu/ft²"),
                width="stretch",
                key="fuel_heat_elec",
            )
    with h2:
        mat = intensity_heatmap_frame(campus, fuel="gas")
        if not mat.empty:
            st.plotly_chart(
                px.imshow(mat, aspect="auto", color_continuous_scale="Blues", title="Gas kBtu/ft²"),
                width="stretch",
                key="fuel_heat_gas",
            )
    with h3:
        mat = demand_heatmap_frame(campus)
        if not mat.empty:
            st.plotly_chart(
                px.imshow(mat, aspect="auto", color_continuous_scale="Viridis", title="Demand kW"),
                width="stretch",
                key="fuel_heat_demand",
            )
        else:
            st.caption("No demand_kw column in electric bills.")

    # Per-meter year×month matrix (Excel-like)
    with st.expander("Year × month usage matrices", expanded=False):
        for m in campus.meters:
            st.markdown(f"**{m.meter_id}** ({m.fuel})")
            st.dataframe(year_month_matrix(m.bills), width="stretch")

    # Weather
    st.subheader("Weather response (HDD / CDD)")
    lat = campus.lat
    lon = campus.lon
    lat_s = st.text_input("Latitude", value="" if lat is None else str(lat), key="fuel_dash_lat")
    lon_s = st.text_input("Longitude", value="" if lon is None else str(lon), key="fuel_dash_lon")
    w1, w2 = st.columns(2)
    if w1.button("Fetch Open-Meteo", key="fuel_dash_fetch"):
        try:
            lat_u = float(lat_s) if lat_s.strip() else (float(lat) if lat is not None else None)
            lon_u = float(lon_s) if lon_s.strip() else (float(lon) if lon is not None else None)
            if lat_u is None or lon_u is None:
                st.error("lat/lon required on campus.json or form.")
            else:
                with st.spinner("Open-Meteo…"):
                    df, meta = _fetch_open_meteo(campus, lat_u, lon_u)
                st.session_state["fuel_dash_hourly"] = df
                st.session_state["fuel_dash_meta"] = meta
                st.success(f"Open-Meteo OK — {meta.get('rows')} rows")
        except Exception as exc:
            st.error(f"Open-Meteo failed: {exc}")
    if w2.button("Synthetic seasonal OAT (offline)", key="fuel_dash_synth"):
        s = _synthetic_hourly(campus)
        st.session_state["fuel_dash_hourly"] = s.to_frame(name="dry_bulb_f")
        st.session_state["fuel_dash_meta"] = {"source": "synthetic_seasonal", "rows": int(len(s))}
        st.warning("Synthetic OAT — prefer Open-Meteo for real R².")

    hourly = st.session_state.get("fuel_dash_hourly")
    meta = st.session_state.get("fuel_dash_meta") or {}
    if hourly is None:
        st.info("Fetch Open-Meteo or use synthetic OAT for degree-day fits.")
        return

    aligned, window = align_fuel_and_degree_days(campus, hourly)
    if not window:
        st.warning("No overlapping months between bills and weather.")
        return
    st.caption(f"Analysis window {window[0]} → {window[-1]} · weather={meta.get('source', '?')}")
    fits = fit_weather_responses(aligned)
    if not fits:
        st.warning("Need ≥6 overlapping months for R².")
        return
    mcols = st.columns(len(fits))
    for col, fit in zip(mcols, fits):
        col.metric(f"{fit.fuel} R² ({fit.x_name.upper()})", f"{fit.r2:.3f}")

    for fit in fits:
        sub = aligned[aligned["fuel"] == fit.fuel]
        fig = go.Figure()
        fig.add_scatter(
            x=sub[fit.x_name], y=sub["usage"], mode="markers",
            text=sub["month"], name="Bills",
        )
        xs = np.linspace(float(sub[fit.x_name].min()), float(sub[fit.x_name].max()), 40)
        fig.add_scatter(x=xs, y=fit.slope * xs + fit.intercept, mode="lines", name=f"R²={fit.r2:.3f}")
        fig.update_layout(
            title=f"{fit.fuel} vs {fit.x_name.upper()}",
            height=340, margin=dict(l=10, r=10, t=40, b=10),
            xaxis_title=fit.x_name.upper(), yaxis_title=fit.unit,
        )
        st.plotly_chart(fig, width="stretch")
        res = residual_frame(aligned, fit)
        st.plotly_chart(
            px.bar(res, x="month", y="residual", title=f"{fit.fuel} residuals"),
            width="stretch",
        )

    report = build_fuel_weather_report(
        campus, hourly, weather_source=str(meta.get("source") or "unknown")
    )
    with st.expander("Fuel weather report JSON"):
        st.json(report)
