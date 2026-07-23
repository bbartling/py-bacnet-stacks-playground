"""ESCO fuel dashboard — tabbed Plotly workspaces (Phase 1 monthly + peers)."""

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

_PHASE2_STUBS = (
    "Interval Energy Analytics",
    "Cost & Tariff",
    "Carbon & Sustainability",
    "Meter Explorer",
    "Anomalies & Opportunities",
    "Projects & M&V",
    "Reports",
)


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


def _peer_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for b in summary["buildings"]:
        cmp = compare_eui(b["site_eui_kbtu_ft2"], b["property_type"])
        rows.append(
            {**b, **{f"peer_{k}": cmp[k] for k in ("p20", "p50", "p80", "band", "vs_median_pct")}}
        )
    return rows


def _render_portfolio(summary: dict[str, Any], campus: Campus, px, go) -> None:
    w = summary["window"]
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Campus site EUI", f"{summary['campus']['site_eui_kbtu_ft2']} kBtu/ft²")
    a2.metric("Electric", f"{summary['campus']['kwh']:,.0f} kWh")
    a3.metric("Gas", f"{summary['campus']['mcf']:,.0f} Mcf")
    a4.metric("Window", f"{w['start']} → {w['end']}")
    st.caption(
        "Cost / carbon / anomaly KPIs: **NEEDS_INPUT** (not in monthly campus package)."
    )

    st.subheader("Site EUI vs peers (same property type)")
    with st.expander("How buildings are benchmarked", expanded=False):
        st.markdown(
            "Site EUI is annualized utility energy ÷ floor area (kBtu/ft²·yr). "
            "Peer **p20 / p50 / p80** come from a public EPA/CBECS-style registry "
            "keyed by each building's `property_type` (office, school, …). "
            "Below p20 ≈ efficient vs peers; above p80 ≈ needs attention. "
            "This is a screening band — not ENERGY STAR scores or calibrated models."
        )
    rows = _peer_rows(summary)
    dfb = pd.DataFrame(rows)
    b0 = rows[0]
    p1, p2, p3, p4 = st.columns(4)
    p1.metric(
        "Bill site EUI",
        f"{b0['site_eui_kbtu_ft2']} kBtu/ft²",
        help="Annualized campus/building bills ÷ floor area (kBtu/ft²·yr).",
    )
    p2.metric(
        "Peer typical (p50)",
        f"{b0['peer_p50']} kBtu/ft²",
        help="Median peer site EUI for this property_type (EPA/CBECS-style registry).",
    )
    p3.metric(
        "Peer p20–p80",
        f"{b0['peer_p20']} – {b0['peer_p80']}",
        help="Typical peer band: p20 (efficient side) to p80 (high side).",
    )
    p4.metric(
        "vs median",
        f"{b0['peer_vs_median_pct']:+.1f}% · {b0['peer_band']}",
        help="Percent vs peer p50 and band label (efficient / typical / high).",
    )

    from wattlab.studio.eui_charts import eui_peer_bullet_figure

    # One band per property type when mixed; else shared band + one row per building
    series = []
    for _, r in dfb.iterrows():
        series.append(
            {
                "label": str(r["label"]),
                "eui": float(r["site_eui_kbtu_ft2"]),
                "color": "#1f77b4",
                "symbol": "diamond",
            }
        )
    # Use first building's peers as the screening band (same-type campuses);
    # per-building bands still show in the metrics / attention table.
    fig_peer = eui_peer_bullet_figure(
        peer_p20=float(dfb["peer_p20"].iloc[0]),
        peer_p50=float(dfb["peer_p50"].iloc[0]),
        peer_p80=float(dfb["peer_p80"].iloc[0]),
        series=series,
        title="Site EUI vs peer p20–p80 band",
    )
    st.plotly_chart(fig_peer, width="stretch", key="fuel_peer_eui_chart")

    # Stacked monthly by commodity
    totals = campus_fuel_totals(campus)
    if not totals.empty:
        pivot = (
            totals.pivot_table(index="month", columns="fuel", values="kbtu", aggfunc="sum")
            .sort_index()
        )
        fig_stack = go.Figure()
        for col in pivot.columns:
            fig_stack.add_bar(x=pivot.index.astype(str), y=pivot[col], name=str(col))
        fig_stack.update_layout(
            barmode="stack",
            height=340,
            margin=dict(l=10, r=10, t=30, b=10),
            title="Monthly site energy by commodity (kBtu)",
            yaxis_title="kBtu",
        )
        st.plotly_chart(fig_stack, width="stretch", key="fuel_stack_commodity")

    # Ranked buildings + attention
    st.subheader("Buildings needing attention")
    attention = dfb.sort_values("peer_vs_median_pct", ascending=False)
    st.dataframe(
        attention[
            [
                "label",
                "floor_area_ft2",
                "site_eui_kbtu_ft2",
                "peer_p50",
                "peer_band",
                "peer_vs_median_pct",
            ]
        ],
        width="stretch",
        hide_index=True,
    )
    fig_rank = px.bar(
        attention,
        x="site_eui_kbtu_ft2",
        y="label",
        orientation="h",
        title="Ranked site EUI (kBtu/ft²)",
    )
    st.plotly_chart(fig_rank, width="stretch", key="fuel_ranked_eui")


