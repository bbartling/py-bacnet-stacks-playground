"""Build Actual Meteorological Year (AMY) EPW files from Open-Meteo / vibe19 weather CSVs.

EnergyPlus EPW data-period rows (35 weather fields after Minute). We fill dry-bulb,
dew-point, RH, pressure, GHI/DNI/DHI, wind; remaining fields use EnergyPlus
missing-value codes so the file still parses.
"""

from __future__ import annotations

import argparse
import math
from calendar import isleap
from pathlib import Path
from typing import Any

import pandas as pd

from wattlab.weather.validate import (
    assert_consecutive_hourly_index,
    assert_epw_frame_physical_bounds,
)

# EPW missing-value conventions (common EnergyPlus defaults)
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


def f_to_c(temp_f: float) -> float:
    if temp_f is None or (isinstance(temp_f, float) and math.isnan(temp_f)):
        return MISS_TEMP
    return (float(temp_f) - 32.0) * 5.0 / 9.0


def mph_to_ms(mph: float) -> float:
    if mph is None or (isinstance(mph, float) and math.isnan(mph)):
        return MISS_WIND_SPD
    return float(mph) * 0.44704


def hpa_to_pa(hpa: float) -> float:
    if hpa is None or (isinstance(hpa, float) and math.isnan(hpa)):
        return MISS_PRESS
    return float(hpa) * 100.0


def _col(df: pd.DataFrame, *names: str) -> pd.Series | None:
    for n in names:
        if n in df.columns and pd.to_numeric(df[n], errors="coerce").notna().any():
            return pd.to_numeric(df[n], errors="coerce")
    return None


def load_weather_frame(path_or_df: Path | str | pd.DataFrame) -> pd.DataFrame:
    if isinstance(path_or_df, pd.DataFrame):
        df = path_or_df.copy()
    else:
        df = pd.read_csv(path_or_df)
    if not isinstance(df.index, pd.DatetimeIndex):
        if "timestamp_utc" in df.columns:
            df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
            df = df.set_index("timestamp_utc")
        else:
            first = df.columns[0]
            df[first] = pd.to_datetime(df[first], utc=True)
            df = df.set_index(first)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    return df.sort_index()


def resample_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """Mean-resample numeric columns to hourly (EnergyPlus EPW resolution)."""
    num = df.apply(pd.to_numeric, errors="coerce")
    return num.resample("1h").mean().dropna(how="all")


def utc_frame_to_local_standard(
    df: pd.DataFrame, tz_hours: int | float
) -> pd.DataFrame:
    """Shift one full calendar year of hourly UTC rows to local standard time.

    EnergyPlus interprets EPW data rows in the LOCATION header's local
    standard time; feeding UTC-stamped rows with a nonzero header timezone
    misaligns solar radiation by ``|tz_hours|`` hours (found live: 884 severe
    'Temperature out of bounds' errors on the Detroit 2025 AMY run). The
    first ``|tz_hours|`` UTC hours of Jan 1 wrap around to the end of the
    local year so the result is still exactly one calendar year.
    """
    if float(tz_hours) != int(tz_hours):
        raise ValueError(f"tz_hours must be a whole hour offset (got {tz_hours})")
    frame = load_weather_frame(df)
    idx = frame.index
    assert_consecutive_hourly_index(idx, context="UTC weather timestamps")
    year = int(idx[0].year)
    expected_rows = 8784 if isleap(year) else 8760
    expected_start = pd.Timestamp(year=year, month=1, day=1, tz=idx.tz)
    if idx[0] != expected_start or len(idx) != expected_rows:
        raise ValueError(
            "utc_frame_to_local_standard requires one full calendar year of "
            f"hourly UTC rows starting Jan 1 00:00 (got {len(idx)} rows "
            f"starting {idx[0]})"
        )
    offset = int(-int(tz_hours)) % expected_rows
    shifted = pd.concat([frame.iloc[offset:], frame.iloc[:offset]])
    shifted.index = pd.date_range(
        start=pd.Timestamp(year=year, month=1, day=1),
        periods=expected_rows,
        freq="1h",
    )
    shifted.index.name = "timestamp_local_standard"
    return shifted


