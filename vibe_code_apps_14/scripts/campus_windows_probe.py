#!/usr/bin/env python3
"""
Windows campus client — Who-Is-Router-To-Network + routed read of every building device.

Copy to the laptop (only this file + pip install bacpypes3 ifaddr):

  python campus_windows_probe.py --campus 192.168.204.18

Devices (via router at campus IP):
  net 200  device,1001   Building mini   analog-value,1
  net 201  device,3456790  VAV @ 192.168.204.14  analog-input,1 (ZoneTemp)
  net 202  device,3456789  AHU @ 192.168.0.13  analog-input,1 (DAP-P)
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import sys
from dataclasses import dataclass
from typing import List, Tuple

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.npdu import IAmRouterToNetwork
from bacpypes3.netservice import NetworkAdapter
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier


@dataclass(frozen=True)
class RoutedDevice:
    label: str
    network: int
    instance: int
    object_id: str
    property_id: str = "present-value"


DEFAULT_DEVICES = (
    RoutedDevice("Building mini", 200, 1001, "analog-value,1"),
    RoutedDevice("Bens fake VAV", 201, 3456790, "analog-input,1"),
    RoutedDevice("Bens fake AHU", 202, 3456789, "analog-input,1"),
)


def _subnet_broadcast(campus_ip: str, port: int) -> Address:
    net = ipaddress.ip_network(f"{campus_ip}/24", strict=False)
    return Address(f"{net.broadcast_address}:{port}")


async def wirtn(
    app: Application, campus_ip: str, port: int, use_broadcast: bool
) -> bool:
    if not app.nse:
        print("FAIL  client has no NetworkServiceElement", file=sys.stderr)
        return False

    dest = (
        _subnet_broadcast(campus_ip, port)
        if use_broadcast
        else Address(f"{campus_ip}:{port}")
    )
    print(f"\n=== Who-Is-Router-To-Network  ->  {dest} ===")
    try:
        replies: List[Tuple[NetworkAdapter, IAmRouterToNetwork]] = (
            await app.nse.who_is_router_to_network(destination=dest)
        )
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  {exc}", file=sys.stderr)
        return False

    if not replies:
        print("FAIL  no I-Am-Router-To-Network", file=sys.stderr)
        return False

    for _adapter, iam in replies:
        print(f"OK    router @ {iam.pduSource}  networks={list(iam.iartnNetworkList)}")
    return True


async def probe_device(app: Application, campus_ip: str, dev: RoutedDevice) -> bool:
    routed = Address(f"{dev.network}:{dev.instance}@{campus_ip}")
    print(f"\n=== {dev.label}  {routed} ===")

    iams = await app.who_is(dev.instance, dev.instance, address=routed)
    if not iams:
        print("FAIL  no I-Am", file=sys.stderr)
        return False
    for iam in iams:
        print(f"OK    I-Am  {iam.iAmDeviceIdentifier}  from  {iam.pduSource}")

    point = ObjectIdentifier(dev.object_id)
    try:
        value = await app.read_property(routed, point, dev.property_id)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  ReadProperty: {exc}", file=sys.stderr)
        return False

    print(f"OK    {dev.object_id}.{dev.property_id} = {value!r}")
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campus", default="192.168.204.18")
    parser.add_argument("--client-bind", default="0.0.0.0:47813")
    parser.add_argument("--router-port", type=int, default=47808)
    parser.add_argument("--wirtn-broadcast", action="store_true")
    parser.add_argument("--skip-wirtn", action="store_true")
    parser.add_argument(
        "--skip-ahu",
        action="store_true",
        help="Skip net 202 AHU probe when 192.168.0.13 is offline",
    )
    args = parser.parse_args()

    bp = SimpleArgumentParser()
    app = Application.from_args(
        bp.parse_args(["--address", args.client_bind, "--route-aware"])
    )

    print(f"Campus head-end: {args.campus}:{args.router_port}")
    print(f"Client bind:     {args.client_bind}  (route-aware)")

    ok = True
    if not args.skip_wirtn:
        ok = await wirtn(app, args.campus, args.router_port, args.wirtn_broadcast)

    for dev in DEFAULT_DEVICES:
        if args.skip_ahu and dev.network == 202:
            continue
        ok = await probe_device(app, args.campus, dev) and ok

    app.close()
    if ok:
        print("\nPASS  all campus routed probes succeeded")
        return 0
    print("\nFAIL  one or more probes failed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
