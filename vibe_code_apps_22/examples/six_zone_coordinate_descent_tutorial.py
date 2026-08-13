# DOCUMENTATION ONLY — fake-data screening tutorial.
# Production code must NEVER import this module or use its simulate() function.
# Copied from simmer_six_zone.py for algorithm reference (coordinate descent).
"""Six-zone daily DSM optimizer tutorial using only the Python standard library.

The optimizer first searches global setback/recovery settings. It then uses
coordinate descent: adjust one zone at a time, retain an improvement, and repeat.

This is fake-data screening code, not a calibrated building model or BAS writer.
"""

from __future__ import annotations

import copy
import csv
import json
from datetime import date
from itertools import product
from pathlib import Path
from typing import Any


SCENARIO = {
    "date": "2026-01-26",
    "school_day": True,
    "occupied_start_hour": 7,
    "occupied_end_hour": 16,
    "occupied_heating_f": 70.0,
    "interval_hours": 1.0,
    "unoccupied_baseload_kw": 42.0,
    "occupied_plugs_lights_kw": 52.0,
    "zone_fan_kw": 3.0,
    "heating_cop": 3.1,
    "max_heating_thermal_kw": 600.0,
}


TARIFF = {
    "status": "ILLUSTRATIVE",
    "off_peak_usd_per_kwh": 0.08,
    "peak_usd_per_kwh": 0.14,
    "peak_rate_start_hour": 7,
    "peak_rate_end_hour": 18,
    "demand_usd_per_kw_month": 15.0,
    "month_to_date_peak_kw": 230.0,
    "ratchet_floor_kw": 0.0,
    "contract_demand_floor_kw": 0.0,
    "comfort_penalty_usd_per_f_hour": 250.0,
    "movement_penalty_usd_per_f": 0.50,
    "allowed_comfort_violation_f_hours": 0.0,
}


COMFORT = {
    "occupied_min_f": 68.0,
    "occupied_max_f": 74.0,
    "unoccupied_min_f": 55.0,
    "unoccupied_max_f": 85.0,
}


OUTDOOR_F = [
    -2, -4, -6, -8, -9, -8, -5, 0, 5, 10, 14, 17,
    19, 20, 18, 14, 10, 6, 3, 1, 0, -1, -2, -3,
]


ZONES = {
    "1F_A": {"initial_f": 65.0, "ua": 0.72, "leakage": 0.018, "recovery": 0.85, "recovery_kw": 5.2},
    "1F_B": {"initial_f": 64.5, "ua": 0.68, "leakage": 0.020, "recovery": 0.82, "recovery_kw": 4.8},
    "1F_C": {"initial_f": 65.5, "ua": 0.75, "leakage": 0.017, "recovery": 0.86, "recovery_kw": 5.4},
    "1F_D": {"initial_f": 64.0, "ua": 0.70, "leakage": 0.021, "recovery": 0.80, "recovery_kw": 4.9},
    "2F_A": {"initial_f": 65.0, "ua": 0.82, "leakage": 0.019, "recovery": 0.84, "recovery_kw": 5.8},
    "2F_B": {"initial_f": 64.5, "ua": 0.78, "leakage": 0.020, "recovery": 0.83, "recovery_kw": 5.5},
}


MAX_COORDINATE_PASSES = 2
ZONE_MOVES = (
    ("setback_down", "setback_offset_f", -1.0),
    ("setback_up", "setback_offset_f", 1.0),
    ("recover_later", "recovery_offset_h", -1.0),
    ("recover_earlier", "recovery_offset_h", 1.0),
)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def make_forecast() -> list[dict[str, Any]]:
    rows = []
    for hour, outdoor_f in enumerate(OUTDOOR_F):
        occupied = bool(
            SCENARIO["school_day"]
            and SCENARIO["occupied_start_hour"] <= hour < SCENARIO["occupied_end_hour"]
        )
        peak_rate = TARIFF["peak_rate_start_hour"] <= hour < TARIFF["peak_rate_end_hour"]
        rows.append(
            {
                "hour": hour,
                "outdoor_f": float(outdoor_f),
                "occupied": occupied,
                "rate": (
                    TARIFF["peak_usd_per_kwh"]
                    if peak_rate
                    else TARIFF["off_peak_usd_per_kwh"]
                ),
            }
        )
    return rows


