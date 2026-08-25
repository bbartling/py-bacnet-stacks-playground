"""Day 05 — expand the WLHP menu (4 setbacks x 4 leads)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eplus_lab as lab

SOURCE = "5ZoneWaterLoopHeatPump.idf"
SCHEDULE = "HTG-SETP-SCH"
OCCUPIED_C = 21.1
SCHOOL_START = 8
SCHOOL_END = 18


def candidate_menu() -> list[tuple[str, float, int]]:
    rows = []
    for setback_f in (60, 62, 64, 68):
        for lead in (0, 1, 2, 3):
            rows.append((f"SB{setback_f}_LEAD{lead}", float(setback_f), lead))
    return rows


def build_idf(source: str, setback_f: float, lead: int) -> str:
    setback_c = lab.f_to_c(setback_f)
    recovery = SCHOOL_START - lead
    text = lab.replace_object(
        source,
        "Schedule:Compact",
        SCHEDULE,
        lab.heating_setpoint_schedule(
            SCHEDULE,
            setback_c=setback_c,
            occupied_c=OCCUPIED_C,
            recovery_hour=recovery,
            occupied_end_hour=SCHOOL_END,
        ),
    )
    text = lab.set_single_run_period(text)
    text = lab.force_run_period_only(text)
    return lab.append_outputs(text, lab.DEFAULT_OUTPUTS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs" / "day05_expand_menu",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run only 4 corner candidates for a faster smoke test",
    )
    args = parser.parse_args()

    source_path = lab.example_idf(SOURCE)
    source = source_path.read_text(encoding="utf-8", errors="replace")
    menu = candidate_menu()
    if args.quick:
        menu = [menu[0], menu[3], menu[12], menu[15]]

    print("DAY 05 — EXPAND THE MENU")
    print(f"Model: {SOURCE} | {len(menu)} EnergyPlus runs\n")

    results = []
    for index, (name, setback_f, lead) in enumerate(menu, start=1):
        print(f"[{index:02d}/{len(menu)}] {name:<14}", end=" ", flush=True)
        text = build_idf(source, setback_f, lead)
        runtime = lab.run_energyplus(text, args.output / "runs" / name)
        metrics = lab.parse_facility_and_readiness(
            args.output / "runs" / name, candidate=name, runtime=runtime
        )
        results.append(metrics)
        print(
            f"ready={str(metrics.ready):<5} kWh={metrics.electricity_kwh:7.1f} "
            f"obj=${metrics.objective_usd:8.2f} ({runtime:.1f}s)"
        )

    winner = lab.print_ranked(results)
    lab.write_results_csv(results, args.output / "grid_search_results.csv")
    lab.write_decision_json(
        args.output / "selected_plan.json",
        {
            "lesson": "day05",
            "model": SOURCE,
            "n_candidates": len(menu),
            "winner": None if winner is None else winner.candidate,
            "warning": "EDUCATIONAL — mirrors energyplus_grid_search_demo.py shape",
        },
    )


if __name__ == "__main__":
    main()