def _render_monthly(campus: Campus, summary: dict[str, Any], go) -> None:
    st.subheader("Monthly utility analytics")
    totals = campus_fuel_totals(campus)
    for fuel, g in totals.groupby("fuel"):
        unit = str(g["unit"].iloc[0])
        filled = _fill_month_gaps(g[["month", "usage", "kbtu"]].copy())
        st.markdown(f"**{fuel.title()}** ({unit})")
        st.dataframe(filled, width="stretch", hide_index=True, height=220)
        fig = go.Figure()
        fig.add_scatter(
            x=filled["month"],
            y=filled["usage"],
            mode="lines+markers",
            connectgaps=False,
            name=fuel,
        )
        fig.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=30, b=10),
            title=f"{fuel.title()} — gaps blank (connectgaps=False)",
            yaxis_title=unit,
        )
        st.plotly_chart(fig, width="stretch", key=f"fuel_monthly_{fuel}_chart")

    # Rolling 12-month EUI when enough history
    months = _continuous_months(summary["window"]["start"], summary["window"]["end"])
    if len(months) >= 12 and not totals.empty:
        by_m = totals.groupby("month", as_index=False)["kbtu"].sum().sort_values("month")
        by_m["roll_12_kbtu"] = by_m["kbtu"].rolling(12, min_periods=12).sum()
        area = float(summary["campus"].get("floor_area_ft2") or 0) or sum(
            float(b.get("floor_area_ft2") or 0) for b in summary["buildings"]
        )
        if area > 0:
            by_m["roll_12_eui"] = by_m["roll_12_kbtu"] / area
            fig_r = go.Figure()
            fig_r.add_scatter(
                x=by_m["month"],
                y=by_m["roll_12_eui"],
                mode="lines+markers",
                connectgaps=False,
                name="Rolling 12-mo EUI",
            )
            fig_r.update_layout(
                height=300,
                title="Rolling 12-month site EUI",
                yaxis_title="kBtu/ft²",
            )
            st.plotly_chart(fig_r, width="stretch", key="fuel_roll12_eui")

    years = sorted({m[:4] for m in months})
    if len(years) >= 2:
        from wattlab.studio.eui_charts import month_abbrev

        st.caption(f"YoY available across bill years {years[0]}…{years[-1]}.")
        yoy = totals.copy()
        yoy["year"] = yoy["month"].astype(str).str[:4]
        yoy["mm"] = yoy["month"].astype(str).str[5:7].map(month_abbrev)
        pivot = yoy.pivot_table(
            index="mm", columns="year", values="kbtu", aggfunc="sum"
        )
        # Keep calendar order Jan…Dec
        from wattlab.studio.eui_charts import MONTH_ABBREV

        pivot = pivot.reindex([m for m in MONTH_ABBREV if m in pivot.index])
        st.dataframe(pivot, width="stretch")
    else:
        st.caption("YoY compare: **NEEDS_INPUT** — need ≥2 calendar years of bills.")

    with st.expander("Year × month usage matrices", expanded=False):
        from wattlab.studio.eui_charts import month_abbrev_columns

        for m in campus.meters:
            st.markdown(f"**{m.meter_id}** ({m.fuel})")
            mat = year_month_matrix(m.bills)
            st.dataframe(month_abbrev_columns(mat), width="stretch")