def _epw_header(
    *,
    location_name: str,
    lat: float,
    lon: float,
    elevation_m: float,
    wmo: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    tz_hours: float | None = None,
) -> list[str]:
    # Explicit local-standard timezone when given; else rough from longitude
    tz = tz_hours if tz_hours is not None else round(lon / 15.0)
    loc = (
        f"LOCATION,{location_name},XX,USA,AMY,{wmo},"
        f"{lat:.3f},{lon:.3f},{tz:.1f},{elevation_m:.1f}"
    )
    design = "DESIGN CONDITIONS,0"
    typical = "TYPICAL/EXTREME PERIODS,0"
    ground = "GROUND TEMPERATURES,0"
    holiday = "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0"
    c1 = "COMMENTS 1,OpenFDD WattLab AMY EPW generated from Open-Meteo / vibe19 weather_observed.csv"
    c2 = "COMMENTS 2,Partial-year OK for overlap-window calibration; missing fields use EPW codes"
    # EnergyPlus hour convention: hour 1 = 00:00–01:00
    start_s = f"{start.month}/{start.day}"
    end_s = f"{end.month}/{end.day}"
    dow = start.day_name()
    periods = f"DATA PERIODS,1,1,Data,{dow},{start_s},{end_s}"
    return [loc, design, typical, ground, holiday, c1, c2, periods]


def _data_row(ts: pd.Timestamp, row: pd.Series) -> str:
    """One EPW data line. Hour is 1–24."""
    year = int(ts.year)
    month = int(ts.month)
    day = int(ts.day)
    hour = int(ts.hour) + 1  # EPW: 1 = first hour of day
    if hour > 24:
        hour = 24
    minute = 0
    source = "?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9"

    db_f = row.get("web-outside-air-temp", row.get("dry_bulb_f", float("nan")))
    dp_f = row.get("web-outside-air-dewpoint", row.get("dew_point_f", float("nan")))
    rh = row.get("web-outside-air-humidity", row.get("relative_humidity_pct", float("nan")))
    wind_mph = row.get("wind_speed_mph", float("nan"))
    wind_dir = row.get("wind_direction_deg", float("nan"))
    press_hpa = row.get("surface_pressure_hpa", float("nan"))
    ghi = row.get("shortwave_radiation_wm2", float("nan"))
    dni = row.get("direct_normal_irradiance_wm2", float("nan"))
    dhi = row.get("diffuse_radiation_wm2", float("nan"))

    db_c = round(f_to_c(db_f), 1) if pd.notna(db_f) else MISS_TEMP
    dp_c = round(f_to_c(dp_f), 1) if pd.notna(dp_f) else MISS_TEMP
    rh_v = int(round(float(rh))) if pd.notna(rh) else MISS_RH
    rh_v = max(0, min(110, rh_v)) if rh_v != MISS_RH else MISS_RH
    press = int(round(hpa_to_pa(press_hpa))) if pd.notna(press_hpa) else MISS_PRESS
    ghi_v = int(round(float(ghi))) if pd.notna(ghi) else 0
    dni_v = int(round(float(dni))) if pd.notna(dni) else 0
    dhi_v = int(round(float(dhi))) if pd.notna(dhi) else 0
    # Extraterrestrial / IR often missing
    eth = 0
    etdn = 0
    hir = MISS_RAD
    wd = int(round(float(wind_dir))) % 360 if pd.notna(wind_dir) else MISS_WIND_DIR
    ws = round(mph_to_ms(wind_mph), 1) if pd.notna(wind_mph) else MISS_WIND_SPD

    fields = [
        year,
        month,
        day,
        hour,
        minute,
        source,
        db_c,
        dp_c,
        rh_v,
        press,
        eth,  # extraterrestrial horizontal
        etdn,  # extraterrestrial direct normal
        hir,  # horizontal infrared
        ghi_v,
        dni_v,
        dhi_v,
        MISS_ILLUM,  # GHI illuminance
        MISS_ILLUM,  # DNI illuminance
        MISS_ILLUM,  # DHI illuminance
        MISS_ILLUM,  # zenith luminance
        wd,
        ws,
        MISS_SKY,  # total sky cover
        MISS_SKY,  # opaque sky cover
        MISS_VIS,  # visibility
        MISS_CEIL,  # ceiling height
        9,  # present weather observation (missing)
        999999999,  # present weather codes
        MISS_PRECIP,  # precipitable water
        MISS_AOD,  # aerosol optical depth
        MISS_SNOW,  # snow depth
        MISS_SNOW,  # days since snow
        MISS_ALBEDO,  # albedo
        MISS_LIQ,  # liquid precip depth
        MISS_LIQ,  # liquid precip quantity
    ]
    return ",".join(str(x) for x in fields)


