#!/usr/bin/env python3
"""
Router + ping-pong player A (net 100) — terminal 1.

One BACpypes3 application: IPv4 router device 998 bridges net 100 (:47830)
and net 200 (:47831), plus commandable analog-value,1 on this device.
Start ping_pong_player_b.py in terminal 2 after this is running.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Union

from bacpypes3.app import Application
from bacpypes3.local.analog import AnalogValueObject
from bacpypes3.local.cmd import Commandable
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier
from bacpypes3.settings import settings

HOST_IP = "192.168.204.18"
PEER_NETWORK = 200
PEER_BIND_PORT = 47833
PEER_ADDRESS = f"{PEER_NETWORK}:{HOST_IP}:{PEER_BIND_PORT}"
IS_STARTER = True
PONG_LIMIT = 100
POLL_SECONDS = 0.8
PONG_OBJECT = "analog-value,1"
JSON_FILE = "router-local.json"


class CommandableAnalogValueObject(Commandable, AnalogValueObject):
    pass


def load_router_objects() -> list:
    path = Path(__file__).with_name(JSON_FILE)
    text = path.read_text().replace("HOST_IP_PLACEHOLDER", HOST_IP)
    cfg = json.loads(text)
    for key, value in cfg.get("BACpypes", {}).items():
        settings[key] = value
    return cfg["router"]


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
        f"[A] loop started  router+player A  peer={peer}  starter={IS_STARTER}",
        flush=True,
    )

    while True:
        try:
            peer_val = await read_peer_pong(app, peer)
        except Exception as exc:  # noqa: BLE001
            print(f"[A] WARN peer read: {exc}", flush=True)
            await asyncio.sleep(POLL_SECONDS)
            continue

        local_val = _as_int(pong.presentValue)

        if peer_val >= PONG_LIMIT or local_val >= PONG_LIMIT:
            if local_val != 0:
                pong.presentValue = 0.0
                print(f"[A] RESET local -> 0 (peer={peer_val})", flush=True)
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
            print(f"[A] HIT  peer={peer_val}  local {local_val} -> {new_local}", flush=True)
        elif peer_val != last_peer:
            print(f"[A] wait  peer={peer_val}  local={local_val}", flush=True)

        last_peer = peer_val
        await asyncio.sleep(POLL_SECONDS)


async def main() -> None:
    app = Application.from_json(load_router_objects())

    pong = CommandableAnalogValueObject(
        objectIdentifier=("analogValue", 1),
        objectName="pong",
        presentValue=0.0,
        description="Ping-pong on router device 998 / net 100",
    )
    app.add_object(pong)

    if app.nse:
        for adapter in app.nsap.adapters.values():
            netlist = [
                other.adapterNet
                for other in app.nsap.adapters.values()
                if other is not adapter and other.adapterNet is not None
            ]
            if netlist:
                await app.nse.i_am_router_to_network(adapter=adapter, network=netlist)

    peer = Address(PEER_ADDRESS)
    print(
        f"[A] ready  router device 998  nets 100:47830 <-> 200:47831  "
        f"peer {peer}",
        flush=True,
    )

    asyncio.create_task(ping_pong_loop(app, pong, peer))
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[A] stopped.", file=sys.stderr)
