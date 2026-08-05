#!/usr/bin/env python
"""Build Madison AMY EPW from Open-Meteo for Lakeside demand window."""
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
import math
from pathlib import Path

import pandas as pd
import requests

ROOT = site_root()
OUT_DIR = ROOT / "eplus" / "weather"
ANSWERS = ROOT / "eplus" / "assumptions" / "answers.json"

# EPW missing codes
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


def f_to_c(t):
    if t is None or (isinstance(t, float) and math.isnan(t)):
        return MISS_TEMP
    return (float(t) - 32.0) * 5.0 / 9.0


def mph_to_ms(mph):
    if mph is None or (isinstance(mph, float) and math.isnan(mph)):
        return MISS_WIND_SPD
    return float(mph) * 0.44704


def fetch_open_meteo(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "dew_point_2m",
                "surface_pressure",
                "shortwave_radiation",
                "direct_normal_irradiance",
                "diffuse_radiation",
                "wind_speed_10m",
                "wind_direction_10m",
            ]
        ),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "UTC",
    }
    print(f"Open-Meteo archive {start}..{end} @ {lat},{lon}")
    r = requests.get(url, params=params, timeout=180)
    r.raise_for_status()
    block = r.json()["hourly"]
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
    return df.sort_values("timestamp_utc").drop_duplicates("timestamp_utc")


def to_local_standard(df: pd.DataFrame, tz_name: str = "America/Chicago") -> pd.DataFrame:
    """Stamp rows in local standard time (no DST) for EPW."""
    out = df.copy()
    out["ts_utc"] = pd.to_datetime(out["timestamp_utc"], utc=True)
    # CST fixed offset -6 for EPW (EnergyPlus local standard)
    out["ts_lst"] = out["ts_utc"] - pd.Timedelta(hours=6)
    out = out.set_index("ts_lst").sort_index()
    return out


def epw_header(lat, lon, elevation_m, start, end, name="Madison_AMY") -> list[str]:
    tz = -6.0
    loc = f"LOCATION,{name},WI,USA,AMY,726410,{lat:.3f},{lon:.3f},{tz:.1f},{elevation_m:.1f}"
    start_s = f"{start.month}/{start.day}"
    end_s = f"{end.month}/{end.day}"
    dow = start.day_name()
    return [
        loc,
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,Lakeside AMY from Open-Meteo archive (UTC→CST-6 LST)",
        "COMMENTS 2,Partial-year OK for GL14 overlap calibration",
        f"DATA PERIODS,1,1,Data,{dow},{start_s},{end_s}",
    ]


def data_row(ts: pd.Timestamp, row: pd.Series) -> str:
    year, month, day = int(ts.year), int(ts.month), int(ts.day)
    hour = int(ts.hour) + 1
    if hour > 24:
        hour = 24
    source = "?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9"
    db = round(f_to_c(row.get("dry_bulb_f")), 1)
    dp = round(f_to_c(row.get("dew_point_f")), 1)
    rh = row.get("relative_humidity_pct")
    rh_v = int(round(float(rh))) if pd.notna(rh) else MISS_RH
    rh_v = max(0, min(110, rh_v)) if rh_v != MISS_RH else MISS_RH
    press = (
        int(round(float(row["surface_pressure_hpa"]) * 100))
        if pd.notna(row.get("surface_pressure_hpa"))
        else MISS_PRESS
    )
    ghi = int(round(float(row["shortwave_radiation_wm2"] or 0))) if pd.notna(row.get("shortwave_radiation_wm2")) else 0
    dni = int(round(float(row["direct_normal_irradiance_wm2"] or 0))) if pd.notna(row.get("direct_normal_irradiance_wm2")) else 0
    dhi = int(round(float(row["diffuse_radiation_wm2"] or 0))) if pd.notna(row.get("diffuse_radiation_wm2")) else 0
    wd = int(round(float(row["wind_direction_deg"]))) % 360 if pd.notna(row.get("wind_direction_deg")) else MISS_WIND_DIR
    ws = round(mph_to_ms(row.get("wind_speed_mph")), 1)
    fields = [
        year, month, day, hour, 0, source, db, dp, rh_v, press,
        0, 0, MISS_RAD, ghi, dni, dhi,
        MISS_ILLUM, MISS_ILLUM, MISS_ILLUM, MISS_ILLUM,
        wd, ws, MISS_SKY, MISS_VIS, MISS_CEIL,
        MISS_PRECIP, MISS_AOD, MISS_SNOW, 0, MISS_ALBEDO, MISS_LIQ,
        0, 0, 0, 0,
    ]
    return ",".join(str(x) for x in fields)


