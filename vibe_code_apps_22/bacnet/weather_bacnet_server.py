#!/home/ben/junk/env/bin/python
"""Live OA weather as a BACnet/IP analog-input device (rusty_bacnet).

Bind: enp3s0 192.168.204.55/24  UDP 47808  broadcast 192.168.204.255

  Device 204055  vibe app 22

  AI:1   Outside Air Dry Bulb     (°F default, units 64)
  AI:2   Outside Air Humidity     (%RH, units 29)
  AI:3   Outside Air Dewpoint     (°F default, units 64)
  CSV:1  API City                 reverse-geocoded from LAT/LON
  CSV:2  Last Updated             local-TZ stamp of last successful OWM poll

  $ python weather_bacnet_server.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv
from rusty_bacnet import (
    BACnetServer,
    ObjectIdentifier,
    ObjectType,
    PropertyIdentifier,
    PropertyValue,
)

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

OWM_TIMELINE = "https://api.openweathermap.org/data/4.0/onecall/timeline/1h"
OWM_REVERSE = "https://api.openweathermap.org/geo/1.0/reverse"
UNITS_F = 64  # degrees-Fahrenheit (ASHRAE 135) — not 62 (Celsius)
UNITS_C = 62
UNITS_RH = 29  # percent-relative-humidity
DEVICE_NAME = "vibe app 22"
CSV_CITY = ObjectIdentifier(ObjectType.CHARACTERSTRING_VALUE, 1)
CSV_UPDATED = ObjectIdentifier(ObjectType.CHARACTERSTRING_VALUE, 2)


def log(msg: str) -> None:
    print(msg, flush=True)
    sys.stdout.flush()


def nearest_hour(hours: list[dict], now: int) -> dict:
    if not hours:
        raise RuntimeError("One Call 4.0 returned no hourly rows")
    return min(hours, key=lambda h: abs(int(h.get("dt") or 0) - now))


def fetch_oa(api_key: str, lat: float, lon: float, units: str) -> dict:
    resp = requests.get(
        OWM_TIMELINE,
        params={"lat": lat, "lon": lon, "appid": api_key, "units": units},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"One Call 4.0 HTTP {resp.status_code}: {resp.text.strip()[:300]}"
        )
    body = resp.json()
    hours = body.get("data") or []
    if isinstance(hours, dict):
        hours = [hours]
    row = nearest_hour(hours, int(time.time()))
    temp = row.get("temp")
    rh = row.get("humidity")
    dew = row.get("dew_point")
    if temp is None or rh is None or dew is None:
        raise RuntimeError(f"hourly row missing temp/humidity/dew_point: {row!r}")
    return {
        "temp": float(temp),
        "humidity": float(rh),
        "dew_point": float(dew),
        "dt": int(row.get("dt") or 0),
    }


def fetch_city(api_key: str, lat: float, lon: float) -> str:
    resp = requests.get(
        OWM_REVERSE,
        params={"lat": lat, "lon": lon, "limit": 1, "appid": api_key},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Geo reverse HTTP {resp.status_code}: {resp.text.strip()[:300]}"
        )
    rows = resp.json()
    if not rows:
        return f"{lat:.4f}, {lon:.4f}"
    place = rows[0]
    parts = [
        str(place.get("name") or "").strip(),
        str(place.get("state") or "").strip(),
        str(place.get("country") or "").strip(),
    ]
    city = ", ".join(p for p in parts if p)
    return city or f"{lat:.4f}, {lon:.4f}"


def local_updated_stamp() -> str:
    """Human-readable last-update time in this box's configured timezone."""
    return datetime.now().astimezone().strftime("%a %b %d, %Y %I:%M:%S %p %Z")


async def write_csv(server: BACnetServer, oid: ObjectIdentifier, text: str) -> None:
    await server.write_property_local(
        oid,
        PropertyIdentifier.PRESENT_VALUE,
        PropertyValue.character_string(text),
        priority=16,
    )


async def enable_ai_present_value_writes(server: BACnetServer) -> None:
    """Analog Input Present_Value is writable only while Out_Of_Service (Clause 12.2)."""
    for inst in (1, 2, 3):
        await server.write_property_local(
            ObjectIdentifier(ObjectType.ANALOG_INPUT, inst),
            PropertyIdentifier.OUT_OF_SERVICE,
            PropertyValue.boolean(True),
        )


