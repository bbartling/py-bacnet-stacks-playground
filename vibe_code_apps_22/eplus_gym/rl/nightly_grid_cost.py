"""Cost accounting for nightly grid compute (incremental demand + monthly sums)."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from eplus_gym.mega.tariff_modes import default_tariff_catalog
from eplus_gym.rl.day_ahead_tariff import rate_vector_from_mode_or_fixture
from eplus_gym.rl.reward_v2 import score_day_v2

INTERVAL_H = 0.25


def monthly_demand_total(
    monthly_peaks_kw: Mapping[str, float],
    *,
    demand_rate_usd_per_kw: float,
    ratchet_floor_kw: float = 0.0,
    contract_floor_kw: float = 0.0,
) -> float:
    """Sum independent monthly demand charges (never one peak across months)."""
    total = 0.0
    for peak in monthly_peaks_kw.values():
        billed = max(float(peak), float(ratchet_floor_kw), float(contract_floor_kw))
        total += billed * float(demand_rate_usd_per_kw)
    return float(total)


def total_cost_from_monthly(
    *,
    monthly_energy_usd: Mapping[str, float],
    monthly_demand_usd: Mapping[str, float],
) -> float:
    return float(sum(monthly_energy_usd.values()) + sum(monthly_demand_usd.values()))


def score_candidate_day(
    *,
    day: str,
    candidate_facility_kw: Sequence[float],
    candidate_zone_temps_f: Mapping[str, Sequence[float]],
    baseline_facility_kw: Sequence[float],
    baseline_zone_temps_f: Mapping[str, Sequence[float]],
    candidate_schedules: Mapping[str, Sequence[float]],
    previous_schedules: Mapping[str, Sequence[float]] | None,
    mtd_peak_kw: float,
    baseline_mtd_peak_kw: float,
    tariff_mode: str = "FLAT_PLUS_DEMAND",
    fixtures_dir: Any | None = None,
) -> dict[str, Any]:
    """Score one target day; selection uses total_modeled_objective (not train reward)."""
    rates, demand_rate, _meta = rate_vector_from_mode_or_fixture(
        tariff_mode, fixtures_dir=fixtures_dir
    )
    res = score_day_v2(
        day=day,
        candidate_facility_kw=list(candidate_facility_kw),
        candidate_zone_temps_f=candidate_zone_temps_f,
        baseline_facility_kw=list(baseline_facility_kw),
        baseline_zone_temps_f=baseline_zone_temps_f,
        candidate_schedules=candidate_schedules,
        previous_schedules=previous_schedules,
        mtd_peak_kw=float(mtd_peak_kw),
        baseline_mtd_peak_kw=float(baseline_mtd_peak_kw),
        rate_kwh=rates,
        demand_rate=float(demand_rate),
    )
    energy = float(res.candidate["energy_cost"])
    demand_inc = float(res.candidate["demand_increment"])
    ready = bool(res.readiness.get("readiness_ok"))
    return {
        "day": day,
        "tariff_mode": tariff_mode,
        "energy_charge_usd": energy,
        "incremental_demand_charge_usd": demand_inc,
        "total_modeled_objective": energy + demand_inc,
        "readiness_ok": ready,
        "readiness_checked": bool(res.readiness.get("checked")),
        "occupied_comfort_degree_hours": float(res.extras.get("occupied_zone_DH") or 0.0),
        "schedule_movement": float(res.extras.get("within_day_schedule_movement") or 0.0),
        "display_paycheck_usd": float(res.display_paycheck_usd),
        "training_reward": float(res.training_reward),
        "peak_kw": float(res.candidate["day_peak_kw"]),
        "daily_kwh": float(sum(float(x) for x in candidate_facility_kw) * INTERVAL_H),
        "fully_ready_eligible": ready,
    }


def default_flat_rates() -> tuple[float, float]:
    cat = default_tariff_catalog()["flat_illustrative"]
    return float(cat.energy_rate_per_kwh), float(cat.demand_rate_per_kw)
