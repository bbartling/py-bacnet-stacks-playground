"""Runtime: PointBus + Plant + wall-clock ticks."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from .bus import PointBus
from .plant import SurrogatePlant
from .points import residential_rtu_points


@dataclass
class TwinRuntime:
    bus: PointBus = field(default_factory=lambda: PointBus(residential_rtu_points()))
    plant: SurrogatePlant = field(default_factory=SurrogatePlant)
    wall_seconds_per_sim_minute: float = 1.0
    sim_minutes_advanced: int = 0
    last_tick_wall: float = field(default_factory=time.time)
    _task: asyncio.Task | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.plant.reset(oa_f=self.bus.present("OA-T"), zone_f=self.bus.present("ZONE-T"))
        self._publish_sensors(self.plant.step(0.0, self.bus.commands()))

    def _publish_sensors(self, sensors: dict[str, float]) -> None:
        for name, value in sensors.items():
            self.bus.set_sensor(name, value)

    def tick(self, sim_minutes: float = 1.0) -> dict[str, float]:
        sensors = self.plant.step(float(sim_minutes) / 60.0, self.bus.commands())
        self._publish_sensors(sensors)
        self.sim_minutes_advanced += int(max(1, round(sim_minutes)))
        self.last_tick_wall = time.time()
        return sensors

    def status(self) -> dict:
        return {
            "claim": "SURROGATE_PLANT_V1",
            "sim_minutes_advanced": self.sim_minutes_advanced,
            "wall_seconds_per_sim_minute": self.wall_seconds_per_sim_minute,
            "points": self.bus.snapshot(),
        }

    async def run_ticker(self) -> None:
        while True:
            await asyncio.sleep(max(0.05, float(self.wall_seconds_per_sim_minute)))
            self.tick(1.0)

    def start_background_ticker(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run_ticker())

    def stop_background_ticker(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None