def new_policy(global_unoccupied_f: float, global_recovery_h: float) -> dict[str, Any]:
    return {
        "global_unoccupied_f": float(global_unoccupied_f),
        "global_recovery_h": float(global_recovery_h),
        "zones": {
            zone: {
                "setback_offset_f": 0.0,
                "recovery_offset_h": 0.0,
                "occupied_offset_f": 0.0,
            }
            for zone in ZONES
        },
    }


def policy_key(policy: dict[str, Any]) -> str:
    return json.dumps(policy, sort_keys=True, separators=(",", ":"))


def zone_controls(policy: dict[str, Any], zone: str) -> dict[str, float]:
    adjustment = policy["zones"][zone]
    return {
        "unoccupied_f": clamp(
            policy["global_unoccupied_f"] + adjustment["setback_offset_f"],
            60.0,
            66.0,
        ),
        "occupied_f": clamp(
            SCENARIO["occupied_heating_f"] + adjustment["occupied_offset_f"],
            68.0,
            71.0,
        ),
        "recovery_h": clamp(
            policy["global_recovery_h"] + adjustment["recovery_offset_h"],
            0.0,
            4.0,
        ),
    }


def zone_setpoint_f(
    controls: dict[str, float], hour: int, occupied: bool
) -> float:
    if occupied:
        return controls["occupied_f"]
    if not SCENARIO["school_day"]:
        return controls["unoccupied_f"]

    lead = controls["recovery_h"]
    recovery_start = SCENARIO["occupied_start_hour"] - lead
    ramp_h = min(2.0, lead)
    if lead > 0 and recovery_start <= hour < SCENARIO["occupied_start_hour"]:
        progress = clamp((hour - recovery_start) / max(0.25, ramp_h), 0.0, 1.0)
        return controls["unoccupied_f"] + progress * (
            controls["occupied_f"] - controls["unoccupied_f"]
        )
    return controls["unoccupied_f"]


def zone_fan_enabled(controls: dict[str, float], hour: int, occupied: bool) -> bool:
    if occupied:
        return True
    if not SCENARIO["school_day"]:
        return False
    recovery_start = SCENARIO["occupied_start_hour"] - controls["recovery_h"]
    return recovery_start <= hour < SCENARIO["occupied_end_hour"]


def comfort_bounds(occupied: bool) -> tuple[float, float]:
    if occupied:
        return COMFORT["occupied_min_f"], COMFORT["occupied_max_f"]
    return COMFORT["unoccupied_min_f"], COMFORT["unoccupied_max_f"]


