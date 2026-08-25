"""Day 07 — night ventilation comparison (NightVent1 vs NightVent2) + setback grid."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eplus_lab as lab

OCCUPIED_C = 21.1
SCHEDULE_CANDIDATES = ("Htg-SetP-Sch", "HTG-SETP-SCH")


def pick_heating_schedule(text: str) -> str:
    for name in SCHEDULE_CANDIDATES:
        if re_search_schedule(text, name):
            return name
    raise RuntimeError("No known heating setpoint schedule found")


def re_search_schedule(text: str, name: str) -> bool:
    import re

    return re.search(rf"(?im)^\s*{re.escape(name)}\s*,", text) is not None


def build_idf(source: str, schedule: str, setback_f: float, lead: int) -> str:
    setback_c = lab.f_to_c(setback_f)
    text = lab.replace_object(
        source,
        "Schedule:Compact",
        schedule,
        lab.heating_setpoint_schedule(
            schedule,
            setback_c=setback_c,
            occupied_c=OCCUPIED_C,
            recovery_hour=8 - lead,
            occupied_end_hour=18,
        ),
    )
    text = lab.set_single_run_period(text, begin_month=7, begin_day=20, name="NIGHTVENT DAY")
    # NightVent examples already size in-file; keep sizing, force weather run.
    text = lab.ensure_weather_run(text, plant_sizing=False, sizing_periods=False)
    return lab.append_outputs(text, lab.DEFAULT_OUTPUTS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs" / "day07_night_vent",
    )
    args = parser.parse_args()

    # NightVent1 = base case (no NV); NightVent2 = Ventilation object night venting.
    models = (
        ("NO_NV", "5ZoneNightVent1.idf"),
        ("WITH_NV", "5ZoneNightVent2.idf"),
    )
    setbacks = (68.0, 72.0)  # cooling-season occupied heat floors / mild setpoints
    leads = (0, 1)

    print("DAY 07 — NIGHT VENTILATION + SMALL SETPOINT GRID")
    print("Compare stock NightVent1 (off) vs NightVent2 (on) for Jul 20\n")

    results = []
    for model_tag, filename in models:
        source_path = lab.example_idf(filename)
        source = source_path.read_text(encoding="utf-8", errors="replace")
        schedule = pick_heating_schedule(source)
        for setback_f in setbacks:
            for lead in leads:
                name = f"{model_tag}_SB{setback_f:.0f}_L{lead}"
                print(f"  {name}", end=" ", flush=True)
                text = build_idf(source, schedule, setback_f, lead)
                runtime = lab.run_energyplus(text, args.output / "runs" / name)
                metrics = lab.parse_facility_and_readiness(
                    args.output / "runs" / name,
                    candidate=name,
                    runtime=runtime,
                    ready_min_f=-999.0,
                )
                metrics.ready = metrics.severe_errors == 0 and metrics.fatal_errors == 0
                metrics.extra = {"model": filename, "night_vent": model_tag}
                results.append(metrics)
                print(f"kWh={metrics.electricity_kwh:.1f} peak={metrics.facility_peak_kw:.1f}")

    winner = lab.print_ranked(results)
    lab.write_results_csv(results, args.output / "grid_search_results.csv")
    lab.write_decision_json(
        args.output / "selected_plan.json",
        {
            "lesson": "day07",
            "winner": None if winner is None else winner.candidate,
            "note": "NightVent1 is documented as the no-NV base case",
        },
    )


if __name__ == "__main__":
    main()
