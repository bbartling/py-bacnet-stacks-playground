"""Single-zone thermostat helpers."""

from vibe24.thermostat import effective_heat_cool, plant_commands_from_bus


def test_effective_heat_cool_symmetric():
    heat, cool = effective_heat_cool(72.0, 2.0)
    assert heat == 71.0
    assert cool == 73.0


def test_deadband_floor():
    heat, cool = effective_heat_cool(70.0, 0.1)
    assert cool - heat == 0.5


def test_plant_commands_inject_eff():
    out = plant_commands_from_bus({"ZONE-SP": 74.0, "DEADBAND": 4.0, "UNIT-ENABLE": 1.0})
    assert out["HEAT-EFF"] == 72.0
    assert out["COOL-EFF"] == 76.0
    assert out["HEAT-SP"] == 72.0
    assert out["COOL-SP"] == 76.0
