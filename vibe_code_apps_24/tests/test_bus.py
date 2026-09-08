"""PointBus priority array behavior."""

from vibe24.bus import PointBus, PointDef, PointKind


def _cmd_bus() -> PointBus:
    return PointBus(
        [
            PointDef("HEAT-SP", PointKind.COMMANDABLE, "heat", default=70.0),
            PointDef("ZONE-T", PointKind.SENSOR, "zone", default=72.0),
        ]
    )


def test_default_wins_at_priority_16():
    bus = _cmd_bus()
    assert bus.present("HEAT-SP") == 70.0
    assert bus.get("HEAT-SP").winning_priority() == 16
    assert bus.get("HEAT-SP").winning_source() == "default"


def test_ui_priority_8_beats_default():
    bus = _cmd_bus()
    bus.write("HEAT-SP", 68.0, priority=8, source="ui")
    assert bus.present("HEAT-SP") == 68.0
    assert bus.get("HEAT-SP").winning_priority() == 8
    assert bus.get("HEAT-SP").winning_source() == "ui"


def test_priority_1_beats_8():
    bus = _cmd_bus()
    bus.write("HEAT-SP", 68.0, priority=8, source="ui")
    bus.write("HEAT-SP", 65.0, priority=1, source="manual")
    assert bus.present("HEAT-SP") == 65.0
    assert bus.get("HEAT-SP").winning_priority() == 1


def test_relinquish_8_falls_back_to_default():
    bus = _cmd_bus()
    bus.write("HEAT-SP", 68.0, priority=8, source="ui")
    bus.relinquish("HEAT-SP", priority=8)
    assert bus.present("HEAT-SP") == 70.0
    assert bus.get("HEAT-SP").winning_priority() == 16


def test_sensor_not_commandable():
    bus = _cmd_bus()
    try:
        bus.write("ZONE-T", 80.0, priority=8)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    bus.set_sensor("ZONE-T", 74.5)
    assert bus.present("ZONE-T") == 74.5
