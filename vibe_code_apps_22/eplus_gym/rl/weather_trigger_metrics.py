"""Metrics, peak-first sensitivity, and strategy summary tables for weather-trigger experiment."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from eplus_gym.eplus_err import scored_runtime_w2a_count
from eplus_gym.rl.two_month_cost import score_flat_plus_demand, score_tou_plus_demand
from eplus_gym.rl.two_month_metrics import aggregate_monthly_physical
from eplus_gym.rl.weather_trigger_select import load_weather_trigger_contract

STRATEGY_LABELS = {
    "ALWAYS_GRID_114": "ALWAYS_GRID_114",
    "ALWAYS_GRID_42": "ALWAYS_GRID_42",
    "ALWAYS_GRID_43": "ALWAYS_GRID_43",
    "ALWAYS_CONTINUOUS_68_74": "ALWAYS_CONTINUOUS_68_74",
    "COLD_TRIGGER_10F": "COLD_TRIGGER_10F",
    "COLD_TRIGGER_20F": "COLD_TRIGGER_20F",
    "COLD_TRIGGER_30F": "COLD_TRIGGER_30F",
    "COLD_TRIGGER_20F_4H": "COLD_TRIGGER_20F_4H",
    "COLD_TRIGGER_20F_8H": "COLD_TRIGGER_20F_8H",
    "a04_native_sch_htgsp": "A04_NATIVE_CALIBRATION_REFERENCE",
    "observed_bas_incumbent_v2": "OBSERVED_BAS_INCUMBENT_V2_HISTORICAL",
    "continuous_68_heat_sensitivity": "CONTINUOUS_DUALSP_68_74_SENSITIVITY_UNVERIFIED",
    "frozen_ppo_flat_seed0": "POLICY_CANDIDATE_FROZEN_PPO_FLAT",
    "frozen_dqn_tou_seed1": "POLICY_CANDIDATE_FROZEN_DQN_TOU",
    "grid_flat_discrete_42": "POLICY_CANDIDATE_GRID_FLAT_DISCRETE_42",
    "grid_tou_discrete_43": "POLICY_CANDIDATE_GRID_TOU_DISCRETE_43",
    "actual_utility_cs351075": "ACTUAL_UTILITY_CS351075_REFERENCE",
}

WEATHER_POLICY_IDS = (
    "ALWAYS_GRID_114",
    "ALWAYS_GRID_42",
    "ALWAYS_GRID_43",
    "ALWAYS_CONTINUOUS_68_74",
    "COLD_TRIGGER_10F",
    "COLD_TRIGGER_20F",
    "COLD_TRIGGER_30F",
    "COLD_TRIGGER_20F_4H",
    "COLD_TRIGGER_20F_8H",
)

COLD_TRIGGER_IDS = (
    "COLD_TRIGGER_10F",
    "COLD_TRIGGER_20F",
    "COLD_TRIGGER_30F",
    "COLD_TRIGGER_20F_4H",
    "COLD_TRIGGER_20F_8H",
)


def _w2a_from_quality(quality: Mapping[str, Any] | None) -> tuple[int | None, int | None]:
    q = quality or {}
    phase = q.get("w2a_low_airflow_by_phase") or {}
    scored = phase.get("scored_runtime")
    warmup = phase.get("warmup")
    if scored is None:
        try:
            scored = scored_runtime_w2a_count(dict(q))
        except Exception:  # noqa: BLE001
            scored = None
    return (
        int(scored) if scored is not None else None,
        int(warmup) if warmup is not None else None,
    )


def strategy_passes_checked_readiness(payload: Mapping[str, Any]) -> bool:
    daily = payload.get("daily") or []
    checked = [d for d in daily if d.get("checked_school_day") or d.get("school_day")]
    if not checked:
        # Imported two-month arms may lack checked flags — use readiness_ok when present
        ready_flags = [d.get("readiness_ok") for d in daily if d.get("readiness_ok") is not None]
        return bool(ready_flags) and all(ready_flags)
    return all(bool(d.get("readiness_ok")) for d in checked)


def build_strategy_summary_row(strategy: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    fac = payload["facility_kw"]
    daily = payload.get("daily") or []
    phys = {r["period"]: r for r in aggregate_monthly_physical(strategy=strategy, facility_kw=fac, daily_rows=daily)}
    flat = {r["period"]: r for r in score_flat_plus_demand(fac)}
    tou = {r["period"]: r for r in score_tou_plus_demand(fac)}
    checked = [d for d in daily if d.get("checked_school_day") or (d.get("school_day") and d.get("readiness_ok") is not None)]
    ready = [d for d in checked if d.get("readiness_ok")]
    occ_dh = sum(float(d.get("occupied_comfort_degree_hours") or 0) for d in daily)
    n_cont = int(payload.get("n_continuous_days") or sum(1 for d in daily if d.get("continuous_day")))
    trigger_dates = list(payload.get("trigger_dates") or [d["day"] for d in daily if d.get("continuous_day")])
    q = payload.get("quality") or {}
    w2a_scored, w2a_warmup = _w2a_from_quality(q)
    return {
        "strategy": strategy,
        "public_label": STRATEGY_LABELS.get(strategy, strategy),
        "dec_kwh": phys["2025-12"]["total_kwh"],
        "dec_peak_15min_kw": phys["2025-12"]["peak_15min_kw"],
        "jan_kwh": phys["2026-01"]["total_kwh"],
        "jan_peak_15min_kw": phys["2026-01"]["peak_15min_kw"],
        "two_month_kwh": phys["two_month"]["total_kwh"],
        "two_month_peak_15min_kw": phys["two_month"]["peak_15min_kw"],
        "illustrative_energy_charge_usd": flat["two_month"]["energy_charge_usd"],
        "illustrative_dec_demand_charge_usd": flat["2025-12"]["demand_charge_usd"],
        "illustrative_jan_demand_charge_usd": flat["2026-01"]["demand_charge_usd"],
        "illustrative_total_cost_usd": flat["two_month"]["total_usd"],
        "illustrative_tou_total_cost_usd": tou["two_month"]["total_usd"],
        "checked_school_days": len(checked),
        "ready_checked_school_days": len(ready),
        "occupied_comfort_degree_hours": round(occ_dh, 4),
        "n_continuous_conditioning_days": n_cont,
        "trigger_dates": ";".join(trigger_dates),
        "severe_count": q.get("severe_count"),
        "fatal_count": q.get("fatal_count"),
        "w2a_scored_runtime": w2a_scored,
        "w2a_warmup": w2a_warmup,
        "n_process_starts": payload.get("n_process_starts"),
        "wall_s": payload.get("elapsed_s"),
        "trajectory_sha256": payload.get("trajectory_hash"),
        "passes_checked_readiness": strategy_passes_checked_readiness(payload),
        "n_intervals": payload.get("n_intervals"),
    }


def build_summary_table(results: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [build_strategy_summary_row(s, p) for s, p in sorted(results.items())]


def peak_first_sensitivity(
    results: Mapping[str, Mapping[str, Any]],
    *,
    tie_kw: float = 1.0,
) -> dict[str, Any]:
    """PEAK_FIRST_RESEARCH_SENSITIVITY — separate from primary economic ranking."""
    rows = []
    for strategy, payload in results.items():
        if not strategy_passes_checked_readiness(payload):
            continue
        summary = build_strategy_summary_row(strategy, payload)
        rows.append(summary)
    if not rows:
        return {
            "label": "PEAK_FIRST_RESEARCH_SENSITIVITY",
            "selected": None,
            "reason": "no strategy passed checked school-readiness",
            "candidates": [],
        }
    min_peak = min(float(r["two_month_peak_15min_kw"]) for r in rows)
    near = [r for r in rows if float(r["two_month_peak_15min_kw"]) <= min_peak + float(tie_kw)]
    selected = min(near, key=lambda r: float(r["illustrative_total_cost_usd"]))
    return {
        "label": "PEAK_FIRST_RESEARCH_SENSITIVITY",
        "selected": selected["strategy"],
        "min_peak_kw": min_peak,
        "tie_kw": float(tie_kw),
        "selected_row": selected,
        "candidates": [
            {
                "strategy": r["strategy"],
                "two_month_peak_15min_kw": r["two_month_peak_15min_kw"],
                "illustrative_total_cost_usd": r["illustrative_total_cost_usd"],
                "two_month_kwh": r["two_month_kwh"],
            }
            for r in sorted(rows, key=lambda x: (x["two_month_peak_15min_kw"], x["illustrative_total_cost_usd"]))
        ],
    }


def peak_cap_feasibility(
    results: Mapping[str, Mapping[str, Any]],
    *,
    caps_kw: Sequence[float] | None = None,
) -> list[dict[str, Any]]:
    contract = load_weather_trigger_contract()
    caps = list(caps_kw) if caps_kw is not None else list(contract.get("peak_caps_kw") or [260, 250, 240, 230])
    out: list[dict[str, Any]] = []
    for strategy, payload in sorted(results.items()):
        peak = float(aggregate_monthly_physical(strategy=strategy, facility_kw=payload["facility_kw"], daily_rows=payload.get("daily") or [])[2]["peak_15min_kw"])
        for cap in caps:
            out.append(
                {
                    "strategy": strategy,
                    "peak_cap_kw": float(cap),
                    "two_month_peak_15min_kw": peak,
                    "passes_cap": peak <= float(cap),
                }
            )
    return out


def research_conclusion(
    *,
    results: Mapping[str, Mapping[str, Any]],
    invalid: bool = False,
) -> dict[str, Any]:
    if invalid:
        return {
            "verdict": "EXPERIMENT_INVALID",
            "simulation_training_ready": False,
            "operational_dsm_ready": False,
            "operational_winner": None,
        }
    summaries = {r["strategy"]: r for r in build_summary_table(results)}
    grid114 = summaries.get("ALWAYS_GRID_114")
    continuous = summaries.get("ALWAYS_CONTINUOUS_68_74")
    cold = [summaries[s] for s in COLD_TRIGGER_IDS if s in summaries and summaries[s].get("passes_checked_readiness")]
    ready_all = [r for r in summaries.values() if r.get("passes_checked_readiness")]

    if continuous and ready_all:
        lowest_peak = min(ready_all, key=lambda r: float(r["two_month_peak_15min_kw"]))
        if lowest_peak["strategy"] == "ALWAYS_CONTINUOUS_68_74" and (
            not cold
            or all(
                float(c["two_month_peak_15min_kw"]) >= float(continuous["two_month_peak_15min_kw"]) - 1e-9
                for c in cold
            )
        ):
            # Continuous remains lowest peak among ready; check if any cold also improves cost vs 114
            if grid114 and cold:
                peak_improvers = [
                    c
                    for c in cold
                    if float(c["two_month_peak_15min_kw"]) < float(grid114["two_month_peak_15min_kw"])
                ]
                if not peak_improvers and float(continuous["two_month_peak_15min_kw"]) <= float(
                    grid114["two_month_peak_15min_kw"]
                ):
                    return {
                        "verdict": "CONTINUOUS_68_74_REMAINS_LOWEST_PEAK",
                        "simulation_training_ready": False,
                        "operational_dsm_ready": False,
                        "operational_winner": None,
                        "lowest_peak_strategy": continuous["strategy"],
                        "best_economic_strategy": min(
                            ready_all, key=lambda r: float(r["illustrative_total_cost_usd"])
                        )["strategy"],
                    }

    if not grid114 or not cold:
        return {
            "verdict": "NO_WEATHER_TRIGGER_IMPROVEMENT",
            "simulation_training_ready": False,
            "operational_dsm_ready": False,
            "operational_winner": None,
        }

    g_peak = float(grid114["two_month_peak_15min_kw"])
    g_cost = float(grid114["illustrative_total_cost_usd"])
    g_kwh = float(grid114["two_month_kwh"])

    improves_both = [
        c
        for c in cold
        if float(c["two_month_peak_15min_kw"]) < g_peak and float(c["illustrative_total_cost_usd"]) < g_cost
    ]
    if improves_both:
        best = min(improves_both, key=lambda r: (r["two_month_peak_15min_kw"], r["illustrative_total_cost_usd"]))
        return {
            "verdict": "WEATHER_TRIGGER_IMPROVES_PEAK_AND_COST",
            "simulation_training_ready": False,
            "operational_dsm_ready": False,
            "operational_winner": None,
            "best_weather_trigger": best["strategy"],
            "best_economic_strategy": min(ready_all, key=lambda r: float(r["illustrative_total_cost_usd"]))["strategy"],
            "lowest_peak_strategy": min(ready_all, key=lambda r: float(r["two_month_peak_15min_kw"]))["strategy"],
        }

    peak_only = [
        c
        for c in cold
        if float(c["two_month_peak_15min_kw"]) < g_peak
        and (float(c["two_month_kwh"]) > g_kwh or float(c["illustrative_total_cost_usd"]) > g_cost)
    ]
    if peak_only:
        best = min(peak_only, key=lambda r: float(r["two_month_peak_15min_kw"]))
        return {
            "verdict": "WEATHER_TRIGGER_IMPROVES_PEAK_WITH_ENERGY_PENALTY",
            "simulation_training_ready": False,
            "operational_dsm_ready": False,
            "operational_winner": None,
            "best_weather_trigger": best["strategy"],
            "best_economic_strategy": min(ready_all, key=lambda r: float(r["illustrative_total_cost_usd"]))["strategy"],
            "lowest_peak_strategy": min(ready_all, key=lambda r: float(r["two_month_peak_15min_kw"]))["strategy"],
        }

    cost_only = [
        c
        for c in cold
        if float(c["illustrative_total_cost_usd"]) < g_cost and float(c["two_month_peak_15min_kw"]) >= g_peak
    ]
    if cost_only:
        best = min(cost_only, key=lambda r: float(r["illustrative_total_cost_usd"]))
        return {
            "verdict": "WEATHER_TRIGGER_LOWERS_COST_BUT_NOT_PEAK",
            "simulation_training_ready": False,
            "operational_dsm_ready": False,
            "operational_winner": None,
            "best_weather_trigger": best["strategy"],
            "best_economic_strategy": min(ready_all, key=lambda r: float(r["illustrative_total_cost_usd"]))["strategy"],
            "lowest_peak_strategy": min(ready_all, key=lambda r: float(r["two_month_peak_15min_kw"]))["strategy"],
        }

    if continuous and ready_all:
        lowest = min(ready_all, key=lambda r: float(r["two_month_peak_15min_kw"]))
        if lowest["strategy"] == "ALWAYS_CONTINUOUS_68_74":
            return {
                "verdict": "CONTINUOUS_68_74_REMAINS_LOWEST_PEAK",
                "simulation_training_ready": False,
                "operational_dsm_ready": False,
                "operational_winner": None,
                "lowest_peak_strategy": continuous["strategy"],
                "best_economic_strategy": min(ready_all, key=lambda r: float(r["illustrative_total_cost_usd"]))[
                    "strategy"
                ],
            }

    return {
        "verdict": "NO_WEATHER_TRIGGER_IMPROVEMENT",
        "simulation_training_ready": False,
        "operational_dsm_ready": False,
        "operational_winner": None,
        "best_economic_strategy": min(ready_all, key=lambda r: float(r["illustrative_total_cost_usd"]))["strategy"]
        if ready_all
        else None,
        "lowest_peak_strategy": min(ready_all, key=lambda r: float(r["two_month_peak_15min_kw"]))["strategy"]
        if ready_all
        else None,
    }