def simulate(policy: dict[str, Any], forecast: list[dict[str, Any]]) -> dict[str, Any]:
    """One complete 24-hour, six-zone simulation."""
    dt = SCENARIO["interval_hours"]
    temperatures = {zone: data["initial_f"] for zone, data in ZONES.items()}
    prior_setpoints = {
        zone: zone_controls(policy, zone)["unoccupied_f"] for zone in ZONES
    }
    hourly = []

    for weather in forecast:
        hour = weather["hour"]
        outdoor_f = weather["outdoor_f"]
        occupied = weather["occupied"]
        controls = {zone: zone_controls(policy, zone) for zone in ZONES}
        setpoints = {
            zone: zone_setpoint_f(controls[zone], hour, occupied) for zone in ZONES
        }
        fans = {
            zone: zone_fan_enabled(controls[zone], hour, occupied) for zone in ZONES
        }

        # Calculate each zone's unconstrained request first, then apply one plant cap.
        free_float: dict[str, float] = {}
        thermal_request: dict[str, float] = {}
        for zone, data in ZONES.items():
            prior_f = temperatures[zone]
            free_f = prior_f + data["leakage"] * (outdoor_f - prior_f) * dt
            deficit_f = max(0.0, setpoints[zone] - free_f)
            steady_kw = (
                data["ua"] * max(0.0, setpoints[zone] - outdoor_f)
                if deficit_f > 0
                else 0.0
            )
            free_float[zone] = free_f
            thermal_request[zone] = steady_kw + data["recovery_kw"] * deficit_f

        requested_kw = sum(thermal_request.values())
        delivered_kw = min(requested_kw, SCENARIO["max_heating_thermal_kw"])
        capacity_fraction = delivered_kw / requested_kw if requested_kw > 0 else 0.0

        low_f, high_f = comfort_bounds(occupied)
        new_temperatures: dict[str, float] = {}
        violation_by_zone: dict[str, float] = {}
        for zone, data in ZONES.items():
            deficit_f = max(0.0, setpoints[zone] - free_float[zone])
            new_f = (
                free_float[zone]
                + data["recovery"] * deficit_f * capacity_fraction * dt
            )
            new_temperatures[zone] = new_f
            violation_by_zone[zone] = max(0.0, low_f - new_f) + max(
                0.0, new_f - high_f
            )

        base_kw = SCENARIO["unoccupied_baseload_kw"]
        if occupied:
            base_kw += SCENARIO["occupied_plugs_lights_kw"]
        fan_kw = sum(SCENARIO["zone_fan_kw"] for enabled in fans.values() if enabled)
        heating_kw = delivered_kw / SCENARIO["heating_cop"]
        facility_kw = base_kw + fan_kw + heating_kw
        interval_kwh = facility_kw * dt
        movement_f = sum(
            abs(setpoints[zone] - prior_setpoints[zone]) for zone in ZONES
        )

        row: dict[str, Any] = {
            "hour": hour,
            "outdoor_f": round(outdoor_f, 4),
            "occupied": occupied,
            "facility_kw": round(facility_kw, 6),
            "interval_kwh": round(interval_kwh, 6),
            "energy_cost_usd": round(interval_kwh * weather["rate"], 6),
            "comfort_violation_f": round(sum(violation_by_zone.values()), 6),
            "movement_f": round(movement_f, 6),
        }
        for zone in ZONES:
            row[f"sp_{zone}"] = round(setpoints[zone], 4)
            row[f"temp_{zone}"] = round(new_temperatures[zone], 4)
            row[f"violation_{zone}"] = round(violation_by_zone[zone], 6)
            row[f"fan_{zone}"] = fans[zone]
        hourly.append(row)

        temperatures = new_temperatures
        prior_setpoints = setpoints

    summary = {
        "peak_kw": max(row["facility_kw"] for row in hourly),
        "kwh": sum(row["interval_kwh"] for row in hourly),
        "energy_cost_usd": sum(row["energy_cost_usd"] for row in hourly),
        "comfort_violation_f_hours": sum(
            row["comfort_violation_f"] * dt for row in hourly
        ),
        "max_hourly_comfort_violation_f": max(
            row["comfort_violation_f"] for row in hourly
        ),
        "movement_f": sum(row["movement_f"] for row in hourly),
        "zone_min_f": {
            zone: min(row[f"temp_{zone}"] for row in hourly) for zone in ZONES
        },
        "zone_max_f": {
            zone: max(row[f"temp_{zone}"] for row in hourly) for zone in ZONES
        },
    }
    return {"policy": copy.deepcopy(policy), "summary": summary, "hourly": hourly}


def score(run: dict[str, Any], baseline: dict[str, Any]) -> None:
    result = run["summary"]
    base = baseline["summary"]
    floor_kw = max(
        TARIFF["month_to_date_peak_kw"],
        TARIFF["ratchet_floor_kw"],
        TARIFF["contract_demand_floor_kw"],
    )
    demand_delta = TARIFF["demand_usd_per_kw_month"] * (
        max(floor_kw, result["peak_kw"]) - max(floor_kw, base["peak_kw"])
    )
    comfort_cost = (
        result["comfort_violation_f_hours"]
        * TARIFF["comfort_penalty_usd_per_f_hour"]
    )
    movement_cost = result["movement_f"] * TARIFF["movement_penalty_usd_per_f"]
    result.update(
        {
            "billing_floor_kw": floor_kw,
            "kwh_penalty": result["kwh"] - base["kwh"],
            "incremental_demand_cost_usd": demand_delta,
            "comfort_penalty_usd": comfort_cost,
            "movement_penalty_usd": movement_cost,
            "objective_j_usd": (
                result["energy_cost_usd"]
                + demand_delta
                + comfort_cost
                + movement_cost
            ),
            "feasible": result["comfort_violation_f_hours"]
            <= TARIFF["allowed_comfort_violation_f_hours"] + 1e-9,
        }
    )


