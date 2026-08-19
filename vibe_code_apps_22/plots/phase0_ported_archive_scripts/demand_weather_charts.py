#!/usr/bin/env python
"""Demand load-profile charts + Open-Meteo Madison weather into vibe19 package."""
from __future__ import annotations


import sys
from pathlib import Path as _PathForLakeside

_APP = _PathForLakeside(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
from lakeside.paths import (  # noqa: E402
    BUILDING_LABEL,
    CAMPUS_ID,
    REGION_LABEL,
    app_root,
    clean_data_building_dir,
    eplus_dir,
    packages_dir,
    reports_dir,
    site_root,
    utilities_dir,
)
from lakeside.paths import BUILDING_ID as _LAKESIDE_BUILDING_ID  # noqa: E402
from lakeside.paths import SITE_REF as _LAKESIDE_SITE_REF  # noqa: E402
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

ROOT = site_root()
CLEAN = clean_data_building_dir()
METER = CLEAN / "CS_ELEC_METER" / "history_wide.csv"
CHARTS = ROOT / "plots" / "analytics"
REPORTS = ROOT / "reports"
PACKAGES = ROOT / "packages"
BUILDING_ID = "LAKESIDE_ES"

# Madison, WI (Open-Meteo)
MADISON_LAT = 43.0731
MADISON_LON = -89.4012
TZ_LOCAL = "America/Chicago"

# Chart look — school utility / night-ops (not purple-default)
BG = "#0f1419"
PANEL = "#1a222c"
INK = "#e8eef4"
MUTED = "#8b9aab"
WEEKDAY = "#3ecf8e"
WEEKEND = "#f0a04b"
ACCENT = "#5eb1ff"
GRID_C = "#2a3544"


def load_demand() -> pd.DataFrame:
    df = pd.read_csv(METER)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.sort_values("timestamp_utc").dropna(subset=["kw_demand"])
    df["ts_local"] = df["timestamp_utc"].dt.tz_convert(TZ_LOCAL)
    df["hour"] = df["ts_local"].dt.hour
    df["month"] = df["ts_local"].dt.to_period("M").astype(str)
    df["dow"] = df["ts_local"].dt.dayofweek  # Mon=0
    df["is_weekend"] = df["dow"] >= 5
    df["day_type"] = np.where(df["is_weekend"], "Weekend", "Weekday")
    return df


def fetch_open_meteo(start: str, end: str) -> pd.DataFrame:
    """Hourly historical-forecast Open-Meteo for Madison (°F)."""
    url = "https://historical-forecast-api.open-meteo.com/v1/forecast"
    params = {
        "latitude": MADISON_LAT,
        "longitude": MADISON_LON,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "dew_point_2m",
                "wind_speed_10m",
                "shortwave_radiation",
            ]
        ),
        "timezone": "UTC",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
    }
    print(f"Open-Meteo Madison {start}..{end} …")
    r = requests.get(url, params=params, timeout=120)
    r.raise_for_status()
    block = r.json().get("hourly") or {}
    if not block.get("time"):
        raise RuntimeError(f"Open-Meteo empty: {r.json().get('reason') or r.text[:200]}")
    wx = pd.DataFrame(
        {
            "timestamp_utc": pd.to_datetime(block["time"], utc=True),
            "web-outside-air-temp": block["temperature_2m"],
            "web-outside-air-humidity": block["relative_humidity_2m"],
            "web-outside-air-dewpoint": block["dew_point_2m"],
            "wind_speed_mph": block.get("wind_speed_10m"),
            "shortwave_radiation_wm2": block.get("shortwave_radiation"),
        }
    )
    # wetbulb via Stull if vibe19 available, else skip
    try:
        # Prefer sibling vibe_code_apps_19 (no hardcoded absolute paths).
        v19_root = _APP.parent / "vibe_code_apps_19"
        if v19_root.is_dir():
            sys.path.insert(0, str(v19_root))
            from app.weather_psychrometrics import enrich_weather_frame

            wx = enrich_weather_frame(wx)
    except Exception as exc:
        print(f"psychrometrics enrich skipped: {exc}")
    wx.attrs["open_meteo"] = {
        "lat": MADISON_LAT,
        "lon": MADISON_LON,
        "place": "Madison, WI",
        "start": start,
        "end": end,
        "fetched_utc": datetime.now(timezone.utc).isoformat(),
    }
    return wx.sort_values("timestamp_utc").drop_duplicates("timestamp_utc")


