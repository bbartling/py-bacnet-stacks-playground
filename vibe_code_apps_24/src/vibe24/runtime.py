"""Runtime: PointBus + Plant + wall-clock ticks."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from .bus import PointBus
from .eplus_plant import CLAIM_SURROGATE
from .plant import SurrogatePlant
from .points import residential_rtu_points
from .thermostat import plant_commands_from_bus

SPEED_MIN = 1.0
SPEED_MAX = 60.0


@dataclass
class TwinRuntime:
    bus: PointBus = field(default_factory=lambda: PointBus(residential_rtu_points()))
    plant: Any = field(default_factory=SurrogatePlant)
    wall_seconds_per_sim_minute: float = 12.0  # ~5x realtime default
    sim_minutes_advanced: int = 0
    last_tick_wall: float = field(default_factory=time.time)
    claim: str = CLAIM_SURROGATE
    paused: bool = False
    _task: asyncio.Task | None = field(default=None, repr=False)
    _wake: asyncio.Event | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        plant_claim = getattr(self.plant, "claim", None)
        if isinstance(plant_claim, str) and plant_claim:
            self.claim = plant_claim
        self.plant.reset(oa_f=self.bus.present("OA-T"), zone_f=self.bus.present("ZONE-T"))
        self._publish_effective_setpoints()
        self._publish_sensors(self.plant.step(0.0, self._plant_commands()))

    def _plant_commands(self) -> dict[str, float]:
        return plant_commands_from_bus(self.bus.commands())

    def _publish_effective_setpoints(self) -> None:
        cmds = self._plant_commands()
        self.bus.set_sensor("HEAT-EFF", float(cmds["HEAT-EFF"]))
        self.bus.set_sensor("COOL-EFF", float(cmds["COOL-EFF"]))

    def _publish_sensors(self, sensors: dict[str, float]) -> None:
        for name, value in sensors.items():
            self.bus.set_sensor(name, value)

    def _wake_ticker(self) -> None:
        if self._wake is not None:
            self._wake.set()

    def tick(self, sim_minutes: float = 1.0) -> dict[str, float]:
        self._publish_effective_setpoints()
        sensors = self.plant.step(float(sim_minutes) / 60.0, self._plant_commands())
        self._publish_sensors(sensors)
        self.sim_minutes_advanced += int(max(1, round(sim_minutes)))
        self.last_tick_wall = time.time()
        return sensors

    def set_speed(self, realtime_factor: float) -> dict:
        factor = float(realtime_factor)
        if factor < SPEED_MIN or factor > SPEED_MAX:
            raise ValueError(f"speed must be between {SPEED_MIN} and {SPEED_MAX}, got {realtime_factor!r}")
        self.wall_seconds_per_sim_minute = 60.0 / factor
        self._wake_ticker()
        return self.sim_clock()

    def set_paused(self, paused: bool) -> dict:
        self.paused = bool(paused)
        self._wake_ticker()
        return self.sim_clock()

    def sim_clock(self) -> dict:
        clock_fn = getattr(self.plant, "sim_clock", None)
        if callable(clock_fn):
            clock = dict(clock_fn())
        else:
            clock = {"month": 7, "day": 15, "hour": 0, "minute": 0, "label": "07/15 00:00"}
        wall = max(float(self.wall_seconds_per_sim_minute), 1e-6)
        clock["realtime_factor"] = round(60.0 / wall, 3)
        clock["wall_seconds_per_sim_minute"] = wall
        clock["sim_minutes_advanced"] = int(self.sim_minutes_advanced)
        clock["paused"] = bool(self.paused)
        return clock

    def status(self) -> dict:
        self._publish_effective_setpoints()
        return {
            "claim": self.claim,
            "sim_minutes_advanced": self.sim_minutes_advanced,
            "wall_seconds_per_sim_minute": self.wall_seconds_per_sim_minute,
            "paused": self.paused,
            "clock": self.sim_clock(),
            "points": self.bus.snapshot(),
        }

    async def run_ticker(self) -> None:
        self._wake = asyncio.Event()
        while True:
            if self.paused:
                self._wake.clear()
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=0.25)
                except TimeoutError:
                    pass
                continue

            period = max(0.05, float(self.wall_seconds_per_sim_minute))
            deadline = time.monotonic() + period
            interrupted = False
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                if self.paused:
                    interrupted = True
                    break
                self._wake.clear()
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=min(0.25, remaining))
                    interrupted = True
                    break
                except TimeoutError:
                    continue
            if not interrupted and not self.paused:
                self.tick(1.0)

    def start_background_ticker(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run_ticker())

    def stop_background_ticker(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None
        self._wake = None