def _validate_annual_coverage(index: pd.DatetimeIndex) -> None:
    """Require one complete calendar year of consecutive hourly rows."""
    start = index[0]
    year = int(start.year)
    expected_rows = 8784 if isleap(year) else 8760
    expected = pd.date_range(
        start=pd.Timestamp(year=year, month=1, day=1, tz=index.tz),
        periods=expected_rows,
        freq="1h",
    )
    if start != expected[0]:
        raise ValueError(
            "coverage_mode='annual' requires a full calendar year starting "
            f"Jan 1 00:00 (data starts {start})"
        )
    if len(index) != expected_rows or not index.equals(expected):
        raise ValueError(
            f"coverage_mode='annual' requires exactly {expected_rows} "
            f"consecutive hourly rows covering {year} with no gaps or "
            f"duplicates (got {len(index)} rows spanning "
            f"{start}..{index[-1]})"
        )


def build_amy_epw(
    weather: Path | str | pd.DataFrame,
    out_path: Path | str,
    *,
    lat: float = 41.98,
    lon: float = -87.92,
    elevation_m: float = 200.0,
    location_name: str = "OpenFDD_AMY",
    wmo: str = "999999",
    coverage_mode: str = "partial",
    tz_hours: float | None = None,
) -> dict[str, Any]:
    """Write an AMY EPW from vibe19/Open-Meteo weather. Returns metadata dict.

    coverage_mode='annual' rejects anything but one complete calendar year
    (8,760 or 8,784 consecutive hourly rows) *before* writing the file;
    coverage_mode='partial' (default) keeps the historical overlap-window
    behavior for calibration slices.

    ``tz_hours`` sets the LOCATION header timezone explicitly. Rows must be
    stamped in that local standard time (see ``utc_frame_to_local_standard``);
    EnergyPlus rejects headers more than ~2 h off the longitude meridian.
    """
    if coverage_mode not in ("annual", "partial"):
        raise ValueError(
            f"coverage_mode must be 'annual' or 'partial' (got {coverage_mode!r})"
        )
    df = load_weather_frame(weather)
    if coverage_mode == "annual":
        # Reject duplicates / sub-hourly / gappy indexes *before* mean-resample
        # can hide them, and reject nonfinite / out-of-bounds weather values.
        assert_consecutive_hourly_index(df.index, context="annual weather timestamps")
        assert_epw_frame_physical_bounds(df)
    hourly = resample_hourly(df)
    if hourly.empty:
        raise ValueError("No hourly weather rows after resample")
    if coverage_mode == "annual":
        _validate_annual_coverage(hourly.index)

    start = hourly.index.min()
    end = hourly.index.max()
    header = _epw_header(
        location_name=location_name,
        lat=lat,
        lon=lon,
        elevation_m=elevation_m,
        wmo=wmo,
        start=start,
        end=end,
        tz_hours=tz_hours,
    )
    lines = header + [_data_row(ts, hourly.loc[ts]) for ts in hourly.index]
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    metadata: dict[str, Any] = {
        "epw": str(out),
        "rows": len(hourly),
        "lat": lat,
        "lon": lon,
        "location_name": location_name,
        "time_basis": "local_standard" if tz_hours is not None else "utc",
        "tz_hours": float(tz_hours) if tz_hours is not None else 0.0,
    }
    if tz_hours is not None:
        metadata["start_local_standard"] = str(start.tz_localize(None))
        metadata["end_local_standard"] = str(end.tz_localize(None))
    else:
        # Backward-compatible keys for callers that have not converted an
        # archive UTC frame to EPW local standard time.
        metadata["start_utc"] = str(start)
        metadata["end_utc"] = str(end)
    return metadata


