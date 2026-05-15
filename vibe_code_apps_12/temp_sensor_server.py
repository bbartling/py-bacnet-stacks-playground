#!/usr/bin/env python3
"""
Mini BACnet DS18B20 Temperature Device (Raspberry Pi B+ friendly)
================================================================

Expose **two** read-only BACnet **analogValue** objects from one **DS18B20**
**1-Wire** sensor on **GPIO4** (physical pin 7) with a **4.7 kΩ** pull-up to **3.3 V**.

Included BACnet objects (hard-coded):
--------------------------------------
- analogValue,1 → **degrees Celsius** (same sensor)
- analogValue,2 → **degrees Fahrenheit** (same sensor)


Typical Raspberry Pi (1-Wire enabled — see README):
---------------------------------------------------
    python temp_sensor_server.py --name PiTemp --instance 3456788 \\
        --address 192.168.204.12/24 --debug


If multiple DS18B20 folders exist, pick one::

    python temp_sensor_server.py --name PiTemp --instance 3456788 \\
        --address 192.168.204.12/24 --w1-device 28-0315977934ff

Override sysfs path::

    --w1-slave-path /sys/bus/w1/devices/28-xxxxxxxxxxxx/w1_slave
"""

from __future__ import annotations

import asyncio
import sys

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.debugging import ModuleLogger, bacpypes_debugging
from bacpypes3.local.analog import AnalogValueObject

from ds18b20_sensor import Ds18b20SysfsReader


INTERVAL_DEFAULT = 2.0


_debug = 0
_log = ModuleLogger(globals())


def build_reader(args) -> Ds18b20SysfsReader:
    return Ds18b20SysfsReader(
        device_id=args.w1_device,
        w1_slave_path=args.w1_slave_path,
    )


def c_to_f(temp_c: float) -> float:
    return temp_c * 9.0 / 5.0 + 32.0


@bacpypes_debugging
class TemperatureApplication:
    def __init__(self, args):
        if _debug:
            _log.debug("Initializing TemperatureApplication")

        self.reader = build_reader(args)
        self.refresh_s = args.sample_interval

        self.app = Application.from_args(args)

        initial_c = self.reader.read_celsius()
        initial_f = c_to_f(initial_c)

        self.av_deg_c = AnalogValueObject(
            objectIdentifier=("analogValue", 1),
            objectName="local-ds18b20-temperature-degC",
            presentValue=float(initial_c),
            statusFlags=[0, 0, 0, 0],
            covIncrement=0.25,
            units="degreesCelsius",
            description="DS18B20 1-Wire — temperature in °C (see README)",
        )
        self.av_deg_f = AnalogValueObject(
            objectIdentifier=("analogValue", 2),
            objectName="local-ds18b20-temperature-degF",
            presentValue=float(initial_f),
            statusFlags=[0, 0, 0, 0],
            covIncrement=0.5,
            units="degreesFahrenheit",
            description="DS18B20 1-Wire — temperature in °F (see README)",
        )
        self.app.add_object(self.av_deg_c)
        self.app.add_object(self.av_deg_f)

        _log.info("BACnet analogValue,1 (°C) and analogValue,2 (°F) initialized.")

        asyncio.create_task(self.update_loop())

    async def update_loop(self) -> None:
        while True:
            await asyncio.sleep(self.refresh_s)

            try:
                temp_c = await asyncio.to_thread(self.reader.read_celsius)
                temp_f = c_to_f(temp_c)

                for av in (self.av_deg_c, self.av_deg_f):
                    sf = list(av.statusFlags)
                    av.statusFlags = [sf[0], 0, sf[2], sf[3]]

                self.av_deg_c.presentValue = float(temp_c)
                self.av_deg_f.presentValue = float(temp_f)

                if _debug:
                    _log.debug(f"Published BACnet: {temp_c:.3f} °C | {temp_f:.3f} °F")

            except Exception as err:  # noqa: BLE001
                _log.error(f"Temperature read failed: {err}")

                for av in (self.av_deg_c, self.av_deg_f):
                    sf = list(av.statusFlags)
                    av.statusFlags = [sf[0], 1, sf[2], sf[3]]


async def main() -> None:
    global _debug

    parser = SimpleArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=INTERVAL_DEFAULT,
        help=f"Seconds between BACnet updates (default {INTERVAL_DEFAULT})",
    )
    parser.add_argument(
        "--w1-device",
        type=str,
        default=None,
        help="1-Wire device id under /sys/bus/w1/devices/ (e.g. 28-0315977934ff); required if several 28-* exist",
    )
    parser.add_argument(
        "--w1-slave-path",
        type=str,
        default=None,
        help="Full path to w1_slave (overrides --w1-device)",
    )

    args = parser.parse_args()

    if args.debug:
        _debug = 1
        _log.set_level("DEBUG")
        _log.debug("Debug mode enabled")

    if _debug:
        _log.debug(f"Parsed arguments: {args}")

    TemperatureApplication(args)

    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log.info("Keyboard interrupt received, shutting down.")
        sys.exit(0)
