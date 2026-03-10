#!/usr/bin/env python3
"""
Mini BACnet Weather Device
--------------------------
Fetches OpenWeather data every 15 minutes and updates BACnet points every 5 seconds.

BACnet objects:
- analogValue,1  -> web-weather-drybulb-temp
- analogValue,2  -> web-weather-dewpoint-temp
- analogValue,3  -> web-weather-relative-humidity
- binaryValue,1  -> web-weather-fetch-ok
"""

import asyncio
import math
import os
import sys

import requests
from dotenv import load_dotenv

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.local.analog import AnalogValueObject
from bacpypes3.local.binary import BinaryValueObject
from bacpypes3.debugging import bacpypes_debugging, ModuleLogger

# -----------------------------------------------------------------------------
# Config / constants
# -----------------------------------------------------------------------------

INTERVAL = 5.0  # keep existing BACnet presentValue update interval
WEATHER_FETCH_INTERVAL = 900.0  # 15 minutes

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY = os.getenv("CITY", "Madison,WI,US")
UNITS = os.getenv("UNITS", "imperial")  # imperial / metric / standard

_debug = 0
_log = ModuleLogger(globals())


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def calc_dewpoint(temp_value: float, rh_percent: float, units: str) -> float:
    """
    Calculate dew point from dry bulb temperature and relative humidity.

    Magnus formula is used internally in degC, then converted back if needed.
    """
    if rh_percent <= 0:
        raise ValueError("Relative humidity must be greater than 0")

    # Convert input temp to C
    if units == "imperial":
        temp_c = (temp_value - 32.0) * 5.0 / 9.0
    elif units == "metric":
        temp_c = temp_value
    elif units == "standard":
        temp_c = temp_value - 273.15
    else:
        temp_c = temp_value

    # Magnus approximation
    a = 17.625
    b = 243.04  # degC
    gamma = math.log(rh_percent / 100.0) + (a * temp_c) / (b + temp_c)
    dewpoint_c = (b * gamma) / (a - gamma)

    # Convert back to requested units
    if units == "imperial":
        return (dewpoint_c * 9.0 / 5.0) + 32.0
    elif units == "metric":
        return dewpoint_c
    elif units == "standard":
        return dewpoint_c + 273.15
    return dewpoint_c


def build_weather_url() -> str:
    if not API_KEY:
        raise ValueError("OPENWEATHER_API_KEY environment variable is not set")

    return (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={CITY}&appid={API_KEY}&units={UNITS}"
    )


def fetch_weather() -> dict:
    """
    Fetch current weather from OpenWeather and return normalized values.
    """
    url = build_weather_url()
    response = requests.get(url, timeout=15)
    response.raise_for_status()

    data = response.json()
    main = data["main"]

    drybulb = float(main["temp"])
    rh = float(main["humidity"])
    dewpoint = calc_dewpoint(drybulb, rh, UNITS)

    return {
        "drybulb": drybulb,
        "rh": rh,
        "dewpoint": dewpoint,
        "fetch_ok": True,
        "raw": data,
    }


# -----------------------------------------------------------------------------
# BACnet object classes
# -----------------------------------------------------------------------------