def _render_weather(campus: Campus, px, go) -> None:
    from wattlab.benchmarks.fuel_weather import (
        bill_overlap_months,
        fit_window_choices,
        months_for_fit_years,
    )
    from wattlab.studio.eui_charts import month_abbrev_columns

    st.subheader("Weather & baseline analytics")
    st.caption(
        f"HDD/CDD base {DD_BASE_F:g}°F. Prefer Open-Meteo over synthetic OAT. "
        "Open-Meteo fetches **all** overlapping bill years; the fit window below "
        "only changes how many trailing months feed the OLS model."
    )
    available = bill_overlap_months(campus)
    choices = fit_window_choices(available)
    if available:
        st.caption(
            f"Bills overlap {choices['first']} → {choices['last']} "
            f"({choices['available_n']} months, up to {choices['max_years']} full year(s))."
        )
        max_y = max(1, int(choices["max_years"]))
        use_all = False
        if choices["available_n"] > max_y * 12:
            use_all = st.checkbox(
                f"Use all {choices['available_n']} overlapping months (not just full years)",
                value=True,
                key="fuel_dash_fit_all",
            )
        years_fit = st.slider(
            "Fit window: last N years",
            min_value=1,
            max_value=max_y,
            value=int(choices["default_years"]),
            key="fuel_dash_fit_years",
            disabled=use_all and choices["available_n"] > max_y * 12,
            help="OLS gas×HDD / elec×CDD uses the latest N×12 months (or all overlap).",
        )
        fit_months = months_for_fit_years(available, years_fit, use_all=use_all)
    else:
        fit_months = 12
        st.warning("No overlapping bill months across meters — cannot fit weather responses.")

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
                with st.spinner("Open-Meteo (full bill span)…"):
                    df, meta = _fetch_open_meteo(campus, lat_u, lon_u)
                st.session_state["fuel_dash_hourly"] = df
                st.session_state["fuel_dash_meta"] = meta
                st.success(f"Open-Meteo OK — {meta.get('rows')} rows (all bill years)")
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

    aligned, window = align_fuel_and_degree_days(campus, hourly, months=fit_months)
    if not window:
        st.warning("No overlapping months between bills and weather.")
        return
    st.caption(
        f"Fit window {window[0]} → {window[-1]} ({len(window)} mo) · "
        f"weather={meta.get('source', '?')}"
    )
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
            x=sub[fit.x_name],
            y=sub["usage"],
            mode="markers",
            text=sub["month"],
            name="Bills",
        )
        xs = np.linspace(float(sub[fit.x_name].min()), float(sub[fit.x_name].max()), 40)
        fig.add_scatter(
            x=xs, y=fit.slope * xs + fit.intercept, mode="lines", name=f"R²={fit.r2:.3f}"
        )
        fig.update_layout(
            title=f"{fit.fuel} vs {fit.x_name.upper()} ({len(sub)} mo)",
            height=340,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis_title=fit.x_name.upper(),
            yaxis_title=fit.unit,
        )
        st.plotly_chart(fig, width="stretch", key=f"fuel_wx_scatter_{fit.fuel}")
        res = residual_frame(aligned, fit)
        st.plotly_chart(
            px.bar(res, x="month", y="residual", title=f"{fit.fuel} residuals"),
            width="stretch",
            key=f"fuel_wx_resid_{fit.fuel}",
        )

    report = build_fuel_weather_report(
        campus, hourly, weather_source=str(meta.get("source") or "unknown"), months=fit_months
    )
    with st.expander("Fuel weather report JSON"):
        st.json(report)


