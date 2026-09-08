"""BACpypes3 BACnet/IP device bridged to PointBus."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .bus import PointKind
from .runtime import TwinRuntime

log = logging.getLogger(__name__)


async def run_bacnet_device(runtime: TwinRuntime, argv: list[str] | None = None) -> None:
    """Start a BACnet/IP application and mirror bus ↔ objects.

    Intended for Linux lab bind. Uses BACpypes3 SimpleArgumentParser flags
    (``--address``, ``--name``, ``--instance``, …) like ``scripts/fake_ahu.py``.
    """
    from bacpypes3.app import Application
    from bacpypes3.argparse import SimpleArgumentParser
    from bacpypes3.local.analog import AnalogInputObject, AnalogOutputObject, AnalogValueObject
    from bacpypes3.local.binary import BinaryInputObject, BinaryOutputObject
    from bacpypes3.local.cmd import Commandable

    class CommandableAnalogValueObject(Commandable, AnalogValueObject):
        pass

    args = SimpleArgumentParser().parse_args(argv)
    app = Application.from_args(args)
    objects: dict[str, Any] = {}
    ai_n = ao_n = av_n = bi_n = bo_n = 1

    for row in runtime.bus.snapshot():
        name = row["name"]
        kind = row["kind"]
        units = row["units"] or None
        pv = float(row["present_value"])
        if kind == PointKind.SENSOR.value:
            if row["binary"] or name in {"FAN-S"}:
                obj = BinaryInputObject(
                    objectIdentifier=("binaryInput", bi_n),
                    objectName=name,
                    presentValue="active" if pv >= 0.5 else "inactive",
                    description=row["description"],
                )
                bi_n += 1
            else:
                obj = AnalogInputObject(
                    objectIdentifier=("analogInput", ai_n),
                    objectName=name,
                    presentValue=pv,
                    units=units or "noUnits",
                    description=row["description"],
                )
                ai_n += 1
        else:
            if name == "UNIT-ENABLE":
                obj = BinaryOutputObject(
                    objectIdentifier=("binaryOutput", bo_n),
                    objectName=name,
                    presentValue="active" if pv >= 0.5 else "inactive",
                    description=row["description"],
                )
                bo_n += 1
            elif name in {"HEAT-SP", "COOL-SP"}:
                obj = CommandableAnalogValueObject(
                    objectIdentifier=("analogValue", av_n),
                    objectName=name,
                    presentValue=pv,
                    units=units or "degreesFahrenheit",
                    covIncrement=0.1,
                    description=row["description"],
                )
                av_n += 1
            else:
                obj = AnalogOutputObject(
                    objectIdentifier=("analogOutput", ao_n),
                    objectName=name,
                    presentValue=pv,
                    units=units or "noUnits",
                    covIncrement=0.1,
                    description=row["description"],
                )
                ao_n += 1
        app.add_object(obj)
        objects[name] = obj

    log.info("BACnet twin online with %d objects", len(objects))

    async def mirror_loop() -> None:
        while True:
            # BACnet → bus (commandable)
            for name, obj in objects.items():
                state = runtime.bus.get(name)
                if state.definition.kind is not PointKind.COMMANDABLE:
                    continue
                raw = obj.presentValue
                if isinstance(raw, str):
                    value = 1.0 if raw == "active" else 0.0
                else:
                    value = float(raw)
                # BACnet stack presentValue is the resolved value; write at priority 16
                # as the device-local fallback unless a higher UI/BACnet slot exists.
                # Higher-priority BACnet writes from clients typically update presentValue
                # via Commandable; we sample resolved PV into priority 10 as "bacnet-pv".
                if abs(runtime.bus.present(name) - value) > 1e-6:
                    # Only push into bus when BACnet differs and UI-8 is not winning.
                    win = state.winning_priority()
                    if win is None or win >= 10:
                        runtime.bus.write(name, value, priority=10, source="bacnet")

            # Bus sensors → BACnet AIs
            for name, obj in objects.items():
                state = runtime.bus.get(name)
                if state.definition.kind is not PointKind.SENSOR:
                    continue
                pv = state.present_value()
                if isinstance(obj, BinaryInputObject):
                    obj.presentValue = "active" if pv >= 0.5 else "inactive"
                else:
                    obj.presentValue = float(pv)

            # Bus commands → BACnet when UI (8) or default wins
            for name, obj in objects.items():
                state = runtime.bus.get(name)
                if state.definition.kind is not PointKind.COMMANDABLE:
                    continue
                win = state.winning_priority()
                if win is not None and win <= 8:
                    pv = state.present_value()
                    if isinstance(obj, BinaryOutputObject):
                        obj.presentValue = "active" if pv >= 0.5 else "inactive"
                    else:
                        obj.presentValue = float(pv)

            await asyncio.sleep(0.5)

    asyncio.create_task(mirror_loop())
    await asyncio.Future()
