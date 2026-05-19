#!/usr/bin/env python3
"""
Ping-pong player B — BACnet network 200 — terminal 3.

Requires ping_pong_ipv4_router.py running in terminal 1 first.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Union

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.local.analog import AnalogValueObject
from bacpypes3.local.cmd import Commandable
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier

# --- hard-coded player B (edit HOST_IP for your PC) ---
HOST_IP = "192.168.204.18"
LOCAL_NETWORK = 200
PEER_NETWORK = 100
LOCAL_BIND = f"{HOST_IP}/24:47833"
ROUTER_ON_LOCAL_NET = f"{HOST_IP}:47831"
PEER_BIND_PORT = 47832
# Router device 998 / pong on net 100, reached via this host's net-200 router port.
PEER_ADDRESS = f"{PEER_NETWORK}:{HOST_IP}:47830@{ROUTER_ON_LOCAL_NET}"
DEVICE_NAME = "PingPong-B"
DEVICE_INSTANCE = 1002
IS_STARTER = False
PONG_LIMIT = 100
POLL_SECONDS = 0.8
PONG_OBJECT = "analog-value,1"


class CommandableAnalogValueObject(Commandable, AnalogValueObject):
    pass


async def discover_router(app: Application) -> None:
    if not app.nse:
        return
    try:
        results = await asyncio.wait_for(
            app.nse.who_is_router_to_network(
                destination=Address(ROUTER_ON_LOCAL_NET),
                network=PEER_NETWORK,
            ),
            timeout=3.0,
        )
        if results:
            src = results[0][1].pduSource
            print(f"[B] router for net {PEER_NETWORK}: {src}", flush=True)
        else:
            print(f"[B] WARN no router reply (using @ path in peer address)", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[B] WARN router discovery: {exc}", flush=True)


def _as_int(value: Union[int, float, None]) -> int:
    if value is None:
        return 0
    return int(round(float(value)))


async def read_peer_pong(app: Application, peer: Address) -> int:
    value = await app.read_property(
        peer,
        ObjectIdentifier(PONG_OBJECT),
        "present-value",
    )
    return _as_int(value)


async def ping_pong_loop(
    app: Application,
    pong: CommandableAnalogValueObject,
    peer: Address,
) -> None:
    last_peer = -1
    print(
        f"[B] loop started  net={LOCAL_NETWORK} bind={LOCAL_BIND}  "
        f"peer={peer}  starter={IS_STARTER}",
        flush=True,
    )

    while True:
        try:
            peer_val = await read_peer_pong(app, peer)
        except Exception as exc:  # noqa: BLE001
            print(f"[B] WARN peer read: {exc}", flush=True)
            await asyncio.sleep(POLL_SECONDS)
            continue

        local_val = _as_int(pong.presentValue)

        if peer_val >= PONG_LIMIT or local_val >= PONG_LIMIT:
            if local_val != 0:
                pong.presentValue = 0.0
                print(f"[B] RESET local -> 0 (peer={peer_val})", flush=True)
            await asyncio.sleep(POLL_SECONDS)
            continue

        acted = False
        new_local = local_val

        if peer_val == 0 and local_val == 0 and IS_STARTER:
            new_local = 1
            acted = True
        elif peer_val > local_val:
            new_local = peer_val + 1
            acted = True

        if acted:
            pong.presentValue = float(new_local)
            print(f"[B] HIT  peer={peer_val}  local {local_val} -> {new_local}", flush=True)
        elif peer_val != last_peer:
            print(f"[B] wait  peer={peer_val}  local={local_val}", flush=True)

        last_peer = peer_val
        await asyncio.sleep(POLL_SECONDS)


async def main() -> None:
    args = SimpleArgumentParser().parse_args(
        [
            "--name",
            DEVICE_NAME,
            "--instance",
            str(DEVICE_INSTANCE),
            "--address",
            LOCAL_BIND,
            "--network",
            str(LOCAL_NETWORK),
            "--route-aware",
        ]
    )
    app = Application.from_args(args)

    pong = CommandableAnalogValueObject(
        objectIdentifier=("analogValue", 1),
        objectName="pong",
        presentValue=0.0,
        description="Ping-pong counter (device 1002 / net 200)",
    )
    app.add_object(pong)

    peer = Address(PEER_ADDRESS)
    print(
        f"[B] ready  {DEVICE_NAME} instance {DEVICE_INSTANCE}  "
        f"net {LOCAL_NETWORK}  {LOCAL_BIND}",
        flush=True,
    )

    await discover_router(app)
    asyncio.create_task(ping_pong_loop(app, pong, peer))
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[B] stopped.", file=sys.stderr)
