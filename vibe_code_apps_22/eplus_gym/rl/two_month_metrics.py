"""Physical trajectory metrics for two-month frozen-policy replay."""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

from eplus_gym.control_v2 import school_windows
from eplus_gym.rl.reward_v2 import readiness_all_six
from eplus_gym.rl.two_month_calendar import month_key, scored_days
from eplus_gym.rl.two_month_rolling import rolling_max_mean

STRATEGY_LABELS = {
    "a04_native_sch_htgsp": "A04_NATIVE_CALIBRATION_REFERENCE",
    "observed_bas_incumbent_v2": "OBSERVED_BAS_INCUMBENT_V2_HISTORICAL",
    "continuous_68_heat_sensitivity": "CONTINUOUS_DUALSP_68_74_SENSITIVITY_UNVERIFIED",
    "frozen_ppo_flat_seed0": "POLICY_CANDIDATE_FROZEN_PPO_FLAT",
    "frozen_dqn_tou_seed1": "POLICY_CANDIDATE_FROZEN_DQN_TOU",
    "grid_flat_discrete_42": "POLICY_CANDIDATE_GRID_FLAT_DISCRETE_42",
    "grid_tou_discrete_43": "POLICY_CANDIDATE_GRID_TOU_DISCRETE_43",
}


def _day_category(day: str) -> str:
    win = school_windows(day)
    d = date.fromisoformat(day[:10])
    if not win.get("school_occupied"):
        return "non_school"
    # crude cold proxy: weekday in Dec/Jan with low OAT not available here — use month heuristic
    if d.month == 12 and d.day >= 15:
        return "cold_school"
    if d.month == 1 and d.day <= 15:
        return "cold_school"
    return "mild_school"


def aggregate_monthly_physical(
    *,
    strategy: str,
    facility_kw: Sequence[float],
    daily_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    days = scored_days()
    if len(facility_kw) != len(days) * 96:
        raise ValueError(f"{strategy}: facility_kw length mismatch")
    by_month: dict[str, list[str]] = {}
    for d in days:
        by_month.setdefault(month_key(d), []).append(d)
    out: list[dict[str, Any]] = []
    for period in ("2025-12", "2026-01", "two_month"):
        if period == "two_month":
            idx_days = days
        else:
            idx_days = by_month[period]
        intervals: list[float] = []
        for d in idx_days:
            i0 = days.index(d) * 96
            intervals.extend([float(x) for x in facility_kw[i0 : i0 + 96]])
        daily_subset = [r for r in daily_rows if str(r["day"]) in idx_days]
        peak = float(max(intervals)) if intervals else 0.0
        peak_day_row = max(daily_subset, key=lambda r: float(r["peak_kw"])) if daily_subset else {}
        out.append(
            {
                "strategy": strategy,
                "public_label": STRATEGY_LABELS.get(strategy, strategy),
                "period": period,
                "total_kwh": float(sum(intervals) * 0.25),
                "peak_15min_kw": peak,
                "peak_30min_mean_kw": rolling_max_mean(intervals, 2),
                "peak_60min_mean_kw": rolling_max_mean(intervals, 4),
                "mean_daily_kwh": float(sum(float(r["daily_kwh"]) for r in daily_subset) / max(len(daily_subset), 1)),
                "mean_daily_peak_kw": float(sum(float(r["peak_kw"]) for r in daily_subset) / max(len(daily_subset), 1)),
                "peak_day": peak_day_row.get("day"),
                "n_days": len(idx_days),
                "n_intervals": len(intervals),
            }
        )
    return out


def build_daily_metrics_table(results: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy, payload in results.items():
        for d in payload.get("daily") or []:
            rows.append(
                {
                    "strategy": strategy,
                    "public_label": STRATEGY_LABELS.get(strategy, strategy),
                    "day": d["day"],
                    "month": month_key(str(d["day"])),
                    "daily_kwh": round(float(d["daily_kwh"]), 4),
                    "peak_kw": round(float(d["peak_kw"]), 4),
                    "peak_30min_mean_kw": round(float(d.get("peak_30min_mean_kw") or 0), 4),
                    "peak_60min_mean_kw": round(float(d.get("peak_60min_mean_kw") or 0), 4),
                    "readiness_ok": d.get("readiness_ok"),
                    "day_category": _day_category(str(d["day"])),
                    "schedule_fingerprint": d.get("schedule_fingerprint"),
                    "trajectory_hash": d.get("trajectory_hash"),
                }
            )
    return rows


def compare_vs_continuous_68(
    results: Mapping[str, Mapping[str, Any]],
    *,
    reference: str = "continuous_68_heat_sensitivity",
) -> dict[str, Any]:
    ref = results.get(reference)
    if not ref:
        return {"reference": reference, "comparisons": []}
    ref_daily = {str(r["day"]): r for r in ref.get("daily") or []}
    out = []
    for strategy, payload in results.items():
        if strategy == reference:
            continue
        lower_peak = lower_kwh = both = 0
        for d in payload.get("daily") or []:
            day = str(d["day"])
            r0 = ref_daily.get(day)
            if not r0:
                continue
            lp = float(d["peak_kw"]) < float(r0["peak_kw"])
            lk = float(d["daily_kwh"]) < float(r0["daily_kwh"])
            lower_peak += int(lp)
            lower_kwh += int(lk)
            both += int(lp and lk)
        out.append(
            {
                "strategy": strategy,
                "days_lower_peak": lower_peak,
                "days_lower_kwh": lower_kwh,
                "days_both": both,
                "n_days": len(payload.get("daily") or []),
            }
        )
    return {"reference": reference, "comparisons": out}


def build_quality_ledger(results: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy, payload in results.items():
        for d in payload.get("daily") or []:
            zones = d.get("zone_temps_series_f") or {}
            ready = readiness_all_six(zones, day=str(d["day"])) if zones else {"readiness_ok": None}
            rows.append(
                {
                    "strategy": strategy,
                    "day": d["day"],
                    "readiness_ok": ready.get("readiness_ok"),
                    "degree_violation": ready.get("degree_violation"),
                    "school_day": ready.get("school_day"),
                    "appendix_only": True,
                    "headline_eligible": bool(ready.get("readiness_ok") is not False),
                }
            )
    return rows


def build_decision_table(results: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """kWh/peak only — no dollars."""
    rows = []
    for strategy, payload in results.items():
        phys = aggregate_monthly_physical(
            strategy=strategy,
            facility_kw=payload["facility_kw"],
            daily_rows=payload.get("daily") or [],
        )
        two = next(r for r in phys if r["period"] == "two_month")
        rows.append(
            {
                "strategy": strategy,
                "public_label": STRATEGY_LABELS.get(strategy, strategy),
                "two_month_kwh": round(two["total_kwh"], 2),
                "two_month_peak_kw": round(two["peak_15min_kw"], 2),
                "dec_kwh": round(next(r for r in phys if r["period"] == "2025-12")["total_kwh"], 2),
                "dec_peak_kw": round(next(r for r in phys if r["period"] == "2025-12")["peak_15min_kw"], 2),
                "jan_kwh": round(next(r for r in phys if r["period"] == "2026-01")["total_kwh"], 2),
                "jan_peak_kw": round(next(r for r in phys if r["period"] == "2026-01")["peak_15min_kw"], 2),
            }
        )
    return rows
