#!/usr/bin/env python3
"""
Mini BACnet RTD Temperature Device (Pi-friendly)
================================================

Expose a single read-only BACnet analogValue that tracks a Pt1000 RTD wired
through a resistor divider measured by an ADS1115 (I2C). The Raspberry Pi has
no native analog pins; GPIO is used indirectly via the I²C pins that talk to the ADC.

Included BACnet object:
-----------------------
- analogValue,1 → local-rtd-temperature (degrees Celsius by default)


Run (simulation mode on any machine):
-----------------------------------
    python temp_sensor_server.py --name BenchRtdPi --instance 3456 --sensor sim


Run on a Raspberry Pi with ADS1115 (see README for wiring):
-----------------------------------------------------------
    python temp_sensor_server.py --name BenchRtdPi --instance 3456788 \
        --address 192.168.204.12/24 --sensor ads1115 --debug

    # Or bind BACnet to a NIC name instead of IPv4 literals (needs `pip install ifaddr`, see README):
    # python temp_sensor_server.py ... --address eth0


Optional sensor flags (ADS1115 divider topology):
-----------------------------------------------
--r-series-ohms       Bias resistor from supply to divider tap (precision metal film)
--v-supply            Divider supply voltage matching your wiring (typically 3.300)
--ads-i2c-addr       ADS1115 address (default 0x48)
--ads-channel        ADS analog channel A0–A3 (default 0)
"""

from __future__ import annotations

import asyncio
import sys

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.debugging import ModuleLogger, bacpypes_debugging
from bacpypes3.local.analog import AnalogValueObject

from rtd_sensor import Ads1115DividerReader, DividerConfig, SimulatedRtdReader


INTERVAL_DEFAULT = 2.0


_debug = 0
_log = ModuleLogger(globals())


def build_reader(args):
    """Create the temperature reader backing store based on CLI mode."""
    if args.sensor == "sim":
        return SimulatedRtdReader()

    if args.sensor == "ads1115":
        divider = DividerConfig(r_series_ohms=args.r_series_ohms, v_supply=args.v_supply)
        return Ads1115DividerReader(
            channel=args.ads_channel,
            divider=divider,
            i2c_address=args.ads_i2c_addr,
            samples_to_average=args.ads_average,
            sample_delay_s=args.ads_sample_delay,
        )

    raise ValueError(f"Unknown sensor backend: {args.sensor}")


def c_to_f(temp_c: float) -> float:
    return temp_c * 9.0 / 5.0 + 32.0


def apply_units(temp_c: float, display: str) -> tuple[float, str]:
    if display == "celsius":
        return temp_c, "degreesCelsius"
    if display == "fahrenheit":
        return c_to_f(temp_c), "degreesFahrenheit"
    raise ValueError(display)


@bacpypes_debugging
class TemperatureApplication:
    def __init__(self, args):
        if _debug:
            _log.debug("Initializing TemperatureApplication")

        self.reader = build_reader(args)
        self.refresh_s = args.sample_interval
        self.display_units = args.display_units

        self.app = Application.from_args(args)

        initial_c = self.reader.read_celsius()
        initial_value, bacnet_units = apply_units(initial_c, self.display_units)

        self.rtd_temperature = AnalogValueObject(
            objectIdentifier=("analogValue", 1),
            objectName="local-rtd-temperature",
            presentValue=float(initial_value),
            statusFlags=[0, 0, 0, 0],
            covIncrement=0.25 if self.display_units == "celsius" else 0.5,
            units=bacnet_units,
            description="Pt1000 RTD measured via divider + ADS1115 (see README wiring)",
        )
        self.app.add_object(self.rtd_temperature)

        _log.info("BACnet analogValue,1 initialized (RTD temperature).")

        asyncio.create_task(self.update_loop())

    async def update_loop(self) -> None:
        while True:
            await asyncio.sleep(self.refresh_s)

            try:
                temp_c = await asyncio.to_thread(self.reader.read_celsius)
                value, _units_literal = apply_units(temp_c, self.display_units)

                # BACnet status flags bits: [in_alarm, fault, overridden, out_of_service]
                sf = list(self.rtd_temperature.statusFlags)
                self.rtd_temperature.statusFlags = [sf[0], 0, sf[2], sf[3]]
                self.rtd_temperature.presentValue = float(value)

                if _debug:
                    _log.debug(f"Published RTD BACnet value: {value:.3f}")

            except Exception as err:  # noqa: BLE001 - surface sensor failures in logs/status
                _log.error(f"Temperature read failed: {err}")

                sf = list(self.rtd_temperature.statusFlags)
                self.rtd_temperature.statusFlags = [sf[0], 1, sf[2], sf[3]]


async def main() -> None:
    global _debug

    parser = SimpleArgumentParser(description=__doc__)
    parser.add_argument(
        "--sensor",
        choices=["sim", "ads1115"],
        default="sim",
        help="Backend: pure software sine (sim) or Raspberry Pi ADS1115 divider (ads1115)",
    )
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=INTERVAL_DEFAULT,
        help=f"Seconds between BACnet updates (default {INTERVAL_DEFAULT})",
    )
    parser.add_argument(
        "--display-units",
        choices=["celsius", "fahrenheit"],
        default="celsius",
        help="BACnet engineering units attached to analogValue,1",
    )

    # Divider / ADC options
    parser.add_argument("--r-series-ohms", type=float, default=3300.0)
    parser.add_argument("--v-supply", type=float, default=3.300)
    parser.add_argument(
        "--ads-i2c-addr",
        type=lambda x: int(x, 0),
        default=0x48,
        help='ADS1115 7-bit I²C address, e.g. "0x48"',
    )
    parser.add_argument("--ads-channel", type=int, choices=(0, 1, 2, 3), default=0)
    parser.add_argument("--ads-average", type=int, default=8, help="ADC samples averaged per BACnet cycle")
    parser.add_argument("--ads-sample-delay", type=float, default=0.002, help="Delay between averaged samples")

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
