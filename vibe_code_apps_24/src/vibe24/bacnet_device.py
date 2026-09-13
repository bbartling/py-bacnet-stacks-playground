"""BACpypes3 BACnet/IP device bridged to PointBus.

Aligned with Joel Bender's BACpypes3 sample:
https://github.com/JoelBender/BACpypes3/blob/main/samples/mini-device-revisited.py

- Commandable setpoints: Commandable + AnalogValueObject (not AnalogOutput)
- Commandable binaries: Commandable + BinaryValueObject (not BinaryOutput)
- statusFlags + covIncrement on values
- Update loop only mutates read-only sensors; commandables left for clients
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .bus import PointKind
from .runtime import TwinRuntime

log = logging.getLogger(__name__)


async def run_bacnet_device(runtime: TwinRuntime, argv: list[str] | None = None) -> None:
    """Start a BACnet/IP application and mirror bus <-> objects (Linux lab bind)."""
    from bacpypes3.app import Application
    from bacpypes3.argparse import SimpleArgumentParser
    from bacpypes3.basetypes import BinaryPV
    from bacpypes3.local.analog import AnalogInputObject, AnalogValueObject
    from bacpypes3.local.binary import BinaryInputObject, BinaryValueObject
    from bacpypes3.local.cmd import Commandable
    from bacpypes3.primitivedata import Real

    class CommandableAnalogValueObject(Commandable, AnalogValueObject):
        """Commandable Analog Value Object (mini-device-revisited)."""

    class CommandableBinaryValueObject(Commandable, BinaryValueObject):
        """Commandable Binary Value Object (mini-device-revisited)."""

    args = SimpleArgumentParser().parse_args(argv)
    app = Application.from_args(args)

    # Explicit catalog — no AnalogOutput fall-through (that produced Workbench
    # "Object:Unknown" / Reject INVALID_TAG on writes).
    objects: dict[str, Any] = {}
    ai_n = av_n = bi_n = bv_n = 1

    for row in runtime.bus.snapshot():
        name = str(row["name"])
        kind = row["kind"]
        units = (row["units"] or "").strip() or "noUnits"
        pv = float(row["present_value"])
        desc = str(row["description"] or name)
        binary = bool(row.get("binary"))

        if kind == PointKind.SENSOR.value:
            if binary or name in {"FAN-S"}:
                obj: Any = BinaryInputObject(
                    objectIdentifier=("binaryInput", bi_n),
                    objectName=name,
                    presentValue="active" if pv >= 0.5 else "inactive",
                    statusFlags=[0, 0, 0, 0],
                    description=desc,
                )
                bi_n += 1
            else:
                obj = AnalogInputObject(
                    objectIdentifier=("analogInput", ai_n),
                    objectName=name,
                    presentValue=pv,
                    statusFlags=[0, 0, 0, 0],
                    units=units,
                    description=desc,
                )
                ai_n += 1
        elif binary or name in {"UNIT-ENABLE", "OCC-OVRD"}:
            obj = CommandableBinaryValueObject(
                objectIdentifier=("binaryValue", bv_n),
                objectName=name,
                presentValue="active" if pv >= 0.5 else "inactive",
                statusFlags=[0, 0, 0, 0],
                description=desc,
            )
            bv_n += 1
        else:
            # Writable analogs: ZONE-SP / DEADBAND (HEAT-EFF/COOL-EFF are sensors above).
            obj = CommandableAnalogValueObject(
                objectIdentifier=("analogValue", av_n),
                objectName=name,
                presentValue=pv,
                statusFlags=[0, 0, 0, 0],
                covIncrement=0.1,
                units=units,
                description=desc,
            )
            av_n += 1

        app.add_object(obj)
        objects[name] = obj
        log.info(
            "BACnet object %s %s",
            obj.objectIdentifier,
            name,
        )

    log.info(
        "BACnet twin online with %d objects (mini-device-revisited AV/BV commandables)",
        len(objects),
    )

    def _bacnet_priority(obj: Any) -> int:
        ccp = getattr(obj, "currentCommandPriority", None)
        if ccp is None:
            return 16
        unsigned = getattr(ccp, "unsigned", None)
        if unsigned is None:
            return 16
        try:
            return int(unsigned)
        except (TypeError, ValueError):
            return 16

    def _as_float(raw: Any) -> float:
        if isinstance(raw, str):
            return 1.0 if raw == "active" else 0.0
        return float(raw)

    async def _push_ui_to_bacnet(obj: Any, value: float, priority: int) -> None:
        if isinstance(obj, CommandableBinaryValueObject):
            typed: Any = BinaryPV("active" if value >= 0.5 else "inactive")
        else:
            typed = Real(value)
        await obj.write_property("presentValue", typed, priority=priority)

    async def mirror_loop() -> None:
        """Sensors follow the plant; commandables are client-owned (mini-device rule)."""
        while True:
            try:
                # BACnet commandables -> bus (so HTML / plant see Workbench writes)
                for name, obj in objects.items():
                    state = runtime.bus.get(name)
                    if state.definition.kind is not PointKind.COMMANDABLE:
                        continue
                    value = _as_float(obj.presentValue)
                    prio = _bacnet_priority(obj)
                    win = state.winning_priority()
                    src = state.winning_source()
                    if src == "ui" and win is not None and win < prio:
                        continue
                    if abs(runtime.bus.present(name) - value) > 1e-6:
                        # Clamp away from overwriting UI-8 with relinquish default noise
                        write_prio = 10 if prio >= 16 else min(max(prio, 1), 15)
                        runtime.bus.write(name, value, priority=write_prio, source="bacnet")

                # Bus sensors -> BACnet AIs / BIs only (never touch commandables here)
                for name, obj in objects.items():
                    state = runtime.bus.get(name)
                    if state.definition.kind is not PointKind.SENSOR:
                        continue
                    pv = state.present_value()
                    if isinstance(obj, BinaryInputObject):
                        desired = "active" if pv >= 0.5 else "inactive"
                        if str(obj.presentValue) != desired:
                            obj.presentValue = desired
                    else:
                        if abs(float(obj.presentValue) - pv) > 1e-6:
                            obj.presentValue = float(pv)

                # HTML UI (priority 8) -> BACnet via write_property only
                for name, obj in objects.items():
                    state = runtime.bus.get(name)
                    if state.definition.kind is not PointKind.COMMANDABLE:
                        continue
                    win = state.winning_priority()
                    src = state.winning_source()
                    if win is None or win > 8 or src != "ui":
                        continue
                    pv = state.present_value()
                    if abs(_as_float(obj.presentValue) - pv) > 1e-6 or _bacnet_priority(obj) != win:
                        await _push_ui_to_bacnet(obj, pv, win)
            except Exception:
                log.exception("BACnet mirror loop error")

            await asyncio.sleep(0.5)

    asyncio.create_task(mirror_loop())
    await asyncio.Future()
