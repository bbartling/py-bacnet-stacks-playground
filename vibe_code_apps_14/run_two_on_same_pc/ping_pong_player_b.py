#!/usr/bin/env python3
"""
Ping-pong player B — run in terminal 2 (Windows or Linux).

Edit HOST_IP if needed, then:
  pip install bacpypes3 ifaddr
  python ping_pong_player_b.py

Terminal 1 must already be running: python ping_pong_player_a.py

No BACnet routing — direct ReadProperty to peer IP:port.
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
LOCAL_BIND = f"{HOST_IP}/24:47810"
PEER_ADDRESS = f"{HOST_IP}:47809"
DEVICE_NAME = "PingPong-B"
DEVICE_INSTANCE = 1002
IS_STARTER = False
PONG_LIMIT = 100
POLL_SECONDS = 0.8
PONG_OBJECT = "analog-value,1"


class CommandableAnalogValueObject(Commandable, AnalogValueObject):
    pass


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
        f"[B] loop started  bind={LOCAL_BIND}  peer={peer}  starter={IS_STARTER}",
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
        ]
    )
    app = Application.from_args(args)

    pong = CommandableAnalogValueObject(
        objectIdentifier=("analogValue", 1),
        objectName="pong",
        presentValue=0.0,
        description="Ping-pong counter",
    )
    app.add_object(pong)

    peer = Address(PEER_ADDRESS)
    print(
        f"[B] ready  {DEVICE_NAME} instance {DEVICE_INSTANCE}  {LOCAL_BIND}",
        flush=True,
    )

    asyncio.create_task(ping_pong_loop(app, pong, peer))
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[B] stopped.", file=sys.stderr)
