"""Single-zone thermostat: one writable SP + deadband → effective heat/cool."""
from __future__ import annotations

MIN_DEADBAND_F = 0.5
DEFAULT_ZONE_SP_F = 72.0
DEFAULT_DEADBAND_F = 2.0


def effective_heat_cool(
    zone_sp_f: float,
    deadband_f: float = DEFAULT_DEADBAND_F,
) -> tuple[float, float]:
    """Return (heat_eff, cool_eff) from center setpoint and full deadband width.

    Real-thermostat style: heat = SP − DB/2, cool = SP + DB/2.
    Deadband is clamped to at least MIN_DEADBAND_F.
    """
    sp = float(zone_sp_f)
    db = max(MIN_DEADBAND_F, float(deadband_f))
    half = db / 2.0
    return sp - half, sp + half


def plant_commands_from_bus(commands: dict[str, float]) -> dict[str, float]:
    """Map bus commands to plant inputs (adds derived HEAT-EFF / COOL-EFF keys)."""
    out = dict(commands)
    zone = float(out.get("ZONE-SP", DEFAULT_ZONE_SP_F))
    db = float(out.get("DEADBAND", DEFAULT_DEADBAND_F))
    heat, cool = effective_heat_cool(zone, db)
    out["HEAT-EFF"] = heat
    out["COOL-EFF"] = cool
    # Back-compat aliases used inside plant control logic.
    out["HEAT-SP"] = heat
    out["COOL-SP"] = cool
    return out
