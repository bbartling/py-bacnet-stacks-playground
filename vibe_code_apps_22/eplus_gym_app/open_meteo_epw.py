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


def _epw_date_token(ts: pd.Timestamp | date) -> str:
    """EnergyPlus DATA PERIODS date: mm/dd/yyyy (required for multi-year AMY).

    EnergyPlus docs / GetNextEnvironment expect mm/dd/yyyy (not yyyy/mm/dd).
    With Treat Weather as Actual=Yes, year tokens enable absolute-date coverage.
    """
    if hasattr(ts, "year"):
        return f"{int(ts.month)}/{int(ts.day)}/{int(ts.year)}"
    raise TypeError(f"expected date-like, got {type(ts)!r}")


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
    # Month/day-only tokens (e.g. 8/1,8/7) make EnergyPlus treat coverage as a
    # single short noyear window and reject winter RunPeriods like 2026-01-26.
    start_s = _epw_date_token(start)
    end_s = _epw_date_token(end)
    dow = start.day_name()
    return [
        loc,
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,AMY from Open-Meteo archive (UTC to local standard, no DST)",
        "COMMENTS 2,M&V actual-year weather - not TMY. Do not treat as typical.",
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


def _parse_epw_period_date(token: str, *, fallback_year: int | None = None) -> date | None:
    """Parse DATA PERIODS start/end token (mm/dd/yyyy, yyyy/mm/dd, or mm/dd)."""
    parts = [p.strip() for p in str(token).split("/") if p.strip()]
    try:
        if len(parts) == 3:
            a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
            # mm/dd/yyyy (EnergyPlus preferred) vs yyyy/mm/dd
            if a > 31:  # year first
                return date(a, b, c)
            if c > 31:  # year last
                return date(c, a, b)
            # Ambiguous small numbers: prefer mm/dd/yyyy when third looks like year>=1900
            if c >= 1900:
                return date(c, a, b)
            if a >= 1900:
                return date(a, b, c)
            return date(c, a, b)
        if len(parts) == 2 and fallback_year is not None:
            return date(int(fallback_year), int(parts[0]), int(parts[1]))
    except ValueError:
        return None
    return None


def parse_epw_data_periods(path: Path) -> dict[str, Any]:
    """Read EnergyPlus DATA PERIODS header coverage (what E+ uses at startup)."""
    header_start: date | None = None
    header_end: date | None = None
    raw: str | None = None
    year_aware = False
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.upper().startswith("DATA PERIODS"):
            continue
        raw = line.strip()
        parts = [p.strip() for p in line.split(",")]
        # DATA PERIODS, n, records/h, name, dow, start, end
        if len(parts) >= 7:
            start_tok, end_tok = parts[5], parts[6]
            year_aware = start_tok.count("/") >= 2 and end_tok.count("/") >= 2
            header_start = _parse_epw_period_date(start_tok)
            header_end = _parse_epw_period_date(end_tok)
        break
    return {
        "raw": raw,
        "start": header_start,
        "end": header_end,
        "year_aware": year_aware,
    }


def repair_epw_data_periods(path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Rewrite DATA PERIODS to mm/dd/yyyy from data-row span (in-place).

    Fixes legacy Open-Meteo AMY files that advertised ``8/1,8/7`` (noyear) while
    data rows spanned a full multi-year window.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    span = parse_epw_span(path)
    start = span.get("start")
    end = span.get("end")
    if start is None or end is None:
        raise ValueError(f"cannot repair DATA PERIODS; no data rows in {path}")
    start_s = _epw_date_token(start)
    end_s = _epw_date_token(end)
    dow = start.strftime("%A")
    new_line = f"DATA PERIODS,1,1,Data,{dow},{start_s},{end_s}"
    out: list[str] = []
    replaced = False
    for line in lines:
        if line.upper().startswith("DATA PERIODS"):
            out.append(new_line)
            replaced = True
        else:
            out.append(line)
    if not replaced:
        # Insert before first data row (digit-leading)
        inserted = False
        rebuilt: list[str] = []
        for line in out:
            if not inserted and line and line[0].isdigit():
                rebuilt.append(new_line)
                inserted = True
            rebuilt.append(line)
        out = rebuilt
        replaced = inserted
    if not replaced:
        raise ValueError(f"could not locate DATA PERIODS in {path}")
    before = parse_epw_data_periods(path)
    meta = {
        "epw": str(path),
        "before": before.get("raw"),
        "after": new_line,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "changed": before.get("raw") != new_line,
    }
    if dry_run or not meta["changed"]:
        return meta
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return meta


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


def _dated_amy_name(slug: str, start: date, end: date) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug).strip("_-") or "site"
    return f"{safe}_amy_{start:%Y%m}_{end:%Y%m}.epw"


def _prune_old_amy(weather: Path, keep: Path, *, slug: str) -> list[str]:
    keep_key = keep.resolve()
    leftover: list[str] = []
    patterns = [f"{slug}_amy*.epw", "madison_amy*.epw"]
    seen: set[str] = set()
    for pat in patterns:
        for p in weather.glob(pat):
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
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
    """Fetch Open-Meteo at site lat/lon and write ``eplus/weather/{slug}_amy_*.epw``.

    Never writes Chicago / screening TMY. Inject ``fetch`` in tests.
    """
    site = Path(site)
    try:
        from lakeside.paths import site_slug

        slug = site_slug(site)
    except Exception:  # noqa: BLE001
        slug = site.name.lower()
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

    stub = weather / f"{slug}_amy_open_meteo.epw"
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
    final = weather / _dated_amy_name(slug, span["start"], span["end"])
    if final.resolve() != stub.resolve():
        if final.exists():
            final.unlink()
        stub.replace(final)
    leftover = _prune_old_amy(weather, final, slug=slug)
    if leftover:
        meta["prune_locked"] = leftover
    meta["epw"] = str(final)
    meta["skipped"] = False
    meta["fetched_utc"] = datetime.now(timezone.utc).isoformat()
    meta["request_start"] = win_start
    meta["request_end"] = win_end
    meta["site_slug"] = slug
    publish_current_amy(site, final, meta)
    return meta


def publish_current_amy(site: Path, epw_path: Path, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Atomically update amy_meta.json and rewrite site_ui_bundle_v1 epw pin."""
    import hashlib
    import os

    site = Path(site)
    epw_path = Path(epw_path)
    try:
        repair_epw_data_periods(epw_path)
    except (OSError, ValueError):
        pass
    weather = site / "eplus" / "weather"
    weather.mkdir(parents=True, exist_ok=True)
    span = parse_epw_span(epw_path)
    doc = dict(meta or {})
    doc["epw"] = str(epw_path)
    doc["kind"] = KIND_AMY
    doc["source"] = doc.get("source") or "open-meteo-archive"
    if span.get("start") is not None:
        doc["start"] = span["start"].isoformat() if hasattr(span["start"], "isoformat") else str(span["start"])
    if span.get("end") is not None:
        doc["end"] = span["end"].isoformat() if hasattr(span["end"], "isoformat") else str(span["end"])
    doc["n_rows"] = span.get("n_rows")
    h = hashlib.sha256()
    with epw_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    doc["sha256"] = h.hexdigest()

    meta_path = weather / "amy_meta.json"
    tmp_meta = weather / f".amy_meta.{os.getpid()}.tmp"
    tmp_meta.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_meta, meta_path)

    bundle = site / "reports" / "site_ui_bundle_v1.json"
    if bundle.is_file():
        try:
            bundle_doc = json.loads(bundle.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            bundle_doc = None
        if isinstance(bundle_doc, dict):
            rel = f"eplus/weather/{epw_path.name}"
            try:
                rel = str(epw_path.resolve().relative_to(site.resolve())).replace("\\", "/")
            except ValueError:
                pass
            bundle_doc["epw"] = rel
            bundle_doc["epw_sha256"] = doc["sha256"]
            bundle_doc["epw_coverage_start"] = doc.get("start")
            bundle_doc["epw_coverage_end"] = doc.get("end")
            tmp_b = bundle.with_name(f".{bundle.name}.{os.getpid()}.tmp")
            tmp_b.write_text(json.dumps(bundle_doc, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp_b, bundle)
            doc["bundle_epw"] = rel
    return doc
