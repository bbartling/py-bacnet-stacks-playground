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

BACnet + AWS IoT Core (BACnet every 2 s, MQTT default every 60 s)::
---------------------------------------------------
    python temp_sensor_server.py --name PiTemp --instance 3456788 \\
        --address 192.168.204.12/24 --aws-iot \\
        --sample-interval 2 --aws-interval 60 \\
        --aws-cert aws_iot_certs/device.cert.pem \\
        --aws-key aws_iot_certs/device.private.key

If multiple DS18B20 folders exist, pick one::

    python temp_sensor_server.py --name PiTemp --instance 3456788 \\
        --address 192.168.204.12/24 --w1-device 28-0315977934ff

Override sysfs path::

    --w1-slave-path /sys/bus/w1/devices/28-xxxxxxxxxxxx/w1_slave
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Optional

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.debugging import ModuleLogger, bacpypes_debugging
from bacpypes3.local.analog import AnalogValueObject

from ds18b20_sensor import Ds18b20SysfsReader
from fault_demo_schedule import FaultDemoScheduler


BACNET_INTERVAL_DEFAULT = 2.0
AWS_INTERVAL_DEFAULT = 60.0


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

        self.fault_demo = bool(getattr(args, "fault_demo", False))
        self.reader = None if self.fault_demo else build_reader(args)
        self._fault_scheduler = (
            FaultDemoScheduler(log=_log.info) if self.fault_demo else None
        )
        self.bacnet_interval_s = args.sample_interval
        self.aws_interval_s = args.aws_interval if args.aws_iot else None
        self._last_aws_publish = 0.0
        self._aws: Optional[object] = None
        self._aws_topic: Optional[str] = None
        if args.aws_iot:
            self._aws = self._build_aws_publisher(args)
            self._aws_topic = args.aws_topic

        self.app = Application.from_args(args)

        if self.fault_demo:
            initial_f = self._fault_scheduler.current_deg_f()
            initial_c = self._fault_scheduler.current_deg_c()
            _log.info(
                "FAULT-DEMO mode: synthetic temperatures (no 1-Wire). "
                + self._fault_scheduler.status_line()
            )
        else:
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
        if self._aws is not None:
            _log.info(
                f"AWS IoT publish enabled → {args.aws_topic} "
                f"(every {self.aws_interval_s}s; BACnet every {self.bacnet_interval_s}s)"
            )

        asyncio.create_task(self.update_loop())

    @staticmethod
    def _build_aws_publisher(args):
        try:
            from aws_iot_publisher import AwsIotPublisher
        except ImportError as err:
            raise SystemExit(
                "AWS IoT requires awsiotsdk: pip install awsiotsdk"
            ) from err

        cert = Path(args.aws_cert)
        key = Path(args.aws_key)
        if not cert.is_file():
            raise SystemExit(f"AWS cert not found: {cert}")
        if not key.is_file():
            raise SystemExit(f"AWS private key not found: {key}")

        return AwsIotPublisher(
            endpoint=args.aws_endpoint,
            cert_path=cert,
            key_path=key,
            client_id=args.aws_client_id,
            topic=args.aws_topic,
        )

    async def update_loop(self) -> None:
        while True:
            await asyncio.sleep(self.bacnet_interval_s)

            try:
                if self.fault_demo:
                    temp_f = self._fault_scheduler.current_deg_f()
                    temp_c = self._fault_scheduler.current_deg_c()
                else:
                    temp_c = await asyncio.to_thread(self.reader.read_celsius)
                    temp_f = c_to_f(temp_c)

                for av in (self.av_deg_c, self.av_deg_f):
                    sf = list(av.statusFlags)
                    av.statusFlags = [sf[0], 0, sf[2], sf[3]]

                self.av_deg_c.presentValue = float(temp_c)
                self.av_deg_f.presentValue = float(temp_f)

                if _debug:
                    _log.debug(f"Published BACnet: {temp_c:.3f} °C | {temp_f:.3f} °F")

                if self._aws is not None and self.aws_interval_s is not None:
                    now = time.monotonic()
                    if now - self._last_aws_publish >= self.aws_interval_s:
                        await asyncio.to_thread(self._aws.publish, temp_c, temp_f)
                        self._last_aws_publish = now
                        if _debug:
                            _log.debug(f"Published AWS IoT → {self._aws_topic}")

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
        default=BACNET_INTERVAL_DEFAULT,
        help=f"Seconds between sensor reads and BACnet AV updates (default {BACNET_INTERVAL_DEFAULT})",
    )
    parser.add_argument(
        "--aws-interval",
        type=float,
        default=AWS_INTERVAL_DEFAULT,
        help=f"Seconds between AWS IoT MQTT publishes when --aws-iot is set (default {AWS_INTERVAL_DEFAULT})",
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
    parser.add_argument(
        "--aws-iot",
        action="store_true",
        help="Also publish each reading to AWS IoT Core (MQTT 5, mTLS)",
    )
    parser.add_argument(
        "--aws-endpoint",
        type=str,
        default="a2ab6ncd4xlhhr-ats.iot.us-east-2.amazonaws.com",
        help="AWS IoT data endpoint hostname",
    )
    parser.add_argument(
        "--aws-cert",
        type=str,
        default="aws_iot_certs/vibe-code-app-12-temp-sensor.cert.pem",
        help="Device certificate PEM path",
    )
    parser.add_argument(
        "--aws-key",
        type=str,
        default="aws_iot_certs/vibe-code-app-12-temp-sensor.private.key",
        help="Device private key PEM path",
    )
    parser.add_argument(
        "--aws-client-id",
        type=str,
        default="basicPubSub",
        help="MQTT client ID (must match IoT policy)",
    )
    parser.add_argument(
        "--aws-topic",
        type=str,
        default="sdk/test/python",
        help="MQTT topic for temperature JSON",
    )
    parser.add_argument(
        "--fault-demo",
        action="store_true",
        help=(
            "Synthetic FDD test schedule (flatline, OOB high/low, rate faults) "
            "instead of reading the DS18B20; use with --aws-iot for cloud validation"
        ),
    )

    args = parser.parse_args()

    if args.fault_demo and not args.aws_iot:
        _log.warning("--fault-demo without --aws-iot: BACnet only (no MQTT to AWS)")

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
