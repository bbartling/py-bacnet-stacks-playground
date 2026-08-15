"""Month-to-date billing floor (not yesterday's peak)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class BillingState:
    floor_kw: float = 0.0
    cycle_key: tuple[int, int] | None = None
    ratchet_kw: float = 0.0
    contract_kw: float = 0.0
    floors: dict[tuple[int, int], float] = field(default_factory=dict)

    def billing_floor_kw(self) -> float:
        return max(float(self.floor_kw), float(self.ratchet_kw), float(self.contract_kw))

    def start_of_day(self, day: date | str) -> float:
        d = day if isinstance(day, date) else date.fromisoformat(str(day)[:10])
        key = (int(d.year), int(d.month))
        if self.cycle_key is None:
            self.cycle_key = key
            if key in self.floors:
                self.floor_kw = float(self.floors[key])
        elif key != self.cycle_key:
            self.floors[self.cycle_key] = float(self.floor_kw)
            self.floor_kw = float(self.floors.get(key, max(float(self.ratchet_kw), float(self.contract_kw))))
            self.cycle_key = key
        return self.billing_floor_kw()

    def observe_peak(self, peak_kw: float) -> float:
        self.floor_kw = max(float(self.floor_kw), float(peak_kw))
        if self.cycle_key is not None:
            self.floors[self.cycle_key] = float(self.floor_kw)
        return self.billing_floor_kw()
