"""Surrogate plant thermal direction smoke."""

from vibe24.plant import SurrogatePlant


def test_cooling_pulls_zone_down_when_above_setpoint():
    plant = SurrogatePlant(zone_f=78.0, oa_f=95.0)
    before = plant.zone_f
    cmds = {"UNIT-ENABLE": 1.0, "OCC-OVRD": 1.0, "HEAT-EFF": 70.0, "COOL-EFF": 72.0}
    for _ in range(30):
        plant.step(1.0 / 60.0, cmds)
    assert plant.zone_f < before
    assert plant.zone_f < 76.0


def test_heating_pulls_zone_up_when_below_setpoint():
    plant = SurrogatePlant(zone_f=62.0, oa_f=20.0)
    before = plant.zone_f
    cmds = {"UNIT-ENABLE": 1.0, "OCC-OVRD": 1.0, "HEAT-EFF": 70.0, "COOL-EFF": 74.0}
    for _ in range(30):
        plant.step(1.0 / 60.0, cmds)
    assert plant.zone_f > before
    assert plant.zone_f > 64.0


def test_disabled_unit_uses_fan_or_idle_not_full_capacity():
    plant = SurrogatePlant(zone_f=78.0, oa_f=95.0)
    out = plant.step(1.0 / 60.0, {"UNIT-ENABLE": 0.0, "HEAT-EFF": 70.0, "COOL-EFF": 72.0})
    assert out["MODE"] == 0.0
    assert out["RTU-KW"] == 0.0
    assert out["FAN-S"] == 0.0