def better(candidate: dict[str, Any], incumbent: dict[str, Any]) -> bool:
    a = candidate["summary"]
    b = incumbent["summary"]
    if a["feasible"] and not b["feasible"]:
        return True
    if not a["feasible"]:
        return False
    return a["objective_j_usd"] < b["objective_j_usd"] - 1e-9


def optimize() -> dict[str, Any]:
    forecast = make_forecast()
    cache: dict[str, dict[str, Any]] = {}
    history: list[dict[str, Any]] = []

    baseline_policy = new_policy(65.0, 0.0)
    baseline = simulate(baseline_policy, forecast)
    score(baseline, baseline)
    cache[policy_key(baseline_policy)] = baseline

    def evaluate(policy: dict[str, Any], stage: str, label: str) -> dict[str, Any]:
        key = policy_key(policy)
        if key not in cache:
            run = simulate(policy, forecast)
            score(run, baseline)
            cache[key] = run
            history.append(
                {
                    "simulation_number": len(cache),
                    "stage": stage,
                    "label": label,
                    **{
                        name: run["summary"][name]
                        for name in (
                            "peak_kw",
                            "kwh",
                            "kwh_penalty",
                            "comfort_violation_f_hours",
                            "incremental_demand_cost_usd",
                            "objective_j_usd",
                            "feasible",
                        )
                    },
                    "policy_key": key,
                }
            )
        return cache[key]

    history.append(
        {
            "simulation_number": 1,
            "stage": "baseline",
            "label": "Baseline",
            **{
                name: baseline["summary"][name]
                for name in (
                    "peak_kw",
                    "kwh",
                    "kwh_penalty",
                    "comfort_violation_f_hours",
                    "incremental_demand_cost_usd",
                    "objective_j_usd",
                    "feasible",
                )
            },
            "policy_key": policy_key(baseline_policy),
        }
    )

    # Phase 1: only 16 global policies, while all six zone temperatures are simulated.
    global_runs = []
    for setback_f, recovery_h in product([65.0, 64.0, 63.0, 62.0], [0, 1, 2, 3]):
        policy = new_policy(setback_f, recovery_h)
        global_runs.append(
            evaluate(policy, "global_grid", f"global_{setback_f:.0f}F_{recovery_h}h")
        )
    incumbent = min(
        (run for run in global_runs if run["summary"]["feasible"]),
        key=lambda run: run["summary"]["objective_j_usd"],
    )
    best_global = copy.deepcopy(incumbent)

    # Phase 2: change one zone at a time. Four neighbor moves per zone per pass.
    accepted_moves = []
    for pass_number in range(1, MAX_COORDINATE_PASSES + 1):
        improved_this_pass = False
        for zone in ZONES:
            local_best = incumbent
            best_move = None
            for move_name, field, delta in ZONE_MOVES:
                trial_policy = copy.deepcopy(incumbent["policy"])
                current = trial_policy["zones"][zone][field]
                if field == "setback_offset_f":
                    trial_policy["zones"][zone][field] = clamp(current + delta, -2.0, 2.0)
                else:
                    trial_policy["zones"][zone][field] = clamp(current + delta, -2.0, 2.0)
                trial = evaluate(
                    trial_policy,
                    f"coordinate_pass_{pass_number}",
                    f"{zone}_{move_name}",
                )
                if better(trial, local_best):
                    local_best = trial
                    best_move = move_name

            if best_move is not None and better(local_best, incumbent):
                incumbent = local_best
                improved_this_pass = True
                accepted_moves.append(
                    {
                        "pass": pass_number,
                        "zone": zone,
                        "move": best_move,
                        "objective_j_usd": incumbent["summary"]["objective_j_usd"],
                    }
                )
        if not improved_this_pass:
            break

    return {
        "forecast": forecast,
        "baseline": baseline,
        "best_global": best_global,
        "screening_solution": incumbent,
        "history": history,
        "accepted_moves": accepted_moves,
        "unique_simulations": len(cache),
    }


