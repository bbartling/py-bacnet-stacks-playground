"""Build Actual Meteorological Year (AMY) EPW files from Open-Meteo / vibe19 weather CSVs.

EnergyPlus EPW data-period rows (35 weather fields after Minute). We fill dry-bulb,
dew-point, RH, pressure, GHI/DNI/DHI, wind; remaining fields use EnergyPlus
missing-value codes so the file still parses.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import pandas as pd

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


def _epw_header(
    *,
    location_name: str,
    lat: float,
    lon: float,
    elevation_m: float,
    wmo: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[str]:
    # Rough timezone from longitude
    tz = round(lon / 15.0)
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


def build_amy_epw(
    weather: Path | str | pd.DataFrame,
    out_path: Path | str,
    *,
    lat: float = 41.98,
    lon: float = -87.92,
    elevation_m: float = 200.0,
    location_name: str = "OpenFDD_AMY",
    wmo: str = "999999",
) -> dict[str, Any]:
    """Write an AMY EPW from vibe19/Open-Meteo weather. Returns metadata dict."""
    df = load_weather_frame(weather)
    hourly = resample_hourly(df)
    if hourly.empty:
        raise ValueError("No hourly weather rows after resample")

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
    )
    lines = header + [_data_row(ts, hourly.loc[ts]) for ts in hourly.index]
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "epw": str(out),
        "rows": len(hourly),
        "start_utc": str(start),
        "end_utc": str(end),
        "lat": lat,
        "lon": lon,
        "location_name": location_name,
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
