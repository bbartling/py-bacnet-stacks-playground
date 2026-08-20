"""Rescore a committed multi-day utility table with independent MTD peaks.

Illustrative accounting only. Not a billed utility invoice.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

ENERGY_RATE = 0.12
DEMAND_RATE = 15.0
BASELINE_ARM = "continuous_70"


def rescore_utility_table_mtd(
    table: Sequence[Mapping[str, Any]],
    *,
    energy_rate: float = ENERGY_RATE,
    demand_rate: float = DEMAND_RATE,
    baseline_arm: str = BASELINE_ARM,
) -> dict[str, Any]:
    """Carry MTD peak per arm. A day below the existing MTD peak has $0 demand increment."""
    if not table:
        raise ValueError("empty utility table")
    arm_names = list(table[0]["arms"].keys())
    mtd = {name: 0.0 for name in arm_names}
    days_out: list[dict[str, Any]] = []
    totals = {
        name: {"energy_cost": 0.0, "demand_increment": 0.0, "three_day_total_usd": 0.0, "final_peak_kw": 0.0}
        for name in arm_names
    }
    for row in table:
        day = str(row["day"])
        row_arms: dict[str, Any] = {}
        for name in arm_names:
            arm = row["arms"][name]
            peak = float(arm["day_peak_kw"])
            kwh = float(arm["daily_kwh"])
            energy = float(arm.get("energy_cost", energy_rate * kwh))
            opening = float(mtd[name])
            demand = float(demand_rate) * max(0.0, peak - opening)
            closing = max(opening, peak)
            mtd[name] = closing
            daily = energy + demand
            row_arms[name] = {
                "opening_mtd_peak_kw": opening,
                "day_peak_kw": peak,
                "daily_kwh": kwh,
                "energy_cost": energy,
                "demand_increment": demand,
                "daily_cost": daily,
                "closing_mtd_peak_kw": closing,
            }
            totals[name]["energy_cost"] += energy
            totals[name]["demand_increment"] += demand
            totals[name]["three_day_total_usd"] += daily
            totals[name]["final_peak_kw"] = closing
        base_cost = row_arms[baseline_arm]["daily_cost"]
        for name in arm_names:
            row_arms[name]["savings_vs_continuous"] = base_cost - row_arms[name]["daily_cost"]
        days_out.append({"day": day, "arms": row_arms})
    base_total = totals[baseline_arm]["three_day_total_usd"]
    for name in arm_names:
        totals[name]["savings_vs_continuous_usd"] = base_total - totals[name]["three_day_total_usd"]
    return {
        "illustrative_not_billed": True,
        "energy_rate_per_kwh": float(energy_rate),
        "demand_rate_per_kw": float(demand_rate),
        "days": days_out,
        "totals": totals,
    }
