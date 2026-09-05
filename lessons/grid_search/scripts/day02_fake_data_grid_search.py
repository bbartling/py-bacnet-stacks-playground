"""Tiny six-zone DSM grid-search demonstration (standard library only).

This is a teaching model for a terminal/YouTube demonstration.  It shows the
same *shape* of the Vibe22 workflow -- forecast -> candidate schedules ->
building simulation -> cost/comfort score -> timed event plan -- without
requiring EnergyPlus, BACnet, pandas, or an API key.

It is NOT a calibrated building model and MUST NOT control a real BAS.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from itertools import product
from pathlib import Path


ZONES = ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B")
INTERVAL_MINUTES = 15
INTERVAL_HOURS = INTERVAL_MINUTES / 60
STEPS = 96
SCHOOL_START_STEP = 30  # 07:30
SCHOOL_END_STEP = 64  # 16:00
READINESS_STEPS = (30, 31)  # 07:30 and 07:45
COMFORT_MIN_F = 68.0
COMFORT_MAX_F = 74.0

# A deliberately obvious cold winter forecast, one value per hour.
HOURLY_OUTDOOR_F = (
    -4, -6, -8, -9, -8, -6, -2, 3, 8, 13, 17, 20,
    22, 23, 21, 17, 12, 8, 5, 2, 0, -1, -2, -3,
)

# Simplified CP-2-inspired rates. PCAC, discounts, holidays, and the rolling
# distribution-demand history are omitted from this educational example.
OFF_PEAK_RATE = 0.0468
ON_PEAK_RATE = 0.0707
ON_PEAK_DEMAND_RATE = 12.25
DISTRIBUTION_DEMAND_RATE = 1.75


@dataclass(frozen=True)
class Candidate:
    name: str
    unoccupied_heat_f: float
    occupied_heat_f: float
    recovery_lead_hours: float
    extension_hours: float


@dataclass
class Result:
    candidate: Candidate
    ready: bool
    readiness_failures: int
    total_kwh: float
    all_hours_peak_kw: float
    on_peak_peak_kw: float
    energy_cost: float
    on_peak_demand_cost: float
    distribution_demand_cost: float
    modeled_cost: float
    facility_kw: list[float]
    setpoints: list[float]
    zone_temps: dict[str, list[float]]


def outdoor_15_minute() -> list[float]:
    """Expand the hourly forecast into 96 fifteen-minute values."""
    return [float(value) for value in HOURLY_OUTDOOR_F for _ in range(4)]


def candidate_menu() -> list[Candidate]:
    """A bounded menu: 5 setbacks x 4 recovery leads x 2 extensions."""
    rows = []
    for setback, lead, extension in product(
        (60.0, 62.0, 64.0, 66.0, 68.0),
        (0.0, 1.0, 2.0, 3.0),
        (0.0, 1.0),
    ):
        rows.append(
            Candidate(
                name=f"SB{setback:.0f}_Lead{lead:.0f}_Ext{extension:.0f}",
                unoccupied_heat_f=setback,
                occupied_heat_f=70.0,
                recovery_lead_hours=lead,
                extension_hours=extension,
            )
        )
    return rows


def schedule_for(candidate: Candidate) -> list[float]:
    recovery_steps = round(candidate.recovery_lead_hours / INTERVAL_HOURS)
    extension_steps = round(candidate.extension_hours / INTERVAL_HOURS)
    recovery_start = max(0, SCHOOL_START_STEP - recovery_steps)
    occupied_end = min(STEPS, SCHOOL_END_STEP + extension_steps)
    values = []
    for step in range(STEPS):
        if recovery_start <= step < occupied_end:
            values.append(candidate.occupied_heat_f)
        else:
            values.append(candidate.unoccupied_heat_f)
    return values


def is_on_peak(step: int) -> bool:
    hour = step * INTERVAL_HOURS
    return 8.0 <= hour < 20.0


def simulate(candidate: Candidate) -> Result:
    """Run a transparent toy thermal simulation for one cold day."""
    outdoor = outdoor_15_minute()
    setpoints = schedule_for(candidate)
    temps = {
        zone: [68.0 - 0.15 * index]
        for index, zone in enumerate(ZONES)
    }
    facility_kw = []

    # Slightly different coefficients make the six zones behave differently.
    ua = (0.72, 0.68, 0.75, 0.70, 0.82, 0.78)
    leakage = (0.016, 0.018, 0.015, 0.019, 0.017, 0.018)
    cop = 3.1
    baseload_kw = 38.0
    occupied_load_kw = 47.0

    for step in range(STEPS):
        oat = outdoor[step]
        setpoint = setpoints[step]
        total_hvac_kw = 0.0

        for index, zone in enumerate(ZONES):
            current = temps[zone][-1]
            passive_change = leakage[index] * (oat - current) * INTERVAL_HOURS
            error = max(0.0, setpoint - current)

            # Heating response is capped to make recovery timing matter.
            active_heat_change = min(0.72, 0.12 + 0.24 * error) if error > 0 else 0.0
            next_temp = current + passive_change + active_heat_change
            temps[zone].append(next_temp)

            envelope_heat_kw = ua[index] * max(0.0, setpoint - oat)
            recovery_heat_kw = 8.0 * error
            total_hvac_kw += 1.35 * (envelope_heat_kw + recovery_heat_kw) / cop

        occupied = SCHOOL_START_STEP <= step < SCHOOL_END_STEP
        facility_kw.append(
            baseload_kw + (occupied_load_kw if occupied else 0.0) + total_hvac_kw
        )

    failures = 0
    for step in READINESS_STEPS:
        # temps has an initial value at index 0, so result after step N is N+1.
        for zone in ZONES:
            value = temps[zone][step + 1]
            if not COMFORT_MIN_F <= value <= COMFORT_MAX_F:
                failures += 1

    total_kwh = sum(facility_kw) * INTERVAL_HOURS
    energy_cost = sum(
        kw * INTERVAL_HOURS * (ON_PEAK_RATE if is_on_peak(step) else OFF_PEAK_RATE)
        for step, kw in enumerate(facility_kw)
    )
    all_peak = max(facility_kw)
    on_peak = max(kw for step, kw in enumerate(facility_kw) if is_on_peak(step))
    on_peak_demand = ON_PEAK_DEMAND_RATE * on_peak
    distribution_demand = DISTRIBUTION_DEMAND_RATE * all_peak
    modeled_cost = energy_cost + on_peak_demand + distribution_demand

    return Result(
        candidate=candidate,
        ready=failures == 0,
        readiness_failures=failures,
        total_kwh=total_kwh,
        all_hours_peak_kw=all_peak,
        on_peak_peak_kw=on_peak,
        energy_cost=energy_cost,
        on_peak_demand_cost=on_peak_demand,
        distribution_demand_cost=distribution_demand,
        modeled_cost=modeled_cost,
        facility_kw=facility_kw,
        setpoints=setpoints,
        zone_temps=temps,
    )


def time_label(step: int) -> str:
    minutes = step * INTERVAL_MINUTES
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def compile_events(result: Result, day: date) -> list[dict]:
    """Collapse 96 schedule values into start/end event blocks."""
    events = []
    start = 0
    values = result.setpoints
    for step in range(1, STEPS + 1):
        changed = step == STEPS or values[step] != values[start]
        if not changed:
            continue
        start_dt = datetime.combine(day, time()) + timedelta(minutes=15 * start)
        end_dt = datetime.combine(day, time()) + timedelta(minutes=15 * step)
        events.append(
            {
                "event_id": f"event-{len(events) + 1}",
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "heating_setpoint_f": values[start],
                "cooling_setpoint_f": 85.0 if values[start] < 68.0 else 74.0,
                "zones": list(ZONES),
                "event_active_rule": "start <= current_time < end",
            }
        )
        start = step
    return events


def print_result_table(results: list[Result], baseline: Result) -> None:
    print("\nTOP ADMISSIBLE PLANS (lower modeled cost is better)")
    print("-" * 92)
    print(
        f"{'rank':>4}  {'candidate':<19} {'ready':<5} "
        f"{'kWh':>8} {'peak kW':>9} {'on-pk kW':>9} {'cost':>10} {'vs base':>10}"
    )
    print("-" * 92)
    eligible = sorted((r for r in results if r.ready), key=lambda r: r.modeled_cost)
    for rank, result in enumerate(eligible[:10], start=1):
        savings = baseline.modeled_cost - result.modeled_cost
        print(
            f"{rank:>4}  {result.candidate.name:<19} {'yes':<5} "
            f"{result.total_kwh:>8.1f} {result.all_hours_peak_kw:>9.1f} "
            f"{result.on_peak_peak_kw:>9.1f} ${result.modeled_cost:>9.2f} "
            f"${savings:>+9.2f}"
        )
    print("-" * 92)


def write_outputs(results: list[Result], selected: Result, baseline: Result, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "grid_search_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "candidate",
                "ready",
                "readiness_failures",
                "kwh",
                "all_hours_peak_kw",
                "on_peak_peak_kw",
                "energy_cost",
                "on_peak_demand_cost",
                "distribution_demand_cost",
                "modeled_cost",
            ),
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "candidate": result.candidate.name,
                    "ready": result.ready,
                    "readiness_failures": result.readiness_failures,
                    "kwh": round(result.total_kwh, 3),
                    "all_hours_peak_kw": round(result.all_hours_peak_kw, 3),
                    "on_peak_peak_kw": round(result.on_peak_peak_kw, 3),
                    "energy_cost": round(result.energy_cost, 3),
                    "on_peak_demand_cost": round(result.on_peak_demand_cost, 3),
                    "distribution_demand_cost": round(result.distribution_demand_cost, 3),
                    "modeled_cost": round(result.modeled_cost, 3),
                }
            )

    events = compile_events(selected, date.fromisoformat("2026-01-26"))
    plan = {
        "schema": "toy.local_dsm_plan.v1",
        "warning": "EDUCATIONAL TOY MODEL - NOT ENERGYPLUS - NO BACNET AUTHORITY",
        "created_by": "standard-library six-zone grid-search demo",
        "baseline": baseline.candidate.name,
        "selected_candidate": selected.candidate.name,
        "predicted_kwh": round(selected.total_kwh, 2),
        "predicted_peak_kw": round(selected.all_hours_peak_kw, 2),
        "predicted_cost": round(selected.modeled_cost, 2),
        "predicted_savings_vs_baseline": round(
            baseline.modeled_cost - selected.modeled_cost, 2
        ),
        "school_ready": selected.ready,
        "events": events,
    }
    (output / "selected_dsm_plan.json").write_text(
        json.dumps(plan, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Tiny six-zone daily DSM grid-search demo")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs" / "day02_fake_data",
    )
    args = parser.parse_args()

    print("VIBE23 DAY 02 FAKE-DATA GRID SEARCH - EDUCATIONAL TOY MODEL")
    print("NOT ENERGYPLUS | NOT CALIBRATED | NO BACNET COMMAND AUTHORITY")
    print("\nTomorrow's hourly outdoor forecast (F):")
    print(" ".join(f"{hour:02d}:{value:>4.0f}" for hour, value in enumerate(HOURLY_OUTDOOR_F)))

    menu = candidate_menu()
    print(f"\n1. Build a bounded menu: {len(menu)} candidate HVAC plans")
    print("2. Simulate each plan for 24 hours at 15-minute resolution")
    print("3. Reject plans that fail the six-zone school-readiness test")
    print("4. Rank the remaining plans by energy + demand cost")

    # A simple reference: continuous 68 F heating availability all day.
    baseline_candidate = Candidate("BASELINE_CONTINUOUS_68", 68.0, 68.0, 0.0, 0.0)
    baseline = simulate(baseline_candidate)
    results = [simulate(candidate) for candidate in menu]
    eligible = [result for result in results if result.ready]
    if not eligible:
        raise SystemExit("No candidate passed readiness; retain normal BAS schedule.")
    best_candidate = min(eligible, key=lambda result: result.modeled_cost)

    # A real edge controller should retain baseline unless a candidate improves it.
    selected = (
        best_candidate
        if best_candidate.modeled_cost < baseline.modeled_cost
        else baseline
    )

    print_result_table(results, baseline)
    print("BASELINE")
    print(
        f"  {baseline.candidate.name}: {baseline.total_kwh:.1f} kWh, "
        f"{baseline.all_hours_peak_kw:.1f} kW, ${baseline.modeled_cost:.2f}"
    )
    print("\nDECISION")
    if selected is baseline:
        print("  BASELINE REMAINS WINNER - publish no DSM override event")
    else:
        savings = baseline.modeled_cost - selected.modeled_cost
        paycheck = min(500.0, max(0.0, 100.0 + 2.0 * savings))
        print(f"  Selected: {selected.candidate.name}")
        print(f"  Modeled savings vs baseline: ${savings:.2f}")
        print(f"  Silly operator paycheck: ${paycheck:.2f}")

    write_outputs(results, selected, baseline, args.output)
    print(f"\nResults: {args.output / 'grid_search_results.csv'}")
    print(f"Event plan: {args.output / 'selected_dsm_plan.json'}")
    print("\nIn Vibe22, EnergyPlus replaces this toy thermal calculation.")


if __name__ == "__main__":
    main()
