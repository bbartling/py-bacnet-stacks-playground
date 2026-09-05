"""Day 08 — RefBldgSmallOffice heating setback grid (Chicago DOE reference)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eplus_lab as lab

SOURCE = "RefBldgSmallOfficeNew2004_Chicago.idf"
SCHEDULE = "HTGSETP_SCH"
OCCUPIED_C = 21.0


def candidate_menu() -> list[tuple[str, float, int]]:
    rows = []
    for setback_f in (60, 64, 68):
        for lead in (0, 2):
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
            occupied_end_hour=18,
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
        default=Path(__file__).resolve().parents[1] / "outputs" / "day08_small_office",
    )
    args = parser.parse_args()

    source_path = lab.example_idf(SOURCE)
    source = source_path.read_text(encoding="utf-8", errors="replace")
    menu = candidate_menu()
    print("DAY 08 — SMALL OFFICE REFERENCE BUILDING")
    print(f"Model: {SOURCE} | {len(menu)} runs\n")

    results = []
    for index, (name, setback_f, lead) in enumerate(menu, start=1):
        print(f"[{index}/{len(menu)}] {name}", end=" ", flush=True)
        text = build_idf(source, setback_f, lead)
        runtime = lab.run_energyplus(text, args.output / "runs" / name)
        metrics = lab.parse_facility_and_readiness(
            args.output / "runs" / name,
            candidate=name,
            runtime=runtime,
            max_zones=None,
        )
        results.append(metrics)
        print(
            f"ready={metrics.ready} minF={metrics.min_ready_zone_f:.1f} "
            f"obj=${metrics.objective_usd:.2f}"
        )

    winner = lab.print_ranked(results)
    lab.write_results_csv(results, args.output / "grid_search_results.csv")
    lab.write_decision_json(
        args.output / "selected_plan.json",
        {
            "lesson": "day08",
            "model": SOURCE,
            "winner": None if winner is None else winner.candidate,
        },
    )


if __name__ == "__main__":
    main()
