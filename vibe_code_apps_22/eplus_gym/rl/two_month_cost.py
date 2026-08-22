"""Illustrative tariff re-scoring for two-month replay (flat and TOU separate)."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from eplus_gym.mega.tariff_modes import default_tariff_catalog
from eplus_gym.rl.multiday_env import trajectory_hash
from eplus_gym.rl.two_month_calendar import month_key, scored_days
from eplus_gym.rl.two_month_metrics import STRATEGY_LABELS
from eplus_gym.rl.two_month_provenance import NOT_AVAILABLE

INTERVAL_H = 0.25


def _month_intervals(facility_kw: Sequence[float], month: str) -> list[float]:
    days = scored_days()
    out: list[float] = []
    for d in days:
        if month_key(d) != month:
            continue
        i0 = days.index(d) * 96
        out.extend([float(x) for x in facility_kw[i0 : i0 + 96]])
    return out


def score_flat_plus_demand(
    facility_kw: Sequence[float],
    *,
    ratchet_floor_kw: float = 0.0,
    contract_floor_kw: float = 0.0,
) -> list[dict[str, Any]]:
    cat = default_tariff_catalog()["flat_illustrative"]
    e_rate = float(cat.energy_rate_per_kwh)
    d_rate = float(cat.demand_rate_per_kw)
    rows = []
    for period in ("2025-12", "2026-01", "two_month"):
        if period == "two_month":
            intervals = [float(x) for x in facility_kw]
        else:
            intervals = _month_intervals(facility_kw, period)
        kwh = sum(intervals) * INTERVAL_H
        peak = max(intervals) if intervals else 0.0
        billed_kw = max(peak, ratchet_floor_kw, contract_floor_kw)
        energy_usd = kwh * e_rate
        demand_usd = billed_kw * d_rate
        rows.append(
            {
                "period": period,
                "total_kwh": round(kwh, 4),
                "peak_15min_kw": round(peak, 4),
                "billed_demand_kw": round(billed_kw, 4),
                "energy_charge_usd": round(energy_usd, 2),
                "demand_charge_usd": round(demand_usd, 2),
                "total_usd": round(energy_usd + demand_usd, 2),
                "tariff_mode": "ILLUSTRATIVE_FLAT_PLUS_DEMAND",
            }
        )
    return rows


def score_tou_plus_demand(
    facility_kw: Sequence[float],
    *,
    ratchet_floor_kw: float = 0.0,
    contract_floor_kw: float = 0.0,
) -> list[dict[str, Any]]:
    cat = default_tariff_catalog()["tou_evening_peak_illustrative"]
    qtr = cat.quarter_hour_prices()
    d_rate = float(cat.demand_rate_per_kw)
    rows = []
    for period in ("2025-12", "2026-01", "two_month"):
        if period == "two_month":
            intervals = [float(x) for x in facility_kw]
        else:
            intervals = _month_intervals(facility_kw, period)
        kwh = sum(intervals) * INTERVAL_H
        peak = max(intervals) if intervals else 0.0
        billed_kw = max(peak, ratchet_floor_kw, contract_floor_kw)
        energy_usd = sum(float(kw) * INTERVAL_H * float(qtr[i % 96]) for i, kw in enumerate(intervals))
        demand_usd = billed_kw * d_rate
        rows.append(
            {
                "period": period,
                "total_kwh": round(kwh, 4),
                "peak_15min_kw": round(peak, 4),
                "billed_demand_kw": round(billed_kw, 4),
                "energy_charge_usd": round(energy_usd, 2),
                "demand_charge_usd": round(demand_usd, 2),
                "total_usd": round(energy_usd + demand_usd, 2),
                "tariff_mode": "ILLUSTRATIVE_TOU_PLUS_DEMAND",
            }
        )
    return rows


def build_flat_cost_table(
    results: Mapping[str, Mapping[str, Any]],
    *,
    utility_evidence: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if utility_evidence:
        for period_key, label in (("dec_2025", "2025-12"), ("jan_2026", "2026-01")):
            blob = utility_evidence[period_key]
            rows.append(
                {
                    "strategy": "actual_utility_cs351075",
                    "public_label": "ACTUAL_UTILITY_BILL",
                    "period": label,
                    "total_kwh": blob["kwh"],
                    "peak_15min_kw": blob["billed_demand_kw"],
                    "energy_charge_usd": blob["actual_energy_charge_usd"],
                    "demand_charge_usd": blob["actual_demand_charge_usd"],
                    "total_usd": blob["actual_total_bill_usd"],
                    "tariff_mode": "ACTUAL_UTILITY",
                    "ranking_eligible": False,
                }
            )
    for strategy, payload in results.items():
        scored = score_flat_plus_demand(payload["facility_kw"])
        th = payload.get("trajectory_hash") or trajectory_hash(payload)
        for s in scored:
            rows.append(
                {
                    "strategy": strategy,
                    "public_label": STRATEGY_LABELS.get(strategy, strategy),
                    "trajectory_hash": th,
                    "ranking_eligible": True,
                    **s,
                }
            )
    return rows


def build_tou_cost_table(
    results: Mapping[str, Mapping[str, Any]],
    *,
    utility_evidence: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if utility_evidence:
        for period_key, label in (("dec_2025", "2025-12"), ("jan_2026", "2026-01")):
            blob = utility_evidence[period_key]
            rows.append(
                {
                    "strategy": "actual_utility_cs351075",
                    "public_label": "ACTUAL_UTILITY_BILL",
                    "period": label,
                    "total_kwh": blob["kwh"],
                    "peak_15min_kw": blob["billed_demand_kw"],
                    "energy_charge_usd": NOT_AVAILABLE,
                    "demand_charge_usd": NOT_AVAILABLE,
                    "total_usd": blob["actual_total_bill_usd"],
                    "tariff_mode": "ACTUAL_UTILITY",
                    "ranking_eligible": False,
                }
            )
    for strategy, payload in results.items():
        scored = score_tou_plus_demand(payload["facility_kw"])
        th = payload.get("trajectory_hash") or trajectory_hash(payload)
        for s in scored:
            rows.append(
                {
                    "strategy": strategy,
                    "public_label": STRATEGY_LABELS.get(strategy, strategy),
                    "trajectory_hash": th,
                    "ranking_eligible": True,
                    **s,
                }
            )
    return rows


def rank_strategies(
    cost_rows: Sequence[Mapping[str, Any]],
    *,
    period: str = "two_month",
    objective: str = "total_usd",
) -> list[dict[str, Any]]:
    """Rank modeled strategies only — never merge flat vs TOU or actual bills."""
    eligible = [
        r
        for r in cost_rows
        if r.get("ranking_eligible") is True and str(r.get("period")) == period and isinstance(r.get(objective), (int, float))
    ]
    return sorted(eligible, key=lambda r: float(r[objective]))


def verify_rescore_identity(payload_a: Mapping[str, Any], payload_b: Mapping[str, Any]) -> bool:
    ha = trajectory_hash(payload_a)
    hb = trajectory_hash(payload_b)
    if ha != hb:
        return False
    fa = score_flat_plus_demand(payload_a["facility_kw"])
    fb = score_flat_plus_demand(payload_b["facility_kw"])
    return fa == fb
