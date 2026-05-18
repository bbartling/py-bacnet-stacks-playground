#!/usr/bin/env python3
"""Generate BACnet traffic against the ipv4-to-ipv4 router (Who-Is + I-Am-Router)."""

from __future__ import annotations

import argparse
import asyncio
import os

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.pdu import Address


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("HOST_IP", "127.0.0.1"))
    parser.add_argument("--client-port", type=int, default=47812)
    parser.add_argument("--router-port", type=int, default=47808)
    args = parser.parse_args()

    bp = SimpleArgumentParser()
    app = Application.from_args(
        bp.parse_args(["--address", f"{args.host}:{args.client_port}"])
    )

    router_addr = Address(f"{args.host}:{args.router_port}")
    print(f"Who-Is to router leg @ {router_addr}")
    i_ams = await app.who_is(998, 998, address=router_addr)
    for iam in i_ams or []:
        print(f"  I-Am {iam.iAmDeviceIdentifier} @ {iam.pduSource}")

  # Broadcast Who-Is-Router on default port world
    print("Who-Is (global) from client bind")
    try:
        i_ams2 = await app.who_is()
        for iam in i_ams2 or []:
            print(f"  I-Am {iam.iAmDeviceIdentifier} @ {iam.pduSource}")
    except Exception as exc:  # noqa: BLE001
        print(f"  global Who-Is: {exc}")

    app.close()


if __name__ == "__main__":
    asyncio.run(main())
