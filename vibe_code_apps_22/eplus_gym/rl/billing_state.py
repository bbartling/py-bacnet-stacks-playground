"""Month-to-date billing floor (not yesterday's peak)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class BillingState:
    floor_kw: float = 0.0
    cycle_month: int | None = None
    ratchet_kw: float = 0.0
    contract_kw: float = 0.0

    def billing_floor_kw(self) -> float:
        return max(float(self.floor_kw), float(self.ratchet_kw), float(self.contract_kw))

    def start_of_day(self, day: date | str) -> float:
        d = day if isinstance(day, date) else date.fromisoformat(str(day)[:10])
        if self.cycle_month is None:
            self.cycle_month = int(d.month)
        elif int(d.month) != int(self.cycle_month):
            self.floor_kw = max(float(self.ratchet_kw), float(self.contract_kw))
            self.cycle_month = int(d.month)
        return self.billing_floor_kw()

    def observe_peak(self, peak_kw: float) -> float:
        self.floor_kw = max(float(self.floor_kw), float(peak_kw))
        return self.billing_floor_kw()