@bacpypes_debugging
class SampleApplication:
    """
    BACnet application exposing four points:

    - analogValue,1: web-weather-drybulb-temp
    - analogValue,2: web-weather-dewpoint-temp
    - analogValue,3: web-weather-relative-humidity
    - binaryValue,1: web-weather-fetch-ok
    """

    def __init__(self, args):
        if _debug:
            _log.debug("Initializing SampleApplication")

        self.app = Application.from_args(args)

        temp_units = {
            "imperial": "degreesFahrenheit",
            "metric": "degreesCelsius",
            "standard": "kelvin",
        }.get(UNITS, "degreesFahrenheit")

        # Weather cache
        self.latest_weather = {
            "drybulb": 0.0,
            "dewpoint": 0.0,
            "rh": 0.0,
            "fetch_ok": False,
        }

        # BACnet read-only weather points
        self.web_weather_temp_av = AnalogValueObject(
            objectIdentifier=("analogValue", 1),
            objectName="web-weather-drybulb-temp",
            presentValue=0.0,
            statusFlags=[0, 0, 0, 0],
            covIncrement=0.5,
            units=temp_units,
            description="Outdoor dry bulb temperature from OpenWeather",
        )

        self.web_weather_dewpoint_av = AnalogValueObject(
            objectIdentifier=("analogValue", 2),
            objectName="web-weather-dewpoint-temp",
            presentValue=0.0,
            statusFlags=[0, 0, 0, 0],
            covIncrement=0.5,
            units=temp_units,
            description="Outdoor dew point calculated from dry bulb and RH",
        )

        self.web_weather_rh_av = AnalogValueObject(
            objectIdentifier=("analogValue", 3),
            objectName="web-weather-relative-humidity",
            presentValue=0.0,
            statusFlags=[0, 0, 0, 0],
            covIncrement=1.0,
            units="percentRelativeHumidity",
            description="Outdoor relative humidity from OpenWeather",
        )

        self.web_weather_fetch_ok_bv = BinaryValueObject(
            objectIdentifier=("binaryValue", 1),
            objectName="web-weather-fetch-ok",
            presentValue="inactive",
            statusFlags=[0, 0, 0, 0],
            description="Active when latest web weather fetch succeeded",
        )

        for obj in [
            self.web_weather_temp_av,
            self.web_weather_dewpoint_av,
            self.web_weather_rh_av,
            self.web_weather_fetch_ok_bv,
        ]:
            self.app.add_object(obj)

        _log.info("BACnet weather objects initialized.")

        # Start loops
        asyncio.create_task(self.weather_fetch_loop())
        asyncio.create_task(self.update_values())

    async def weather_fetch_loop(self) -> None:
        """
        Fetch weather every 15 minutes and store in cache.
        """
        while True:
            try:
                weather = await asyncio.to_thread(fetch_weather)

                self.latest_weather["drybulb"] = weather["drybulb"]
                self.latest_weather["dewpoint"] = weather["dewpoint"]
                self.latest_weather["rh"] = weather["rh"]
                self.latest_weather["fetch_ok"] = True

                _log.info(
                    "Weather fetch OK | drybulb=%.2f dewpoint=%.2f rh=%.2f",
                    self.latest_weather["drybulb"],
                    self.latest_weather["dewpoint"],
                    self.latest_weather["rh"],
                )

                if _debug:
                    _log.debug(f"Raw weather payload: {weather['raw']}")

            except Exception as err:
                self.latest_weather["fetch_ok"] = False
                _log.error(f"Weather fetch failed: {err}")

            await asyncio.sleep(WEATHER_FETCH_INTERVAL)

    async def update_values(self) -> None:
        """
        Keep existing 5-second BACnet presentValue update loop,
        but now publish the latest cached weather values into BACnet objects.
        """
        while True:
            await asyncio.sleep(INTERVAL)

            self.web_weather_temp_av.presentValue = float(self.latest_weather["drybulb"])
            self.web_weather_dewpoint_av.presentValue = float(self.latest_weather["dewpoint"])
            self.web_weather_rh_av.presentValue = float(self.latest_weather["rh"])
            self.web_weather_fetch_ok_bv.presentValue = (
                "active" if self.latest_weather["fetch_ok"] else "inactive"
            )

            if _debug:
                _log.debug(
                    "BACnet updated | temp=%.2f dewpoint=%.2f rh=%.2f fetch_ok=%s",
                    self.web_weather_temp_av.presentValue,
                    self.web_weather_dewpoint_av.presentValue,
                    self.web_weather_rh_av.presentValue,
                    self.web_weather_fetch_ok_bv.presentValue,
                )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

async def main() -> None:
    global _debug

    parser = SimpleArgumentParser()
    args = parser.parse_args()

    if args.debug:
        _debug = 1
        _log.set_level("DEBUG")
        _log.debug("Debug mode enabled")

    if _debug:
        _log.debug(f"Parsed arguments: {args}")

    SampleApplication(args)

    # run forever
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log.info("Keyboard interrupt received, shutting down.")
        sys.exit(0)