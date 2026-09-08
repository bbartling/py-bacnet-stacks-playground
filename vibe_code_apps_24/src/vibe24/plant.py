"""Surrogate residential heat-pump / zone plant (SURROGATE_PLANT_V1)."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class SurrogatePlant:
    """First-order zone + simple RTU capacity curve.

    Not EnergyPlus. Tuned for demo dynamics: writes change commands instantly;
    zone temperature moves over successive ``step`` calls.
    """

    zone_f: float = 72.0
    oa_f: float = 85.0
    # Effective thermal time constant ~45 minutes.
    tau_hours: float = 0.75
    ua_kw_per_f: float = 0.18
    heat_cap_kw: float = 12.0
    cool_cap_kw: float = 14.0
    heat_cop: float = 2.8
    cool_cop: float = 3.5
    fan_kw: float = 0.45
    deadband_f: float = 0.5
    sim_minute: int = 0

    def reset(self, *, oa_f: float, zone_f: float) -> None:
        self.oa_f = float(oa_f)
        self.zone_f = float(zone_f)
        self.sim_minute = 0

    def step(self, dt_hours: float, commands: dict[str, float]) -> dict[str, float]:
        dt = max(float(dt_hours), 1e-6)
        enable = float(commands.get("UNIT-ENABLE", 1.0)) >= 0.5
        occ = float(commands.get("OCC-OVRD", 1.0)) >= 0.5
        heat_sp = float(commands.get("HEAT-SP", 71.0))
        cool_sp = float(commands.get("COOL-SP", 73.0))
        if heat_sp > cool_sp - 1.0:
            cool_sp = heat_sp + 2.0

        # Mild diurnal OA drift for “looks alive” without weather file.
        self.sim_minute = (self.sim_minute + max(1, int(round(dt * 60.0)))) % (24 * 60)
        hour = self.sim_minute / 60.0
        self.oa_f = 78.0 + 12.0 * math.sin((hour - 14.0) / 24.0 * 2.0 * math.pi)

        load_kw = self.ua_kw_per_f * (self.oa_f - self.zone_f)
        if occ:
            load_kw += 0.6  # internal gains

        mode = 0
        thermal_kw = 0.0
        elec_kw = 0.0
        fan = 0.0

        if enable:
            if self.zone_f < heat_sp - self.deadband_f:
                mode = 1
                thermal_kw = self.heat_cap_kw
                elec_kw = thermal_kw / max(self.heat_cop, 0.1) + self.fan_kw
                fan = 1.0
            elif self.zone_f > cool_sp + self.deadband_f:
                mode = 2
                thermal_kw = -self.cool_cap_kw
                elec_kw = self.cool_cap_kw / max(self.cool_cop, 0.1) + self.fan_kw
                fan = 1.0
            elif abs(load_kw) > 0.2:
                mode = 3
                elec_kw = self.fan_kw
                fan = 1.0

        # Energy balance on zone air node (lumped).
        net_kw = thermal_kw - load_kw
        # 1 kW · h ≈ 3412 Btu; ~3500 ft² house air mass proxy via tau.
        dT = (net_kw / max(self.ua_kw_per_f * self.tau_hours, 1e-3)) * dt
        self.zone_f = float(self.zone_f + dT)

        return {
            "ZONE-T": self.zone_f,
            "OA-T": self.oa_f,
            "RTU-KW": elec_kw,
            "FAN-S": fan,
            "MODE": float(mode),
        }
