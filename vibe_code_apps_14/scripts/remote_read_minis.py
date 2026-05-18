#!/usr/bin/env python3
"""
Run from a **second PC** on the LAN while the lab server runs timed minis.

This is **direct BACnet/IP** to each mini (unicast to :47809 / :47810). It is **not**
BACnet routing — there is no router in `run_timed_lab.sh minis`.

Example (on your Windows/Linux laptop):

  pip install bacpypes3 ifaddr
  python remote_read_minis.py --server 192.168.204.18

While on bensserver:

  sudo ./scripts/run_timed_lab.sh minis
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier

# mini-device-revisited.py read-only simulated "sensor"
SENSOR_OBJECT = "analog-value,1"
SENSOR_PROPERTY = "present-value"


async def probe_device(
    app: Application,
    server_ip: str,
    device_port: int,
    device_instance: int,
    label: str,
) -> bool:
    dest = Address(f"{server_ip}:{device_port}")
    print(f"\n=== {label}  instance {device_instance}  @ {dest} ===")

    i_ams = await app.who_is(device_instance, device_instance, address=dest)
    if not i_ams:
        print(f"FAIL  no I-Am (is timed lab running on {server_ip}?)", file=sys.stderr)
        return False

    for iam in i_ams:
        print(f"OK    I-Am  {iam.iAmDeviceIdentifier}  from  {iam.pduSource}")

    point = ObjectIdentifier(SENSOR_OBJECT)
    try:
        value = await app.read_property(dest, point, SENSOR_PROPERTY)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  ReadProperty {SENSOR_OBJECT} {SENSOR_PROPERTY}: {exc}", file=sys.stderr)
        return False

    print(f"OK    ReadProperty  {SENSOR_OBJECT}.{SENSOR_PROPERTY} = {value!r}")
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--server",
        required=True,
        help="Lab server LAN IP (e.g. 192.168.204.18 where run_timed_lab.sh runs)",
    )
    parser.add_argument(
        "--client-bind",
        default="0.0.0.0:47813",
        help="Local UDP bind for this PC (default 0.0.0.0:47813)",
    )
    parser.add_argument("--mini-a-port", type=int, default=47809)
    parser.add_argument("--mini-b-port", type=int, default=47810)
    parser.add_argument("--instance-a", type=int, default=1001)
    parser.add_argument("--instance-b", type=int, default=1002)
    args = parser.parse_args()

    bp = SimpleArgumentParser()
    app = Application.from_args(bp.parse_args(["--address", args.client_bind]))

    print(f"Client bind: {args.client_bind}")
    print(f"Server:      {args.server}")
    print("Mode:        direct unicast (not routed)")

    ok_a = await probe_device(
        app, args.server, args.mini_a_port, args.instance_a, "MiniA"
    )
    ok_b = await probe_device(
        app, args.server, args.mini_b_port, args.instance_b, "MiniB"
    )

    app.close()

    if ok_a and ok_b:
        print("\nPASS  both minis answered Who-Is and present-value read")
        return 0
    print("\nFAIL  one or both minis did not respond", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
