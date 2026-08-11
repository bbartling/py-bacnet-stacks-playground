"""Fetch Open-Meteo archive weather and write an EnergyPlus AMY EPW.

This is the agent tool for site weather. Do **not** invent an EPW from BAS
OAT-only (missing solar / RH / wind / pressure). Do **not** copy Chicago TMY
and call it Madison typical.

AMY = actual meteorological year at the site lat/lon (M&V).
TMY = separate Madison MSN TMY3/TMYx download — not produced here.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests

from eplus_gym_app.weather_files import KIND_AMY, resolve_amy_epw

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY = (
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "surface_pressure",
    "shortwave_radiation",
    "direct_normal_irradiance",
    "diffuse_radiation",
    "wind_speed_10m",
    "wind_direction_10m",
)

MISS_TEMP = 99.9
MISS_RH = 999
MISS_PRESS = 999999
MISS_RAD = 9999
MISS_ILLUM = 999999
MISS_WIND_DIR = 999
MISS_WIND_SPD = 999
MISS_SKY = 99
MISS_VIS = 9999
MISS_CEIL = 99999
MISS_PRECIP = 999
MISS_AOD = 999
MISS_SNOW = 999
MISS_ALBEDO = 999
MISS_LIQ = 99

FetchFn = Callable[..., pd.DataFrame]


def _f_to_c(t: Any) -> float:
    if t is None or (isinstance(t, float) and math.isnan(t)):
        return MISS_TEMP
    return (float(t) - 32.0) * 5.0 / 9.0


def _mph_to_ms(mph: Any) -> float:
    if mph is None or (isinstance(mph, float) and math.isnan(mph)):
        return MISS_WIND_SPD
    return float(mph) * 0.44704


def default_archive_end(*, as_of: date | None = None, lag_days: int = 3) -> date:
    """Open-Meteo archive lags a few days behind wall-clock."""
    return (as_of or date.today()) - timedelta(days=int(lag_days))


def default_calendar_window(
    *,
    answers_start: str | None,
    answers_end: str | None,
    as_of: date | None = None,
    lag_days: int = 3,
) -> tuple[str, str]:
    start = (answers_start or "2025-08-01")[:10]
    cap = default_archive_end(as_of=as_of, lag_days=lag_days)
    try:
        end_ans = date.fromisoformat((answers_end or "")[:10])
    except ValueError:
        end_ans = cap
    end = max(end_ans, cap)
    return start, end.isoformat()


def site_geo(site: Path) -> dict[str, Any]:
    answers = Path(site) / "eplus" / "assumptions" / "answers.json"
    if not answers.is_file():
        raise FileNotFoundError(f"missing {answers} (need lat/lon for Open-Meteo)")
    ans = json.loads(answers.read_text(encoding="utf-8"))
    win = ans.get("data_window") or {}
    return {
        "lat": float(ans["lat"]),
        "lon": float(ans["lon"]),
        "city": str(ans.get("city") or "Madison, WI"),
        "elevation_m": float(ans.get("elevation_m") or 261.0),
        "tz_name": str(ans.get("tz_name") or "America/Chicago"),
        "utc_offset_hours": float(ans.get("utc_offset_hours") or -6.0),
        "start": str(win.get("start_utc") or "2025-08-01")[:10],
        "end": str(win.get("end_utc") or "")[:10],
        "wmo": str(ans.get("wmo") or "726410"),
        "location_name": str(ans.get("epw_location_name") or "Madison_AMY"),
        "answers": answers,
    }


def fetch_open_meteo_archive(
    lat: float,
    lon: float,
    start: str,
    end: str,
    *,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(HOURLY),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "UTC",
    }
    get = session.get if session is not None else requests.get
    r = get(ARCHIVE_URL, params=params, timeout=180)
    r.raise_for_status()
    payload = r.json()
    block = payload.get("hourly") or {}
    if not block.get("time"):
        raise RuntimeError(f"Open-Meteo empty: {payload.get('reason') or 'no hourly.time'}")
    df = pd.DataFrame(
        {
            "timestamp_utc": pd.to_datetime(block["time"], utc=True),
            "dry_bulb_f": block["temperature_2m"],
            "dew_point_f": block["dew_point_2m"],
            "relative_humidity_pct": block["relative_humidity_2m"],
            "surface_pressure_hpa": block["surface_pressure"],
            "shortwave_radiation_wm2": block["shortwave_radiation"],
            "direct_normal_irradiance_wm2": block["direct_normal_irradiance"],
            "diffuse_radiation_wm2": block["diffuse_radiation"],
            "wind_speed_mph": block["wind_speed_10m"],
            "wind_direction_deg": block["wind_direction_10m"],
        }
    )
    elev = payload.get("elevation")
    df.attrs["elevation_m"] = float(elev) if elev is not None else None
    df.attrs["source"] = "open-meteo-archive"
    df.attrs["url"] = ARCHIVE_URL
    return df.sort_values("timestamp_utc").drop_duplicates("timestamp_utc")


def to_local_standard(df: pd.DataFrame, utc_offset_hours: float = -6.0) -> pd.DataFrame:
    """Stamp rows in local standard time (no DST) for EnergyPlus EPW."""
    out = df.copy()
    out["ts_utc"] = pd.to_datetime(out["timestamp_utc"], utc=True)
    out["ts_lst"] = out["ts_utc"] + pd.Timedelta(hours=float(utc_offset_hours))
    return out.set_index("ts_lst").sort_index()


def _epw_header(
    *,
    lat: float,
    lon: float,
    elevation_m: float,
    start: pd.Timestamp,
    end: pd.Timestamp,
    location_name: str,
    wmo: str,
    utc_offset_hours: float,
) -> list[str]:
    loc = (
        f"LOCATION,{location_name},WI,USA,AMY,{wmo},"
        f"{lat:.3f},{lon:.3f},{utc_offset_hours:.1f},{elevation_m:.1f}"
    )
    start_s = f"{start.month}/{start.day}"
    end_s = f"{end.month}/{end.day}"
    dow = start.day_name()
    return [
        loc,
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,AMY from Open-Meteo archive (UTC to local standard, no DST)",
        "COMMENTS 2,M&V actual-year weather — not TMY. Do not treat as typical.",
        f"DATA PERIODS,1,1,Data,{dow},{start_s},{end_s}",
    ]


def _data_row(ts: pd.Timestamp, row: pd.Series) -> str:
    year, month, day = int(ts.year), int(ts.month), int(ts.day)
    hour = int(ts.hour) + 1
    if hour > 24:
        hour = 24
    source = "?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9"
    db = round(_f_to_c(row.get("dry_bulb_f")), 1)
    dp = round(_f_to_c(row.get("dew_point_f")), 1)
    rh = row.get("relative_humidity_pct")
    rh_v = int(round(float(rh))) if pd.notna(rh) else MISS_RH
    rh_v = max(0, min(110, rh_v)) if rh_v != MISS_RH else MISS_RH
    press = (
        int(round(float(row["surface_pressure_hpa"]) * 100))
        if pd.notna(row.get("surface_pressure_hpa"))
        else MISS_PRESS
    )
    ghi = (
        int(round(float(row["shortwave_radiation_wm2"] or 0)))
        if pd.notna(row.get("shortwave_radiation_wm2"))
        else 0
    )
    dni = (
        int(round(float(row["direct_normal_irradiance_wm2"] or 0)))
        if pd.notna(row.get("direct_normal_irradiance_wm2"))
        else 0
    )
    dhi = (
        int(round(float(row["diffuse_radiation_wm2"] or 0)))
        if pd.notna(row.get("diffuse_radiation_wm2"))
        else 0
    )
    wd = (
        int(round(float(row["wind_direction_deg"]))) % 360
        if pd.notna(row.get("wind_direction_deg"))
        else MISS_WIND_DIR
    )
    ws = round(_mph_to_ms(row.get("wind_speed_mph")), 1)
    fields = [
        year, month, day, hour, 0, source, db, dp, rh_v, press,
        0, 0, MISS_RAD, ghi, dni, dhi,
        MISS_ILLUM, MISS_ILLUM, MISS_ILLUM, MISS_ILLUM,
        wd, ws, MISS_SKY, MISS_VIS, MISS_CEIL,
        MISS_PRECIP, MISS_AOD, MISS_SNOW, 0, MISS_ALBEDO, MISS_LIQ,
        0, 0, 0, 0,
    ]
    return ",".join(str(x) for x in fields)


def write_epw(
    df_lst: pd.DataFrame,
    out: Path,
    *,
    lat: float,
    lon: float,
    elevation_m: float,
    location_name: str = "Madison_AMY",
    wmo: str = "726410",
    utc_offset_hours: float = -6.0,
) -> dict[str, Any]:
    hourly = df_lst.resample("h").mean(numeric_only=True).dropna(subset=["dry_bulb_f"])
    hourly = hourly.copy()
    hourly["date"] = hourly.index.date
    day_counts = hourly.groupby("date").size()
    full_days = set(day_counts[day_counts >= 24].index)
    hourly = hourly[hourly["date"].isin(full_days)].drop(columns=["date"])
    if hourly.empty:
        raise RuntimeError("No complete AMY days after resample")
    start, end = hourly.index.min(), hourly.index.max()
    lines = _epw_header(
        lat=lat,
        lon=lon,
        elevation_m=elevation_m,
        start=start,
        end=end,
        location_name=location_name,
        wmo=wmo,
        utc_offset_hours=utc_offset_hours,
    ) + [_data_row(ts, hourly.loc[ts]) for ts in hourly.index]
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "epw": str(out),
        "rows": int(len(hourly)),
        "start_lst": str(start),
        "end_lst": str(end),
        "lat": float(lat),
        "lon": float(lon),
        "elevation_m": float(elevation_m),
        "kind": KIND_AMY,
        "source": "open-meteo-archive",
    }


def parse_epw_span(path: Path) -> dict[str, Any]:
    start: date | None = None
    end: date | None = None
    n = 0
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line[0].isalpha():
            continue
        parts = line.split(",")
        if len(parts) < 4:
            continue
        try:
            d = date(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            continue
        n += 1
        if start is None:
            start = d
        end = d
    return {"start": start, "end": end, "n_rows": n}


def amy_stale(
    epw: Path | None,
    *,
    as_of: date | None = None,
    lag_days: int = 5,
) -> bool:
    if epw is None or not Path(epw).is_file():
        return True
    span = parse_epw_span(Path(epw))
    end = span.get("end")
    if end is None:
        return True
    need = default_archive_end(as_of=as_of, lag_days=lag_days)
    return end < need


def _dated_amy_name(start: date, end: date) -> str:
    return f"madison_amy_{start:%Y%m}_{end:%Y%m}.epw"


def _prune_old_amy(weather: Path, keep: Path) -> list[str]:
    keep_key = keep.resolve()
    leftover: list[str] = []
    for p in weather.glob("madison_amy*.epw"):
        if p.resolve() == keep_key:
            continue
        try:
            p.unlink(missing_ok=True)
        except OSError:
            leftover.append(p.name)
    return leftover


def refresh_amy_epw(
    site: Path,
    *,
    start: str | None = None,
    end: str | None = None,
    force: bool = False,
    as_of: date | None = None,
    lag_days: int = 5,
    fetch: FetchFn | None = None,
) -> dict[str, Any]:
    """Fetch Open-Meteo at site lat/lon and write ``eplus/weather/madison_amy_*.epw``.

    Never writes Chicago / screening TMY. Inject ``fetch`` in tests.
    """
    site = Path(site)
    geo = site_geo(site)
    existing = resolve_amy_epw(site)
    if not force and not amy_stale(existing, as_of=as_of, lag_days=lag_days):
        span = parse_epw_span(existing) if existing else {}
        return {
            "epw": str(existing),
            "skipped": True,
            "reason": "AMY already covers Open-Meteo archive lag window",
            "kind": KIND_AMY,
            "source": "open-meteo-archive",
            "start": str(span.get("start")),
            "end": str(span.get("end")),
        }

    win_start, win_end = default_calendar_window(
        answers_start=start or geo["start"],
        answers_end=end or geo["end"],
        as_of=as_of,
        lag_days=3,
    )
    if start:
        win_start = start[:10]
    if end:
        win_end = end[:10]

    fetch_fn = fetch or fetch_open_meteo_archive
    raw = fetch_fn(geo["lat"], geo["lon"], win_start, win_end)
    elev = raw.attrs.get("elevation_m")
    elevation_m = float(elev) if elev is not None else float(geo["elevation_m"])
    lst = to_local_standard(raw, utc_offset_hours=float(geo["utc_offset_hours"]))

    weather = site / "eplus" / "weather"
    weather.mkdir(parents=True, exist_ok=True)
    raw.to_csv(weather / "open_meteo_amy_hourly.csv", index=False)

    stub = weather / "madison_amy_open_meteo.epw"
    meta = write_epw(
        lst,
        stub,
        lat=float(geo["lat"]),
        lon=float(geo["lon"]),
        elevation_m=elevation_m,
        location_name=str(geo["location_name"]),
        wmo=str(geo["wmo"]),
        utc_offset_hours=float(geo["utc_offset_hours"]),
    )
    span = parse_epw_span(stub)
    if span["start"] is None or span["end"] is None:
        raise RuntimeError("wrote EPW but could not parse data span")
    final = weather / _dated_amy_name(span["start"], span["end"])
    if final.resolve() != stub.resolve():
        if final.exists():
            final.unlink()
        stub.replace(final)
    leftover = _prune_old_amy(weather, final)
    if leftover:
        meta["prune_locked"] = leftover
    meta["epw"] = str(final)
    meta["skipped"] = False
    meta["fetched_utc"] = datetime.now(timezone.utc).isoformat()
    meta["request_start"] = win_start
    meta["request_end"] = win_end
    (weather / "amy_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
