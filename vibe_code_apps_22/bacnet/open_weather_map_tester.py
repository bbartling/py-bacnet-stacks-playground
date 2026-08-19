import argparse
import os
from datetime import datetime, timezone

import requests

try:
    from dotenv import load_dotenv

    # Always prefer junk/.env over a stale OPENWEATHER_API_KEY in the shell.
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)
except ImportError:
    pass

"""
.env:
  OPENWEATHER_API_KEY=...
  LAT=43.0731
  LON=-89.4012

Default units: Fahrenheit. One Call 4.0 hourly forecast is 48h ahead.

  python open_weather_map_tester.py
  python open_weather_map_tester.py --metric
  python open_weather_map_tester.py --hours 36
"""


def fetch(url, params=None):
    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        raise SystemExit(
            f"One Call 4.0 error {resp.status_code}: {resp.text.strip()[:400]}\n"
            "Confirm One Call 4.0 is on this key:\n"
            "https://home.openweathermap.org/subscriptions"
        )
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="One Call 4.0 hourly temp / humidity / dewpoint")
    parser.add_argument(
        "--metric",
        action="store_true",
        help="Celsius (default is Fahrenheit)",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=48,
        help="Forecast hours to print (default 48, One Call 4.0 hourly max ahead)",
    )
    args = parser.parse_args()

    api_key = (os.getenv("OPENWEATHER_API_KEY") or "").strip()
    lat = float(os.getenv("LAT", "43.0731"))  # Madison, WI
    lon = float(os.getenv("LON", "-89.4012"))
    units = "metric" if args.metric else "imperial"
    hours_n = max(1, args.hours)
    unit_symbol = "°C" if units == "metric" else "°F"

    if not api_key:
        raise ValueError("OPENWEATHER_API_KEY is not set in the .env file")

    url = "https://api.openweathermap.org/data/4.0/onecall/timeline/1h"
    params = {"lat": lat, "lon": lon, "appid": api_key, "units": units}
    now = int(datetime.now(timezone.utc).timestamp())
    rows = []

    while url and len(rows) < hours_n:
        body = fetch(url, params)
        params = None
        hours = body.get("data") or []
        if isinstance(hours, dict):
            hours = [hours]
        for hour in hours:
            if hour.get("dt", 0) < now:
                continue
            rows.append(hour)
            if len(rows) >= hours_n:
                break
        url = body.get("next") if len(rows) < hours_n else None

    print(
        f"Madison hourly 4.0 ({lat:.4f},{lon:.4f}) — "
        f"temp / humidity / dewpoint ({len(rows)}h {unit_symbol})"
    )
    if not rows:
        raise SystemExit("No hourly rows returned (check LAT/LON and subscription).")
    for hour in rows[:hours_n]:
        ts = datetime.fromtimestamp(hour["dt"], tz=timezone.utc).isoformat()
        temp = hour.get("temp")
        humidity = hour.get("humidity")
        dew = hour.get("dew_point")
        dew_s = f"{dew}{unit_symbol}" if dew is not None else "n/a"
        print(f"{ts}  {temp}{unit_symbol}  {humidity}%  dew {dew_s}")


if __name__ == "__main__":
    main()