def write_weather_sidecar(wx: pd.DataFrame, demand: pd.DataFrame) -> Path:
    """Align hourly weather onto demand 5-min grid and write vibe19 weather/."""
    weather_dir = CLEAN / "weather"
    weather_dir.mkdir(parents=True, exist_ok=True)

    grid = pd.DatetimeIndex(demand["timestamp_utc"].unique()).sort_values()
    src = wx.set_index("timestamp_utc").sort_index()
    if src.index.tz is None:
        src.index = src.index.tz_localize("UTC")
    combined = src.index.union(grid)
    aligned = src.reindex(combined).sort_index()
    for c in aligned.columns:
        if pd.api.types.is_numeric_dtype(aligned[c]):
            aligned[c] = pd.to_numeric(aligned[c], errors="coerce").interpolate(
                method="time", limit_direction="both"
            )
    aligned = aligned.reindex(grid).reset_index()
    aligned = aligned.rename(columns={"index": "timestamp_utc"})
    if "timestamp_utc" not in aligned.columns:
        aligned = aligned.rename(columns={aligned.columns[0]: "timestamp_utc"})

    out = aligned.copy()
    out["timestamp_utc"] = pd.to_datetime(out["timestamp_utc"], utc=True).dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    # Keep vibe19-friendly column set
    keep = [
        c
        for c in [
            "timestamp_utc",
            "web-outside-air-temp",
            "web-outside-air-humidity",
            "web-outside-air-dewpoint",
            "web-outside-air-wetbulb",
            "wind_speed_mph",
            "shortwave_radiation_wm2",
        ]
        if c in out.columns
    ]
    out[keep].to_csv(weather_dir / "history_wide.csv", index=False)

    cols = pd.DataFrame(
        [
            {"column": "web-outside-air-temp", "point_role": "web-outside-air-temp", "units": "degF"},
            {"column": "web-outside-air-humidity", "point_role": "web-outside-air-humidity", "units": "%"},
            {"column": "web-outside-air-dewpoint", "point_role": "web-outside-air-dewpoint", "units": "degF"},
        ]
    )
    if "web-outside-air-wetbulb" in keep:
        cols = pd.concat(
            [
                cols,
                pd.DataFrame(
                    [
                        {
                            "column": "web-outside-air-wetbulb",
                            "point_role": "web-outside-air-wetbulb",
                            "units": "degF",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    cols.to_csv(weather_dir / "columns.csv", index=False)

    meta = {
        "source": "external_weather_open_meteo",
        "place": "Madison, WI",
        "lat": MADISON_LAT,
        "lon": MADISON_LON,
        "timezone_fetch": "UTC",
        "aligned_to": "CS_ELEC_METER 5-min grid",
        "rows": len(out),
        "fetched_utc": datetime.now(timezone.utc).isoformat(),
    }
    (weather_dir / "manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    # Also stash raw hourly for reports
    REPORTS.mkdir(parents=True, exist_ok=True)
    wx_out = wx.copy()
    wx_out["timestamp_utc"] = pd.to_datetime(wx_out["timestamp_utc"], utc=True).dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    wx_out.to_csv(REPORTS / "open_meteo_madison_hourly.csv", index=False)
    print(f"wrote weather sidecar: {weather_dir} ({len(out)} rows)")
    return weather_dir


def style_ax(ax) -> None:
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=MUTED)
    for spine in ax.spines.values():
        spine.set_color(GRID_C)
    ax.grid(True, color=GRID_C, alpha=0.6, lw=0.6)


def chart_monthly_load_profiles(demand: pd.DataFrame) -> Path:
    """Avg kW by hour-of-day, one panel per month, weekday vs weekend."""
    CHARTS.mkdir(parents=True, exist_ok=True)
    prof = (
        demand.groupby(["month", "day_type", "hour"], as_index=False)["kw_demand"]
        .mean()
        .rename(columns={"kw_demand": "kw_avg"})
    )
    months = sorted(prof["month"].unique())
    n = len(months)
    ncols = 3
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(13.5, 3.2 * nrows), sharey=True)
    fig.patch.set_facecolor(BG)
    axes = np.atleast_1d(axes).ravel()

    for i, month in enumerate(months):
        ax = axes[i]
        style_ax(ax)
        sub = prof[prof["month"] == month]
        for day_type, color in (("Weekday", WEEKDAY), ("Weekend", WEEKEND)):
            s = sub[sub["day_type"] == day_type].sort_values("hour")
            if s.empty:
                continue
            ax.plot(s["hour"], s["kw_avg"], color=color, lw=2.2, label=day_type)
            ax.fill_between(s["hour"], s["kw_avg"], alpha=0.15, color=color)
        ax.set_title(month, color=INK, fontsize=11, pad=6)
        ax.set_xlim(0, 23)
        ax.set_xticks([0, 6, 12, 18, 23])
        ax.set_xlabel("Hour (local)", color=MUTED, fontsize=8)
        if i % ncols == 0:
            ax.set_ylabel("Avg kW", color=MUTED, fontsize=9)

    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", facecolor=PANEL, edgecolor=GRID_C, labelcolor=INK)
    fig.suptitle(
        "Lakeside electric demand — monthly diurnal shape\nWeekday vs weekend averages (America/Chicago)",
        color=INK,
        fontsize=14,
        y=0.995,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = CHARTS / "demand_monthly_weekday_weekend_profiles.png"
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)
    print(f"chart: {out}")

    # Also write tidy profile CSV for reuse
    prof.to_csv(REPORTS / "demand_diurnal_profiles_by_month.csv", index=False)
    return out


def chart_overall_weekday_weekend(demand: pd.DataFrame) -> Path:
    """Single overlay: overall weekday vs weekend mean shape + monthly heatmap of peak."""
    CHARTS.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 4.8), gridspec_kw={"width_ratios": [1.1, 1]})
    fig.patch.set_facecolor(BG)

    ax = axes[0]
    style_ax(ax)
    for day_type, color in (("Weekday", WEEKDAY), ("Weekend", WEEKEND)):
        s = (
            demand[demand["day_type"] == day_type]
            .groupby("hour")["kw_demand"]
            .mean()
            .reindex(range(24))
        )
        ax.plot(s.index, s.values, color=color, lw=2.6, label=day_type)
        ax.fill_between(s.index, s.values, alpha=0.18, color=color)
    ax.set_title("All-period diurnal average", color=INK)
    ax.set_xlabel("Hour (local)", color=MUTED)
    ax.set_ylabel("Avg kW", color=MUTED)
    ax.set_xlim(0, 23)
    ax.legend(facecolor=PANEL, edgecolor=GRID_C, labelcolor=INK)

    ax2 = axes[1]
    style_ax(ax2)
    pivot = (
        demand.groupby(["month", "day_type"])["kw_demand"]
        .mean()
        .unstack("day_type")
        .sort_index()
    )
    x = np.arange(len(pivot))
    w = 0.38
    if "Weekday" in pivot.columns:
        ax2.bar(x - w / 2, pivot["Weekday"], width=w, color=WEEKDAY, label="Weekday")
    if "Weekend" in pivot.columns:
        ax2.bar(x + w / 2, pivot["Weekend"], width=w, color=WEEKEND, label="Weekend")
    ax2.set_xticks(x)
    ax2.set_xticklabels(pivot.index, rotation=45, ha="right", fontsize=8, color=MUTED)
    ax2.set_title("Mean demand by month", color=INK)
    ax2.set_ylabel("Avg kW", color=MUTED)
    ax2.legend(facecolor=PANEL, edgecolor=GRID_C, labelcolor=INK)

    fig.suptitle("Lakeside load shape — weekday vs weekend", color=INK, fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = CHARTS / "demand_weekday_weekend_summary.png"
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)
    print(f"chart: {out}")
    return out


def _draw_demand_oat_scatter(ax, m: pd.DataFrame, *, peak_hours: pd.DataFrame | None = None) -> float:
    """Weekday/weekend OAT scatter; optionally star peak-day hourly points. Returns Pearson r."""
    style_ax(ax)
    for day_type, color, marker in (("Weekday", WEEKDAY, "o"), ("Weekend", WEEKEND, "^")):
        s = m[m["day_type"] == day_type]
        ax.scatter(
            s["oat_f"],
            s["kw_avg"],
            s=12,
            alpha=0.35,
            c=color,
            marker=marker,
            label=day_type,
            edgecolors="none",
        )
    if peak_hours is not None and not peak_hours.empty:
        ax.scatter(
            peak_hours["oat_f"],
            peak_hours["kw_avg"],
            s=55,
            c=ACCENT,
            marker="*",
            zorder=5,
            label="Peak day hours",
            edgecolors="white",
            linewidths=0.4,
        )
    ax.set_xlabel("Madison web OAT (°F)", color=MUTED)
    ax.set_ylabel("Hourly avg demand (kW)", color=MUTED)
    r = float(m["oat_f"].corr(m["kw_avg"]))
    ax.set_title(f"Demand vs Open-Meteo OAT  ·  Pearson r = {r:.2f}", color=INK)
    ax.legend(facecolor=PANEL, edgecolor=GRID_C, labelcolor=INK)
    return r


def chart_demand_vs_weather(demand: pd.DataFrame, wx: pd.DataFrame) -> tuple[Path, Path, Path]:
    """Hourly demand vs Madison OAT — scatter, density, and scatter+peak-day profile."""
    CHARTS.mkdir(parents=True, exist_ok=True)
    d = demand.copy()
    d["hour_utc"] = d["timestamp_utc"].dt.floor("h")
    hourly = (
        d.groupby(["hour_utc", "day_type"], as_index=False)
        .agg(kw_avg=("kw_demand", "mean"))
    )
    w = wx.copy()
    w["timestamp_utc"] = pd.to_datetime(w["timestamp_utc"], utc=True)
    w["hour_utc"] = w["timestamp_utc"].dt.floor("h")
    w = w.groupby("hour_utc", as_index=False).agg(oat_f=("web-outside-air-temp", "mean"))

    m = hourly.merge(w, on="hour_utc", how="inner").dropna()
    m.to_csv(REPORTS / "demand_vs_web_weather_hourly.csv", index=False)

    # Peak demand day = local calendar day containing the max 5-min kW
    peak_idx = d["kw_demand"].idxmax()
    peak_ts = d.loc[peak_idx, "ts_local"]
    peak_date = peak_ts.date()
    peak_kw = float(d.loc[peak_idx, "kw_demand"])
    day = d[d["ts_local"].dt.date == peak_date].sort_values("ts_local")
    day_hours = day["ts_local"].dt.hour + day["ts_local"].dt.minute / 60.0
    peak_hour_utc = d.loc[peak_idx, "hour_utc"]
    peak_hours = m[m["hour_utc"].isin(day["hour_utc"].unique())]

    # Scatter only (no regression lines)
    fig, ax = plt.subplots(figsize=(8.0, 5.4))
    fig.patch.set_facecolor(BG)
    r = _draw_demand_oat_scatter(ax, m)
    fig.tight_layout()
    out_scatter = CHARTS / "demand_vs_web_weather_scatter.png"
    fig.savefig(out_scatter, dpi=140, facecolor=BG)
    plt.close(fig)
    print(f"chart: {out_scatter}  r={r:.3f}  n={len(m)}")

    # Density (hexbin) as its own figure
    fig2, ax2 = plt.subplots(figsize=(8.0, 5.4))
    fig2.patch.set_facecolor(BG)
    style_ax(ax2)
    hb = ax2.hexbin(m["oat_f"], m["kw_avg"], gridsize=28, cmap="YlOrRd", mincnt=1)
    cb = fig2.colorbar(hb, ax=ax2, pad=0.02)
    cb.set_label("Hours", color=MUTED)
    cb.ax.yaxis.set_tick_params(color=MUTED)
    plt.setp(plt.getp(cb.ax.axes, "yticklabels"), color=MUTED)
    ax2.set_xlabel("Madison web OAT (°F)", color=MUTED)
    ax2.set_ylabel("Hourly avg demand (kW)", color=MUTED)
    ax2.set_title(f"Density (all hours)  ·  Pearson r = {r:.2f}", color=INK)
    fig2.tight_layout()
    out_density = CHARTS / "demand_vs_web_weather_density.png"
    fig2.savefig(out_density, dpi=140, facecolor=BG)
    plt.close(fig2)
    print(f"chart: {out_density}")

    # Combined: scatter + peak-day 24h load profile
    fig3, axes = plt.subplots(1, 2, figsize=(13.5, 5.4), gridspec_kw={"width_ratios": [1.15, 1]})
    fig3.patch.set_facecolor(BG)
    _draw_demand_oat_scatter(axes[0], m, peak_hours=peak_hours)

    # Align Open-Meteo OAT onto the peak day's 5-min timestamps
    wx_day = wx.copy()
    wx_day["timestamp_utc"] = pd.to_datetime(wx_day["timestamp_utc"], utc=True)
    oat_src = (
        wx_day.set_index("timestamp_utc")["web-outside-air-temp"]
        .sort_index()
        .astype(float)
    )
    if oat_src.index.tz is None:
        oat_src.index = oat_src.index.tz_localize("UTC")
    day_idx = pd.DatetimeIndex(day["timestamp_utc"])
    oat_union = oat_src.reindex(oat_src.index.union(day_idx)).sort_index()
    oat_union = oat_union.interpolate(method="time", limit_direction="both")
    day_oat = oat_union.reindex(day_idx).to_numpy()

    axp = axes[1]
    style_ax(axp)
    ln_kw = axp.plot(day_hours, day["kw_demand"].values, color=ACCENT, lw=1.8, label="Demand")
    axp.fill_between(day_hours, day["kw_demand"].values, alpha=0.22, color=ACCENT)
    # Mark the instantaneous peak
    sc_peak = axp.scatter(
        [peak_ts.hour + peak_ts.minute / 60.0],
        [peak_kw],
        s=70,
        c="#ff6b6b",
        zorder=5,
        marker="o",
        edgecolors="white",
        linewidths=0.6,
        label=f"Peak {peak_kw:.0f} kW",
    )
    axp.set_xlim(0, 24)
    axp.set_xticks([0, 6, 12, 18, 24])
    axp.set_xlabel("Hour (local)", color=MUTED)
    axp.set_ylabel("Demand (kW)", color=MUTED)

    ax_oat = axp.twinx()
    ax_oat.set_facecolor("none")
    ln_oat = ax_oat.plot(
        day_hours,
        day_oat,
        color=WEEKEND,
        lw=2.0,
        ls="--",
        label="Madison OAT (Open-Meteo)",
    )
    ax_oat.set_ylabel("Outside air temp (°F)", color=WEEKEND)
    ax_oat.tick_params(axis="y", colors=WEEKEND)
    for spine in ax_oat.spines.values():
        spine.set_color(GRID_C)
    if np.isfinite(day_oat).any():
        oat_min = float(np.nanmin(day_oat))
        oat_max = float(np.nanmax(day_oat))
        pad = max(2.0, 0.12 * (oat_max - oat_min + 1e-6))
        ax_oat.set_ylim(oat_min - pad, oat_max + pad)

    dow = peak_ts.strftime("%a")
    oat_at_peak = float(oat_union.reindex([d.loc[peak_idx, "timestamp_utc"]]).iloc[0])
    axp.set_title(
        f"Peak demand day · {peak_date} ({dow})\n"
        f"max {peak_kw:.0f} kW @ {peak_ts.strftime('%H:%M')}  ·  OAT {oat_at_peak:.0f}°F",
        color=INK,
    )
    handles = ln_kw + [sc_peak] + ln_oat
    labels = [h.get_label() for h in handles]
    axp.legend(handles, labels, facecolor=PANEL, edgecolor=GRID_C, labelcolor=INK, loc="upper right")

    fig3.suptitle(
        "Lakeside demand vs Madison web weather + peak-day load profile",
        color=INK,
        fontsize=13,
    )
    fig3.tight_layout(rect=[0, 0, 1, 0.94])
    out_combo = CHARTS / "demand_vs_web_weather_scatter_peak_day.png"
    fig3.savefig(out_combo, dpi=140, facecolor=BG)
    plt.close(fig3)
    print(
        f"chart: {out_combo}  peak_day={peak_date} peak_kw={peak_kw:.1f} "
        f"peak_hour_utc={peak_hour_utc}"
    )

    return out_scatter, out_density, out_combo


def rebuild_zip() -> Path:
    PACKAGES.mkdir(parents=True, exist_ok=True)
    out = PACKAGES / f"{BUILDING_ID}_hvac_openfdd_package_v1.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in CLEAN.rglob("*"):
            if f.is_file():
                arc = f"{BUILDING_ID}/{f.relative_to(CLEAN).as_posix()}"
                zf.write(f, arcname=arc)
    print(f"rebuilt package: {out}")
    return out


def validate_has_weather(zip_path: Path) -> None:
    v19 = Path(r"C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_19")
    if not v19.is_dir():
        return
    sys.path.insert(0, str(v19))
    from app.package_io import load_package_zip

    result = load_package_zip(zip_path.read_bytes())
    has_wx = result.weather is not None and not result.weather.empty
    cols = list(result.weather.columns)[:8] if has_wx else []
    print(f"vibe19 validate: equip={len(result.frames)} has_weather={has_wx} wx_cols={cols}")


def load_weather_frame(demand: pd.DataFrame, *, allow_fetch: bool = True) -> pd.DataFrame:
    """Load Madison weather for demand charts: prefer site CSV, else optional Open-Meteo fetch."""
    wx_path = CLEAN / "weather" / "history_wide.csv"
    if wx_path.is_file():
        wx = pd.read_csv(wx_path)
        wx["timestamp_utc"] = pd.to_datetime(wx["timestamp_utc"], utc=True)
        if "web-outside-air-temp" not in wx.columns:
            raise ValueError(f"{wx_path} missing web-outside-air-temp")
        print(f"weather from {wx_path} rows={len(wx)}")
        return wx.sort_values("timestamp_utc")
    if not allow_fetch:
        raise FileNotFoundError(f"missing {wx_path} and fetch disabled")
    start = demand["timestamp_utc"].min().strftime("%Y-%m-%d")
    end = demand["timestamp_utc"].max().strftime("%Y-%m-%d")
    return fetch_open_meteo(start, end)


def regenerate_analytics_charts(*, allow_weather_fetch: bool = True) -> list[Path]:
    """Rebuild the demand + GL14 analytics PNGs used by the load-profile notebook."""
    outs: list[Path] = []
    if not METER.is_file():
        print(f"skip demand charts — missing {METER}")
    else:
        demand = load_demand()
        CHARTS.mkdir(parents=True, exist_ok=True)
        REPORTS.mkdir(parents=True, exist_ok=True)
        outs.append(chart_monthly_load_profiles(demand))
        outs.append(chart_overall_weekday_weekend(demand))
        try:
            wx = load_weather_frame(demand, allow_fetch=allow_weather_fetch)
            outs.extend(chart_demand_vs_weather(demand, wx))
        except Exception as e:
            print(f"skip demand-vs-weather charts: {e}")

    # GL14 calibration progress (copies into plots/analytics)
    try:
        scripts_dir = str(_APP / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from eplus_calibration_plots import (  # type: ignore
            LOG,
            ANALYTICS as GL14_ANALYTICS,
            PLOTS as GL14_PLOTS,
            plot_gl14_progress,
            plot_gl14_status_strip,
            plot_error_heatmap,
        )

        if LOG.is_file():
            GL14_PLOTS.mkdir(parents=True, exist_ok=True)
            GL14_ANALYTICS.mkdir(parents=True, exist_ok=True)
            log = pd.read_csv(LOG)
            for fn in (plot_gl14_progress, plot_gl14_status_strip, plot_error_heatmap):
                p = fn(log)
                if p and p.is_file():
                    dest = GL14_ANALYTICS / p.name
                    dest.write_bytes(p.read_bytes())
                    outs.append(dest)
                    print(f"chart: {dest}")
        else:
            print(f"skip GL14 charts — missing {LOG}")
    except Exception as e:
        print(f"skip GL14 charts: {e}")
    return outs


def main() -> int:
    if not METER.is_file():
        raise SystemExit(f"Missing demand CSV: {METER}")
    demand = load_demand()
    print(
        f"demand rows={len(demand)} "
        f"{demand['timestamp_utc'].min()} .. {demand['timestamp_utc'].max()}"
    )

    chart_monthly_load_profiles(demand)
    chart_overall_weekday_weekend(demand)

    start = demand["timestamp_utc"].min().strftime("%Y-%m-%d")
    end = demand["timestamp_utc"].max().strftime("%Y-%m-%d")
    wx = fetch_open_meteo(start, end)
    print(f"weather hourly rows={len(wx)}")

    write_weather_sidecar(wx, demand)
    chart_demand_vs_weather(demand, wx)

    # Stamp root column_map note
    cmap_path = CLEAN / "column_map.json"
    if cmap_path.is_file():
        doc = json.loads(cmap_path.read_text(encoding="utf-8"))
        doc["weather"] = {
            "source": "open_meteo",
            "place": "Madison, WI",
            "lat": MADISON_LAT,
            "lon": MADISON_LON,
            "file": "weather/history_wide.csv",
            "column_roles": {
                "web-outside-air-temp": "web-outside-air-temp",
                "web-outside-air-humidity": "web-outside-air-humidity",
                "web-outside-air-dewpoint": "web-outside-air-dewpoint",
            },
        }
        cmap_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    zpath = rebuild_zip()
    validate_has_weather(zpath)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