def _render_demand(campus: Campus, px) -> None:
    from wattlab.studio.eui_charts import month_abbrev_columns

    st.subheader("Demand & peak analysis")
    mat = month_abbrev_columns(demand_heatmap_frame(campus))
    if mat.empty:
        st.info(
            "NEEDS_INPUT: no `demand_kw` column in electric bills — peak/demand charts unavailable."
        )
        return
    st.plotly_chart(
        px.imshow(mat, aspect="auto", color_continuous_scale="Viridis", title="Demand kW"),
        width="stretch",
        key="fuel_heat_demand",
    )
    # Monthly peak bars when heatmap has numeric values
    peaks = mat.max(axis=1)
    if not peaks.empty:
        fig = px.bar(
            x=peaks.index.astype(str),
            y=peaks.values,
            labels={"x": "year", "y": "peak_kw"},
            title="Peak demand by year (from bill demand_kw)",
        )
        st.plotly_chart(fig, width="stretch", key="fuel_monthly_peak")


def _render_data_quality(campus: Campus, summary: dict[str, Any]) -> None:
    st.subheader("Data quality")
    totals = campus_fuel_totals(campus)
    w = summary["window"]
    expected = _continuous_months(w["start"], w["end"])
    st.metric("Expected bill months", len(expected))
    for fuel, g in totals.groupby("fuel"):
        present = set(g["month"].astype(str))
        missing = [m for m in expected if m not in present]
        pct = 100.0 * (1.0 - len(missing) / max(len(expected), 1))
        st.markdown(f"**{fuel}** completeness {pct:.0f}% — missing {len(missing)} month(s)")
        if missing:
            st.caption(", ".join(missing[:24]) + ("…" if len(missing) > 24 else ""))
    st.caption(
        f"Allocation method is a scenario (not meter truth). Shared meters: "
        f"{[m.meter_id for m in campus.meters if m.shared] or 'none'}."
    )
    h1, h2 = st.columns(2)
    with h1:
        mat = intensity_heatmap_frame(campus, fuel="electricity")
        if not mat.empty:
            import plotly.express as px
            from wattlab.studio.eui_charts import month_abbrev_columns

            st.plotly_chart(
                px.imshow(
                    month_abbrev_columns(mat),
                    aspect="auto",
                    color_continuous_scale="YlOrRd",
                    title="Elec kBtu/ft²",
                ),
                width="stretch",
                key="fuel_heat_elec",
            )
    with h2:
        mat = intensity_heatmap_frame(campus, fuel="gas")
        if not mat.empty:
            import plotly.express as px
            from wattlab.studio.eui_charts import month_abbrev_columns

            st.plotly_chart(
                px.imshow(
                    month_abbrev_columns(mat),
                    aspect="auto",
                    color_continuous_scale="Blues",
                    title="Gas kBtu/ft²",
                ),
                width="stretch",
                key="fuel_heat_gas",
            )


def render(*, campus: Campus | None = None) -> None:
    import plotly.express as px
    import plotly.graph_objects as go

    st.header("Fuel dashboard — ESCO energy use")
    st.caption(
        f"Tabbed monthly analytics (Plotly). HDD/CDD base {DD_BASE_F:g}°F. "
        "Missing months stay blank — no fake continuity. Interval/Haystack tabs are Phase 2."
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

    tab_names = [
        "Portfolio Overview",
        "Monthly Utility Analytics",
        "Weather & Baseline",
        "Demand & Peak",
        "Data Quality",
        *_PHASE2_STUBS,
    ]
    tabs = st.tabs(tab_names)
    with tabs[0]:
        _render_portfolio(summary, campus, px, go)
    with tabs[1]:
        _render_monthly(campus, summary, go)
    with tabs[2]:
        _render_weather(campus, px, go)
    with tabs[3]:
        _render_demand(campus, px)
    with tabs[4]:
        _render_data_quality(campus, summary)
    for i, name in enumerate(_PHASE2_STUBS, start=5):
        with tabs[i]:
            st.info(
                f"**{name}** — Phase 2 / NEEDS_INPUT. Requires interval meters, tariffs, "
                "or carbon factors not present in the monthly campus package."
            )