def write_amy(df_lst: pd.DataFrame, out: Path, lat: float, lon: float) -> dict:
    hourly = df_lst.resample("h").mean(numeric_only=True).dropna(subset=["dry_bulb_f"])
    # Keep only complete local calendar days; start at first Aug 1 00:00 LST if present
    hourly = hourly.copy()
    hourly["date"] = hourly.index.date
    # Drop partial first/last days
    day_counts = hourly.groupby("date").size()
    full_days = set(day_counts[day_counts >= 24].index)
    hourly = hourly[hourly["date"].isin(full_days)]
    if hourly.empty:
        raise RuntimeError("No complete AMY days after resample")
    # Prefer calibration window starting 2025-08-01
    start_pref = pd.Timestamp("2025-08-01")
    if hourly.index.tz is not None:
        start_pref = start_pref.tz_localize(hourly.index.tz)
    # index may be tz-aware UTC-labeled CST
    hourly = hourly[hourly.index >= start_pref]
    # rebuild without date col
    hourly = hourly.drop(columns=["date"])
    start, end = hourly.index.min(), hourly.index.max()
    lines = epw_header(lat, lon, 261.0, start, end) + [
        data_row(ts, hourly.loc[ts]) for ts in hourly.index
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "epw": str(out),
        "rows": len(hourly),
        "start_lst": str(start),
        "end_lst": str(end),
        "lat": lat,
        "lon": lon,
    }


def download_tmy_placeholder(out: Path) -> Path:
    """Copy Chicago TMY as screening stand-in if Madison TMY download unavailable;
    prefer EnergyPlus weather if Madison present; else Chicago (climate 5A/6A neighbor).
    """
    candidates = [
        Path(r"C:\EnergyPlusV26-1-0\WeatherData\USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"),
    ]
    # Try energyplus.net style Madison if user dropped it
    local = list(OUT_DIR.glob("*Madison*.epw")) + list(OUT_DIR.glob("*MSN*.epw"))
    if local:
        return local[0]
    src = candidates[0]
    out.write_bytes(src.read_bytes())
    # Rewrite LOCATION name comment via sidecar note
    (out.with_suffix(".txt")).write_text(
        "Screening EPW: Chicago O'Hare TMY3 stand-in (Madison TMY not bundled). "
        "Calibration uses madison_amy_*.epw from Open-Meteo.\n",
        encoding="utf-8",
    )
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ans = json.loads(ANSWERS.read_text(encoding="utf-8"))
    lat, lon = float(ans["lat"]), float(ans["lon"])
    start = ans["data_window"]["start_utc"]
    end = ans["data_window"]["end_utc"]

    tmy_out = OUT_DIR / "madison_tmy_screening.epw"
    download_tmy_placeholder(tmy_out)
    print(f"screening epw: {tmy_out}")

    raw = fetch_open_meteo(lat, lon, start, end)
    raw.to_csv(OUT_DIR / "open_meteo_amy_hourly.csv", index=False)
    lst = to_local_standard(raw)
    amy_out = OUT_DIR / "madison_amy_202508_202607.epw"
    meta = write_amy(lst, amy_out, lat, lon)
    (OUT_DIR / "amy_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"AMY epw: {meta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