async def publish(server: BACnetServer, sample: dict, city: str, updated: str) -> None:
    pairs = (
        (1, sample["temp"]),
        (2, sample["humidity"]),
        (3, sample["dew_point"]),
    )
    for inst, value in pairs:
        await server.write_property_local(
            ObjectIdentifier(ObjectType.ANALOG_INPUT, inst),
            PropertyIdentifier.PRESENT_VALUE,
            PropertyValue.real(value),
        )
    await write_csv(server, CSV_CITY, city)
    await write_csv(server, CSV_UPDATED, updated)


async def run(args: argparse.Namespace) -> None:
    api_key = (os.getenv("OPENWEATHER_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("OPENWEATHER_API_KEY missing — set it in junk/.env")
    lat = float(os.getenv("LAT", "43.0731"))
    lon = float(os.getenv("LON", "-89.4012"))
    units = "metric" if args.metric else "imperial"
    deg = UNITS_C if args.metric else UNITS_F
    unit_sym = "°C" if args.metric else "°F"

    log(f"Fetching OpenWeather One Call 4.0 for {lat:.4f},{lon:.4f} ({units})…")
    sample = fetch_oa(api_key, lat, lon, units)
    try:
        city = fetch_city(api_key, lat, lon)
    except Exception as exc:
        city = f"{lat:.4f}, {lon:.4f}"
        log(f"Geo reverse failed, using coordinates: {exc}")
    updated = local_updated_stamp()

    server = BACnetServer(
        device_instance=args.device_instance,
        device_name=DEVICE_NAME,
        interface=args.bind,
        port=args.port,
        broadcast_address=args.broadcast,
    )
    server.add_analog_input(
        instance=1,
        name="Outside Air Dry Bulb",
        units=deg,
        present_value=sample["temp"],
    )
    server.add_analog_input(
        instance=2,
        name="Outside Air Humidity",
        units=UNITS_RH,
        present_value=sample["humidity"],
    )
    server.add_analog_input(
        instance=3,
        name="Outside Air Dewpoint",
        units=deg,
        present_value=sample["dew_point"],
    )
    server.add_character_string_value(instance=1, name="API City")
    server.add_character_string_value(instance=2, name="Last Updated")
    await server.start()
    await enable_ai_present_value_writes(server)
    await publish(server, sample, city, updated)
    addr = await server.local_address()
    log(
        f"BACnet/IP server {addr}  device {args.device_instance}  {DEVICE_NAME!r}\n"
        f"  bind {args.bind}  broadcast {args.broadcast}\n"
        f"  city {city}\n"
        f"  last updated {updated}\n"
        f"  AI:1 dry-bulb {sample['temp']}{unit_sym}\n"
        f"  AI:2 humidity {sample['humidity']}%RH\n"
        f"  AI:3 dewpoint {sample['dew_point']}{unit_sym}\n"
        f"  CSV:1 API City / CSV:2 Last Updated\n"
        f"Poll every {args.poll}s. Who-Is this device from YABE on 192.168.204.0/24."
    )

    try:
        while True:
            await asyncio.sleep(args.poll)
            try:
                sample = fetch_oa(api_key, lat, lon, units)
                updated = local_updated_stamp()
                await publish(server, sample, city, updated)
                log(
                    f"updated {updated}  {city}  "
                    f"{sample['temp']}{unit_sym}  "
                    f"{sample['humidity']}%  "
                    f"dew {sample['dew_point']}{unit_sym}"
                )
            except Exception as exc:
                log(f"OWM poll failed (keeping last Present_Value): {exc}")
    finally:
        await server.stop()


def main() -> None:
    p = argparse.ArgumentParser(description="OpenWeather OA → rusty_bacnet Analog Inputs")
    p.add_argument("--bind", default="192.168.204.55", help="enp3s0 IPv4")
    p.add_argument("--broadcast", default="192.168.204.255")
    p.add_argument("--port", type=int, default=47808)
    p.add_argument("--device-instance", type=int, default=204055)
    p.add_argument("--poll", type=int, default=1200, help="OWM refresh seconds")
    p.add_argument("--metric", action="store_true", help="°C instead of °F")
    args = p.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
