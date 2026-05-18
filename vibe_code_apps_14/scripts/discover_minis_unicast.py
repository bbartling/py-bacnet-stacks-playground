#!/usr/bin/env python3
"""Unicast Who-Is to mini devices on non-standard BACnet/IP UDP ports."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.pdu import Address


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("HOST_IP", "127.0.0.1"))
    parser.add_argument("--client-port", type=int, default=47812, help="local bind port")
    parser.add_argument("--mini-a-port", type=int, default=47809)
    parser.add_argument("--mini-b-port", type=int, default=47810)
    parser.add_argument("--instance-a", type=int, default=1001)
    parser.add_argument("--instance-b", type=int, default=1002)
    args = parser.parse_args()

    bp = SimpleArgumentParser()
    app_args = bp.parse_args(["--address", f"{args.host}:{args.client_port}"])
    app = Application.from_args(app_args)

    targets = [
        (args.mini_a_port, args.instance_a),
        (args.mini_b_port, args.instance_b),
    ]
    for port, inst in targets:
        dest = Address(f"{args.host}:{port}")
        i_ams = await app.who_is(inst, inst, address=dest)
        if not i_ams:
            print(f"no I-Am on {dest} for instance {inst}", file=sys.stderr)
            continue
        for iam in i_ams:
            print(f"{iam.iAmDeviceIdentifier} @ {iam.pduSource}")

    app.close()


if __name__ == "__main__":
    asyncio.run(main())
