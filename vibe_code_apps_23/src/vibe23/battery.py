"""Simple behind-the-meter battery dispatch for residential DSM demos."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, Sequence

import numpy as np

from .residential.constants import DT_HOURS, INTERVALS_PER_DAY

DispatchMode = Literal["peak_shave", "price_arbitrage", "battery_only"]


@dataclass(frozen=True)
class BatteryParams:
    capacity_kwh: float
    max_charge_kw: float
    max_discharge_kw: float
    eta_c: float = 0.95
    eta_d: float = 0.95
    soc_min: float = 0.1
    soc_max: float = 0.95
    initial_soc: float = 0.5

    def __post_init__(self) -> None:
        if self.capacity_kwh <= 0:
            raise ValueError("capacity_kwh must be positive")
        if self.max_charge_kw < 0 or self.max_discharge_kw < 0:
            raise ValueError("power limits must be non-negative")
        if not 0 < self.eta_c <= 1 or not 0 < self.eta_d <= 1:
            raise ValueError("efficiencies must be in (0, 1]")
        if not 0 <= self.soc_min < self.soc_max <= 1:
            raise ValueError("invalid SOC bounds")
        if not self.soc_min <= self.initial_soc <= self.soc_max:
            raise ValueError("initial_soc outside bounds")

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def simulate_dispatch(
    facility_kw: Sequence[float],
    prices: Sequence[float],
    params: BatteryParams,
    mode: DispatchMode = "price_arbitrage",
    *,
    dt_hours: float = DT_HOURS,
    cap_purchased_to_house_peak: bool = True,
) -> dict[str, list[float] | float]:
    """Greedy battery dispatch on purchased-grid load.

    Cannot charge and discharge in the same interval. SOC bounds are enforced.
    Thermal flexibility is assumed already reflected in ``facility_kw``.

    This is a heuristic — compare against ``vibe23.dispatch.cyclic_lp_dispatch``
    for an optimality gap. When ``cap_purchased_to_house_peak`` is True, charging
    cannot create a purchased peak above the house facility peak.
    """

    load = np.asarray(facility_kw, dtype=float)
    price = np.asarray(prices, dtype=float)
    if load.ndim != 1 or price.ndim != 1:
        raise ValueError("facility_kw and prices must be 1-D")
    if len(load) != len(price):
        raise ValueError("facility_kw and prices length mismatch")
    if len(load) < 1:
        raise ValueError("empty series")

    n = len(load)
    soc = float(params.initial_soc)
    energy_cap = float(params.capacity_kwh)
    purchased = np.zeros(n, dtype=float)
    charge = np.zeros(n, dtype=float)
    discharge = np.zeros(n, dtype=float)
    soc_series = np.zeros(n, dtype=float)

    mean_price = float(np.mean(price))
    peak_threshold = float(np.quantile(load, 0.8)) if mode == "peak_shave" else None
    median_load = float(np.median(load))
    house_peak = float(np.max(load))

    for i in range(n):
        kw = float(load[i])
        p = float(price[i])
        room_to_charge = max(0.0, (params.soc_max - soc) * energy_cap / params.eta_c / dt_hours)
        room_to_discharge = max(0.0, (soc - params.soc_min) * energy_cap * params.eta_d / dt_hours)
        max_c = min(params.max_charge_kw, room_to_charge)
        max_d = min(params.max_discharge_kw, room_to_discharge)
        if cap_purchased_to_house_peak:
            max_c = min(max_c, max(0.0, house_peak - kw))

        do_charge = False
        do_discharge = False
        c_kw = 0.0
        d_kw = 0.0
        if mode in {"price_arbitrage", "battery_only"}:
            if p < mean_price and max_c > 0:
                do_charge = True
            elif p > mean_price and max_d > 0:
                do_discharge = True
        elif mode == "peak_shave":
            assert peak_threshold is not None
            if kw >= peak_threshold and max_d > 0:
                do_discharge = True
            elif kw <= median_load and max_c > 0:
                # Recharge when at/below median load (old 0.5×P80 trigger was unreachable
                # under high baseload floors).
                do_charge = True

        if do_charge and not do_discharge:
            c_kw = max_c
            soc = min(params.soc_max, soc + (c_kw * dt_hours * params.eta_c) / energy_cap)
        elif do_discharge and not do_charge:
            if mode == "peak_shave" and peak_threshold is not None:
                target = max(0.0, peak_threshold * 0.95)
                d_kw = min(max_d, max(0.0, kw - target))
                if d_kw <= 0 and max_d > 0:
                    d_kw = min(max_d, kw)
            else:
                d_kw = min(max_d, kw)  # do not export
            soc = max(params.soc_min, soc - (d_kw * dt_hours / params.eta_d) / energy_cap)
        charge[i] = c_kw
        discharge[i] = d_kw
        purchased[i] = max(0.0, kw + c_kw - d_kw)
        soc_series[i] = soc

    return {
        "purchased_kw": purchased.tolist(),
        "soc": soc_series.tolist(),
        "charge_kw": charge.tolist(),
        "discharge_kw": discharge.tolist(),
        "final_soc": float(soc_series[-1]),
        "intervals": float(n),
        "dt_hours": float(dt_hours),
        "mode": mode,
        "nominal_intervals_per_day": float(INTERVALS_PER_DAY),
        "purchased_peak_kw": float(np.max(purchased)),
        "house_peak_kw": house_peak,
        "cap_purchased_to_house_peak": bool(cap_purchased_to_house_peak),
    }
