"""Day 06 — demand-limit schedule grid on 5ZoneAirCooledDemandLimiting."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eplus_lab as lab

SOURCE = "5ZoneAirCooledDemandLimiting.idf"
LIMIT_SCH = "Limit Schedule"


def candidate_menu() -> list[tuple[str, float]]:
    # Peak demand caps in Watts during 08:00–20:00.
    return [
        ("LIMIT_OFF_9999999", 9_999_999.0),
        ("LIMIT_15kW", 15_000.0),
        ("LIMIT_12kW", 12_000.0),
        ("LIMIT_10kW", 10_000.0),
        ("LIMIT_8kW", 8_000.0),
    ]


def build_idf(source: str, peak_w: float) -> str:
    text = lab.replace_object(
        source,
        "Schedule:Compact",
        LIMIT_SCH,
        lab.demand_limit_schedule(LIMIT_SCH, peak_w),
    )
    text = lab.set_single_run_period(text, begin_month=7, begin_day=15, name="DEMAND LIMIT DAY")
    text = lab.ensure_weather_run(text)
    return lab.append_outputs(text, lab.DEFAULT_OUTPUTS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs" / "day06_demand_limiting",
    )
    args = parser.parse_args()

    source_path = lab.example_idf(SOURCE)
    source = source_path.read_text(encoding="utf-8", errors="replace")
    menu = candidate_menu()
    print("DAY 06 — DEMAND LIMITING GRID")
    print(f"Model: {SOURCE} | summer day Jul 15 | {len(menu)} runs")
    print("Readiness gate relaxed (cooling model) — rank by objective only.\n")

    results = []
    for index, (name, peak_w) in enumerate(menu, start=1):
        print(f"[{index}/{len(menu)}] {name}", end=" ", flush=True)
        text = build_idf(source, peak_w)
        runtime = lab.run_energyplus(text, args.output / "runs" / name)
        metrics = lab.parse_facility_and_readiness(
            args.output / "runs" / name,
            candidate=name,
            runtime=runtime,
            ready_min_f=-999.0,  # summer cooling lesson — do not gate on heating
        )
        metrics.ready = metrics.severe_errors == 0 and metrics.fatal_errors == 0
        results.append(metrics)
        print(
            f"peak={metrics.facility_peak_kw:.1f} kW "
            f"obj=${metrics.objective_usd:.2f} ({runtime:.1f}s)"
        )

    winner = lab.print_ranked(results)
    lab.write_results_csv(results, args.output / "grid_search_results.csv")
    lab.write_decision_json(
        args.output / "selected_plan.json",
        {
            "lesson": "day06",
            "model": SOURCE,
            "winner": None if winner is None else winner.candidate,
            "note": "Illustrative demand caps; stock DemandManager example",
        },
    )


if __name__ == "__main__":
    main()
