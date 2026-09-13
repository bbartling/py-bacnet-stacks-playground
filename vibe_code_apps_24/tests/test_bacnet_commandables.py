"""BACnet object typing matches mini-device-revisited (no live bind)."""

import asyncio

from bacpypes3.basetypes import BinaryPV
from bacpypes3.local.analog import AnalogInputObject, AnalogValueObject
from bacpypes3.local.binary import BinaryInputObject, BinaryValueObject
from bacpypes3.local.cmd import Commandable
from bacpypes3.primitivedata import Real

from vibe24.bus import PointKind
from vibe24.runtime import TwinRuntime


class CommandableAnalogValueObject(Commandable, AnalogValueObject):
    pass


class CommandableBinaryValueObject(Commandable, BinaryValueObject):
    pass


def _build_objects_like_device(runtime: TwinRuntime) -> dict:
    objects: dict = {}
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
                obj = BinaryInputObject(
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
        objects[name] = obj
    return objects


def test_no_analog_outputs_and_bv_commandables():
    objs = _build_objects_like_device(TwinRuntime())
    assert isinstance(objs["ZONE-SP"], CommandableAnalogValueObject)
    assert isinstance(objs["DEADBAND"], CommandableAnalogValueObject)
    assert isinstance(objs["HEAT-EFF"], AnalogInputObject)
    assert isinstance(objs["COOL-EFF"], AnalogInputObject)
    assert isinstance(objs["UNIT-ENABLE"], CommandableBinaryValueObject)
    assert isinstance(objs["OCC-OVRD"], CommandableBinaryValueObject)

    def _otype(obj) -> str:
        return str(obj.objectIdentifier[0]).replace("-", "").lower()

    assert _otype(objs["ZONE-SP"]) == "analogvalue"
    assert _otype(objs["HEAT-EFF"]) == "analoginput"
    assert all("analogoutput" not in _otype(o) for o in objs.values())
    assert isinstance(objs["ZONE-T"], AnalogInputObject)
    assert isinstance(objs["FAN-S"], BinaryInputObject)


def test_commandable_write_property_at_priority():
    async def _run() -> None:
        objs = _build_objects_like_device(TwinRuntime())
        zone = objs["ZONE-SP"]
        await zone.write_property("presentValue", Real(68.0), priority=8)
        assert float(zone.presentValue) == 68.0
        assert int(zone.currentCommandPriority.unsigned) == 8

        enable = objs["UNIT-ENABLE"]
        await enable.write_property("presentValue", BinaryPV("inactive"), priority=8)
        assert str(enable.presentValue) == "inactive"

    asyncio.run(_run())