def epw_data_period(epw_path: Path | str) -> dict[str, Any] | None:
    """Return begin/end dates covered by an EPW (DATA PERIODS + data rows).

    Used to auto-align IDF ``RunPeriod`` when AMY weather is partial-year
    (default annual RunPeriod + short EPW → EnergyPlus fatal EOF).

    ``end`` is the last **complete** calendar day (max hour ≥ 23). A trailing
    partial day (e.g. last row 10:00) is clipped so EnergyPlus does not EOF mid-day.
    """
    from collections import defaultdict
    from datetime import date

    path = Path(epw_path)
    if not path.is_file():
        return None
    header_begin: date | None = None
    header_end: date | None = None
    first_row: date | None = None
    last_row: date | None = None
    last_row_hour: int | None = None
    hours_by_day: dict[date, set[int]] = defaultdict(set)
    day_order: list[date] = []

    def _md(token: str, year: int | None = None) -> date | None:
        parts = token.replace(" ", "").split("/")
        if len(parts) != 2:
            return None
        try:
            m, d = int(parts[0]), int(parts[1])
            y = year or 2000
            return date(y, m, d)
        except ValueError:
            return None

    with path.open(encoding="utf-8", errors="replace") as fh:
        for i, raw in enumerate(fh):
            line = raw.strip()
            if i < 8 and line.upper().startswith("DATA PERIODS"):
                fields = [f.strip() for f in line.split(",")]
                # DATA PERIODS,n,n,name,dow,start,end
                if len(fields) >= 7:
                    header_begin = _md(fields[5])
                    header_end = _md(fields[6])
                continue
            if i < 8:
                continue
            # Data row: year,month,day,hour,...
            parts = line.split(",")
            if len(parts) < 4:
                continue
            try:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                hour = int(float(parts[3]))
                row_d = date(y, m, d)
            except ValueError:
                continue
            if first_row is None:
                first_row = row_d
            last_row = row_d
            last_row_hour = hour
            if row_d not in hours_by_day:
                day_order.append(row_d)
            hours_by_day[row_d].add(hour)

    begin = first_row or header_begin
    if begin is None:
        return None

    def _day_complete(d: date) -> bool:
        hrs = hours_by_day.get(d) or set()
        # EPW hours are typically 1–24 (or 0–23). Treat max≥23 as a full day
        # (trailing partial days end ~10:00 and must not set RunPeriod end).
        return bool(hrs) and max(hrs) >= 23

    end_clipped = False
    end: date | None = None
    # Walk days in **file appearance order** (TMY years differ by month — do not
    # sort by absolute calendar date or Dec 31 1981 loses to Apr 2002).
    if day_order:
        for d in reversed(day_order):
            if _day_complete(d):
                end = d
                break
        if end is None:
            # No complete day — cannot safely align annual-style RunPeriod
            return {
                "begin": begin.isoformat(),
                "end": None,
                "begin_date": begin,
                "end_date": None,
                "full_calendar_year": False,
                "n_days": None,
                "source": str(path),
                "last_row_hour": last_row_hour,
                "end_clipped_from_partial_day": True,
                "partial_day_only": True,
                "ok": False,
                "reason": "partial_day_only",
            }
        if last_row is not None and end != last_row:
            end_clipped = True
        elif (
            last_row is not None
            and end == last_row
            and last_row_hour is not None
            and last_row_hour < 23
        ):
            # Incomplete last day — should have selected prior complete day above
            end_clipped = True
    else:
        end = last_row or header_end
        if end is None:
            return None

    # n_days: for mixed-year TMY use month/day span via header or row count of days
    if day_order and len(day_order) >= 360:
        n_days = len(day_order)
    else:
        n_days = (end - begin).days + 1 if end >= begin else len(day_order) or None

    full_year = begin.month == 1 and begin.day == 1 and end.month == 12 and end.day == 31
    if header_begin and header_end:
        full_year = full_year or (
            header_begin.month == 1
            and header_begin.day == 1
            and header_end.month == 12
            and header_end.day == 31
            and (n_days is not None and n_days >= 360)
            and not end_clipped
        )
    return {
        "begin": begin.isoformat(),
        "end": end.isoformat(),
        "begin_date": begin,
        "end_date": end,
        "full_calendar_year": bool(full_year),
        "n_days": n_days,
        "source": str(path),
        "last_row_hour": last_row_hour,
        "end_clipped_from_partial_day": end_clipped,
        "partial_day_only": False,
        "ok": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build AMY EPW from weather CSV")
    p.add_argument("weather_csv", type=Path)
    p.add_argument("-o", "--out", type=Path, required=True)
    p.add_argument("--lat", type=float, default=41.98)
    p.add_argument("--lon", type=float, default=-87.92)
    p.add_argument("--elevation-m", type=float, default=200.0)
    p.add_argument("--name", default="OpenFDD_AMY")
    args = p.parse_args(argv)
    meta = build_amy_epw(
        args.weather_csv,
        args.out,
        lat=args.lat,
        lon=args.lon,
        elevation_m=args.elevation_m,
        location_name=args.name,
    )
    print(meta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
