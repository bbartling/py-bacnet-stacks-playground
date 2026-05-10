"""
BACnet Who-Is / I-Am sweep, then per-device object-list read (point index).

Run (bind address = *this host's* NIC on the BACnet subnet, not the field device IP):

  cd /home/ben
  python3 bas_build_spec/bacnet_scripts_example/point_discovery.py \\
    --name BensReadApp --instance 100 --address 192.168.204.18/24:47808 --debug

Requires: pip install bacpypes3

Who-Is device-instance range is capped at **4194303** (22-bit BACnet); larger values raise
``ParameterOutOfRange`` from bacpypes3.
"""

from __future__ import annotations

import asyncio
import sys

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.apdu import IAmRequest
from bacpypes3.primitivedata import ObjectIdentifier
from bacpypes3.debugging import ModuleLogger

# BACnet device instance number is 22 bits (ASHRAE 135); bacpypes3 enforces 0..4194303.
BACNET_MAX_DEVICE_INSTANCE = 4194303

_debug = 0
_log = ModuleLogger(globals())


async def read_object_list_for_i_am(app: Application, i_am: IAmRequest) -> None:
    """Use the I-Am source address and device instance (do not use the bind IP)."""
    device_instance = i_am.iAmDeviceIdentifier[1]
    target = i_am.pduSource
    device_oid = ObjectIdentifier(("device", device_instance))

    header = f"--- Device {device_instance} @ {target!s} ---"
    print(header)
    try:
        obj_list = await app.read_property(
            target,
            device_oid,
            "object-list",
        )
    except Exception as exc:  # noqa: BLE001 — lab script; show per-device failure
        print(f"  read object-list failed: {exc!r}")
        return

    if obj_list is None:
        print("  (empty object-list)")
        return
    print(f"  object-list count: {len(obj_list)}")
    for obj in obj_list:
        print(f"    {obj}")


async def main() -> None:
    app: Application | None = None
    try:
        parser = SimpleArgumentParser()
        args = parser.parse_args()

        if _debug:
            _log.debug("args: %r", args)

        app = Application.from_args(args)

        # Who-Is range (inclusive). High must be <= BACNET_MAX_DEVICE_INSTANCE.
        low, high = 1, BACNET_MAX_DEVICE_INSTANCE
        print(f"--- Who-Is ({low}..{high}) ---")
        i_ams: list[IAmRequest] = await app.who_is(low, high)
        if not i_ams:
            print("No I-Am replies in time window.")
            return

        print(f"Collected {len(i_ams)} I-Am response(s):")
        for i_am in sorted(i_ams, key=lambda m: m.iAmDeviceIdentifier[1]):
            print(
                f"  instance={i_am.iAmDeviceIdentifier[1]} "
                f"addr={i_am.pduSource!s} "
                f"vendor={getattr(i_am, 'vendorID', '?')}"
            )

        print()
        for i_am in sorted(i_ams, key=lambda m: m.iAmDeviceIdentifier[1]):
            await read_object_list_for_i_am(app, i_am)
            print()

    finally:
        if app is not None:
            app.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