def effective_schedule(policy: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for zone in ZONES:
        controls = zone_controls(policy, zone)
        rows.append(
            {
                "zone": zone,
                "unoccupied_heating_f": controls["unoccupied_f"],
                "occupied_heating_f": controls["occupied_f"],
                "recovery_lead_hours": controls["recovery_h"],
            }
        )
    return rows


def save_outputs(study: dict[str, Any]) -> Path:
    output_dir = Path(__file__).with_name("six_zone_dsm_output")
    output_dir.mkdir(parents=True, exist_ok=True)
    solution = study["screening_solution"]

    payload = {
        "claim": "SIX_ZONE_TUTORIAL_SCREENING_ONLY",
        "scenario": {
            **SCENARIO,
            "day_of_week": date.fromisoformat(SCENARIO["date"]).strftime("%A"),
        },
        "tariff": TARIFF,
        "unique_full_day_simulations": study["unique_simulations"],
        "accepted_moves": study["accepted_moves"],
        "baseline": study["baseline"]["summary"],
        "best_global": study["best_global"]["summary"],
        "screening_solution": solution["summary"],
        "six_zone_schedule": effective_schedule(solution["policy"]),
        "operational_winner": None,
    }
    (output_dir / "study.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with (output_dir / "evaluation_history.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(study["history"][0]))
        writer.writeheader()
        writer.writerows(study["history"])

    with (output_dir / "screening_solution_hourly.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(solution["hourly"][0]))
        writer.writeheader()
        writer.writerows(solution["hourly"])

    schedule = effective_schedule(solution["policy"])
    with (output_dir / "six_zone_schedule.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(schedule[0]))
        writer.writeheader()
        writer.writerows(schedule)

    return output_dir


def print_report(study: dict[str, Any]) -> None:
    baseline = study["baseline"]["summary"]
    global_result = study["best_global"]["summary"]
    solution = study["screening_solution"]
    final = solution["summary"]

    print("\nSIX-ZONE DSM COORDINATE-DESCENT TUTORIAL")
    print("Fake data and illustrative tariff; no operational BAS recommendation.\n")
    print(f"Full 24-hour simulations performed: {study['unique_simulations']}")
    print(f"Zone-temperature updates: {study['unique_simulations'] * 24 * len(ZONES)}")
    print(f"Accepted zone moves: {len(study['accepted_moves'])}\n")
    print(f"Baseline:    {baseline['peak_kw']:.1f} kW, {baseline['kwh']:.1f} kWh")
    print(f"Best global: {global_result['peak_kw']:.1f} kW, {global_result['kwh']:.1f} kWh")
    print(
        f"Six-zone:    {final['peak_kw']:.1f} kW, {final['kwh']:.1f} kWh, "
        f"comfort {final['comfort_violation_f_hours']:.2f} F-h"
    )
    print("\nFinal six-zone screening schedule:")
    print(f"{'Zone':<6} {'Unocc F':>9} {'Occ F':>8} {'Recovery lead h':>16}")
    print("-" * 44)
    for row in effective_schedule(solution["policy"]):
        print(
            f"{row['zone']:<6} {row['unoccupied_heating_f']:>9.1f} "
            f"{row['occupied_heating_f']:>8.1f} {row['recovery_lead_hours']:>16.1f}"
        )
    print("\nOperational recommendation: NONE")


def main() -> None:
    study = optimize()
    print_report(study)
    output_dir = save_outputs(study)
    print(f"Artifacts: {output_dir}")


if __name__ == "__main__":
    main()

