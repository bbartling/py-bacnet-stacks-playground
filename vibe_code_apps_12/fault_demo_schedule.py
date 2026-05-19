"""
Synthetic temperature schedule for FDD validation (AWS IoT / cloud dashboard).

Inspired by open-fdd-afdd-stack fake_bacnet_devices fault_schedule: sequential
phases that exercise each rule in fdd_rules.py (bounds, flatline, rate/hr, rate/min).

At default Pi cadence (BACnet 2 s, MQTT 10 s) each phase is long enough for
flatline_window=18 and rolling_window=6 to latch on the cloud side.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional


def f_to_c(deg_f: float) -> float:
    return (deg_f - 32.0) * 5.0 / 9.0


@dataclass(frozen=True)
class FaultPhase:
    name: str
    duration_s: float
    """Return target °F at elapsed seconds within this phase (0 .. duration_s)."""
    temp_f_at: Callable[[float], float]


# One full cycle (~50 min). Repeats when loop=True.
PHASES: tuple[FaultPhase, ...] = (
    FaultPhase(
        "baseline",
        300.0,
        lambda _t: 70.0,
    ),
    FaultPhase(
        "flatline",
        600.0,
        lambda _t: 70.0,
    ),
    FaultPhase(
        "out_of_bounds_high",
        600.0,
        lambda _t: 90.0,
    ),
    FaultPhase(
        "out_of_bounds_low",
        600.0,
        lambda _t: 55.0,
    ),
    FaultPhase(
        "rate_spike",
        120.0,
        lambda t: 70.0 if t < 30.0 else 88.0,
    ),
    FaultPhase(
        "rate_ramp",
        180.0,
        lambda t: 70.0 + min(30.0, t * 0.35),
    ),
    FaultPhase(
        "recovery",
        300.0,
        lambda _t: 70.0,
    ),
)


class FaultDemoScheduler:
    """Monotonic clock; yields synthetic °F for BACnet + MQTT (no 1-Wire read)."""

    def __init__(
        self,
        phases: tuple[FaultPhase, ...] = PHASES,
        loop: bool = True,
        log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._phases = phases
        self._loop = loop
        self._log = log or (lambda _m: None)
        self._t0 = time.monotonic()
        self._cycle_s = sum(p.duration_s for p in phases)
        self._last_phase_name: str | None = None

    @property
    def cycle_seconds(self) -> float:
        return self._cycle_s

    def _elapsed_in_cycle(self) -> float:
        elapsed = time.monotonic() - self._t0
        if self._loop and self._cycle_s > 0:
            return elapsed % self._cycle_s
        return min(elapsed, self._cycle_s)

    def _locate(self, elapsed: float) -> tuple[FaultPhase, float]:
        t = 0.0
        for phase in self._phases:
            if elapsed < t + phase.duration_s:
                return phase, elapsed - t
            t += phase.duration_s
        last = self._phases[-1]
        return last, last.duration_s

    def current_deg_f(self) -> float:
        elapsed = self._elapsed_in_cycle()
        phase, phase_t = self._locate(elapsed)
        if phase.name != self._last_phase_name:
            self._last_phase_name = phase.name
            self._log(
                f"FAULT-DEMO phase → {phase.name} "
                f"({phase.duration_s:.0f}s target)"
            )
        return float(phase.temp_f_at(phase_t))

    def current_deg_c(self) -> float:
        return f_to_c(self.current_deg_f())

    def status_line(self) -> str:
        elapsed = self._elapsed_in_cycle()
        phase, phase_t = self._locate(elapsed)
        return (
            f"fault-demo {phase.name} "
            f"{phase_t:.0f}/{phase.duration_s:.0f}s "
            f"cycle {elapsed:.0f}/{self._cycle_s:.0f}s"
        )
