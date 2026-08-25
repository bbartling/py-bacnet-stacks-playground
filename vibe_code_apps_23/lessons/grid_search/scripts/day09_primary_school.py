"""Day 09 — RefBldgPrimarySchool occupancy-aware readiness grid."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eplus_lab as lab

SOURCE = "RefBldgPrimarySchoolNew2004_Chicago.idf"
SCHEDULE = "HTGSETP_SCH"
OCCUPIED_C = 21.0
# Primary school: check readiness near bell time.
READY_CLOCKS = ((7, 30), (7, 45), (8, 0))


def candidate_menu() -> list[tuple[str, float, int]]:
    rows = []
    for setback_f in (60, 62, 66):
        for lead in (1, 2, 3):
            rows.append((f"SB{setback_f}_LEAD{lead}", float(setback_f), lead))
    return rows


def build_idf(source: str, setback_f: float, lead: int) -> str:
    text = lab.replace_object(
        source,
        "Schedule:Compact",
        SCHEDULE,
        lab.heating_setpoint_schedule(
            SCHEDULE,
            setback_c=lab.f_to_c(setback_f),
            occupied_c=OCCUPIED_C,
            recovery_hour=8 - lead,
            occupied_end_hour=16,
        ),
    )
    text = lab.set_single_run_period(text)
    text = lab.ensure_weather_run(text)
    return lab.append_outputs(text, lab.DEFAULT_OUTPUTS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs" / "day09_primary_school",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run three representative candidates only",
    )
    args = parser.parse_args()

    source_path = lab.example_idf(SOURCE)
    source = source_path.read_text(encoding="utf-8", errors="replace")
    menu = candidate_menu()
    if args.quick:
        menu = [menu[0], menu[4], menu[8]]

    print("DAY 09 — PRIMARY SCHOOL READINESS GRID")
    print(f"Model: {SOURCE} | readiness clocks {READY_CLOCKS}")
    print(f"{len(menu)} EnergyPlus runs (school IDFs are slower)\n")

    results = []
    for index, (name, setback_f, lead) in enumerate(menu, start=1):
        print(f"[{index:02d}/{len(menu)}] {name}", end=" ", flush=True)
        text = build_idf(source, setback_f, lead)
        runtime = lab.run_energyplus(text, args.output / "runs" / name)
        metrics = lab.parse_facility_and_readiness(
            args.output / "runs" / name,
            candidate=name,
            runtime=runtime,
            ready_clocks=READY_CLOCKS,
            max_zones=None,
        )
        results.append(metrics)
        print(
            f"ready={metrics.ready} minF={metrics.min_ready_zone_f:.1f} "
            f"kWh={metrics.electricity_kwh:.1f} ({runtime:.1f}s)"
        )

    winner = lab.print_ranked(results)
    lab.write_results_csv(results, args.output / "grid_search_results.csv")
    lab.write_decision_json(
        args.output / "selected_plan.json",
        {
            "lesson": "day09",
            "model": SOURCE,
            "ready_clocks": [f"{h:02d}:{m:02d}" for h, m in READY_CLOCKS],
            "winner": None if winner is None else winner.candidate,
            "note": "Occupancy-aware readiness — fail closed if classrooms are cold",
        },
    )


if __name__ == "__main__":
    main()
