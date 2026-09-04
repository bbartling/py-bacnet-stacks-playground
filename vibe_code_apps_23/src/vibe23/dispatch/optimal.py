"""Cyclic LP battery dispatch — PhD-honest bound next to the greedy heuristic."""
from __future__ import annotations

from typing import Sequence

import numpy as np

from ..battery import BatteryParams
from ..residential.constants import DT_HOURS


def cyclic_lp_dispatch(
    facility_kw: Sequence[float],
    prices: Sequence[float],
    params: BatteryParams,
    *,
    dt_hours: float = DT_HOURS,
    throughput_cost_per_kwh: float = 0.05,
    cap_purchased_to_house_peak: bool = True,
) -> dict[str, list[float] | float | str]:
    """Minimize bill + throughput cost subject to cyclic SOC and no export.

    Uses ``scipy.optimize.linprog``. Reports an optimality *bound* for the
    same constraints (continuous LP; simultaneous charge/discharge is weakly
    dominated when throughput is priced).
    """
    from scipy.optimize import linprog

    load = np.asarray(facility_kw, dtype=float)
    price = np.asarray(prices, dtype=float)
    if load.ndim != 1 or price.ndim != 1:
        raise ValueError("facility_kw and prices must be 1-D")
    if len(load) != len(price) or len(load) < 2:
        raise ValueError("facility_kw and prices length mismatch / too short")

    n = len(load)
    dt = float(dt_hours)
    cap = float(params.capacity_kwh)
    s_min = float(params.soc_min) * cap
    s_max = float(params.soc_max) * cap
    house_peak = float(np.max(load))

    # Variables: [c_0..c_{n-1}, d_0..d_{n-1}, S_0..S_{n-1}]
    nc = n
    nd = n
    ns = n
    nvar = nc + nd + ns

    def c_i(t: int) -> int:
        return t

    def d_i(t: int) -> int:
        return nc + t

    def s_i(t: int) -> int:
        return nc + nd + t

    c_obj = np.zeros(nvar)
    for t in range(n):
        # price * (load + c - d) * dt + throughput_cost * (c+d) * dt
        c_obj[c_i(t)] += float(price[t]) * dt + float(throughput_cost_per_kwh) * dt
        c_obj[d_i(t)] += -float(price[t]) * dt + float(throughput_cost_per_kwh) * dt
    # constant price*load*dt ignored

    bounds: list[tuple[float | None, float | None]] = []
    for t in range(n):
        bounds.append((0.0, float(params.max_charge_kw)))
    for t in range(n):
        bounds.append((0.0, float(params.max_discharge_kw)))
    for t in range(n):
        bounds.append((s_min, s_max))

    a_eq = []
    b_eq = []
    # SOC: S_{t+1} - S_t - eta_c*c*dt + d*dt/eta_d = 0  (wrap cyclic)
    for t in range(n):
        row = np.zeros(nvar)
        t_next = (t + 1) % n
        row[s_i(t_next)] += 1.0
        row[s_i(t)] -= 1.0
        row[c_i(t)] -= float(params.eta_c) * dt
        row[d_i(t)] += dt / float(params.eta_d)
        a_eq.append(row)
        b_eq.append(0.0)

    a_ub = []
    b_ub = []
    # purchased = load + c - d >= 0  =>  -c + d <= load
    # purchased <= house_peak (optional) => c - d <= house_peak - load
    for t in range(n):
        row = np.zeros(nvar)
        row[c_i(t)] = -1.0
        row[d_i(t)] = 1.0
        a_ub.append(row)
        b_ub.append(float(load[t]))
        if cap_purchased_to_house_peak:
            row2 = np.zeros(nvar)
            row2[c_i(t)] = 1.0
            row2[d_i(t)] = -1.0
            a_ub.append(row2)
            b_ub.append(house_peak - float(load[t]))

    result = linprog(
        c_obj,
        A_ub=np.asarray(a_ub) if a_ub else None,
        b_ub=np.asarray(b_ub) if b_ub else None,
        A_eq=np.asarray(a_eq),
        b_eq=np.asarray(b_eq),
        bounds=bounds,
        method="highs",
    )
    if not result.success:
        raise RuntimeError(f"cyclic LP failed: {result.message}")

    x = result.x
    charge = x[0:n]
    discharge = x[n : 2 * n]
    energy = x[2 * n : 3 * n]
    purchased = load + charge - discharge
    soc = energy / cap

    bill = float(np.sum(price * purchased * dt))
    throughput_kwh = float(np.sum((charge + discharge) * dt))
    return {
        "purchased_kw": purchased.tolist(),
        "soc": soc.tolist(),
        "charge_kw": charge.tolist(),
        "discharge_kw": discharge.tolist(),
        "final_soc": float(soc[-1]),
        "initial_soc_opt": float(soc[0]),
        "intervals": float(n),
        "dt_hours": dt,
        "mode": "cyclic_lp",
        "bill_usd": bill,
        "throughput_kwh": throughput_kwh,
        "throughput_cost_per_kwh": float(throughput_cost_per_kwh),
        "objective_usd": float(result.fun) + float(np.sum(price * load * dt)),
        "purchased_peak_kw": float(np.max(purchased)),
        "house_peak_kw": house_peak,
        "solver": "scipy.linprog.highs",
    }


def optimality_gap(
    *,
    greedy_bill_usd: float,
    lp_bill_usd: float,
) -> dict[str, float]:
    """Fraction of LP bill savings captured by a heuristic (1.0 = matches LP)."""
    if lp_bill_usd <= 0 and greedy_bill_usd <= 0:
        return {"gap_fraction": 1.0, "greedy_bill_usd": greedy_bill_usd, "lp_bill_usd": lp_bill_usd}
    # Lower bill is better. Capture ratio relative to a no-battery reference is
    # computed by callers; here report greedy/lp bill ratio inverted carefully.
    if greedy_bill_usd <= 0:
        return {"gap_fraction": 1.0, "greedy_bill_usd": greedy_bill_usd, "lp_bill_usd": lp_bill_usd}
    # If LP bill is lower, fraction of LP value = (ref - greedy)/(ref - lp) needs ref.
    # Without ref, report how close greedy bill is to LP bill (1 = equal, <1 if worse).
    if lp_bill_usd <= 0:
        return {"gap_fraction": 0.0, "greedy_bill_usd": greedy_bill_usd, "lp_bill_usd": lp_bill_usd}
    ratio = float(lp_bill_usd / greedy_bill_usd)
    return {
        "bill_ratio_lp_over_greedy": ratio,
        "greedy_bill_usd": float(greedy_bill_usd),
        "lp_bill_usd": float(lp_bill_usd),
        "greedy_minus_lp_usd": float(greedy_bill_usd - lp_bill_usd),
    }
