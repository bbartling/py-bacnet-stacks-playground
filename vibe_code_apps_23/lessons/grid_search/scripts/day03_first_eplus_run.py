"""Day 03 — first real EnergyPlus run on a stock 1-zone example."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eplus_lab as lab


def prepare_idf(source: str) -> str:
    text = lab.set_single_run_period(source, begin_month=1, begin_day=14)
    text = lab.force_run_period_only(text)
    text = lab.append_outputs(
        text,
        [
            "Output:Variable,*,Site Outdoor Air Drybulb Temperature,Timestep;",
            "Output:Variable,*,Zone Mean Air Temperature,Timestep;",
        ],
    )
    return text


def summarize(run_dir: Path) -> dict:
    csv_path = run_dir / "eplusout.csv"
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        oat_col = next(
            (n for n in fieldnames if "OUTDOOR AIR DRYBULB" in n.upper()), None
        )
        zone_cols = [
            n for n in fieldnames if "ZONE MEAN AIR TEMPERATURE" in n.upper()
        ]
        rows = list(reader)

    oats = [float(r[oat_col]) for r in rows if oat_col and r.get(oat_col)]
    zones = []
    for col in zone_cols:
        zones.extend(float(r[col]) for r in rows if r.get(col))
    severe, fatal = lab.count_err_markers(run_dir / "eplusout.err")
    return {
        "rows": len(rows),
        "oat_min_c": min(oats) if oats else None,
        "oat_max_c": max(oats) if oats else None,
        "zone_min_c": min(zones) if zones else None,
        "zone_max_c": max(zones) if zones else None,
        "severe_errors": severe,
        "fatal_errors": fatal,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs" / "day03_first_eplus",
    )
    args = parser.parse_args()

    source_path = lab.example_idf("1ZoneUncontrolled.idf")
    print("DAY 03 — FIRST ENERGYPLUS RUN")
    print(f"Model: {source_path.name}")
    print("NOT A GRID SEARCH YET — prove the toolchain works.\n")

    text = prepare_idf(source_path.read_text(encoding="utf-8", errors="replace"))
    runtime = lab.run_energyplus(text, args.output / "runs" / "BASELINE")
    summary = summarize(args.output / "runs" / "BASELINE")
    lab.write_decision_json(
        args.output / "summary.json",
        {
            "lesson": "day03",
            "model": source_path.name,
            "runtime_seconds": round(runtime, 2),
            **summary,
            "warning": "EDUCATIONAL — stock ExampleFile — no BACnet",
        },
    )
    print(f"Runtime: {runtime:.1f}s")
    print(f"CSV rows: {summary['rows']}")
    if summary["oat_min_c"] is not None:
        print(
            f"OAT range C: {summary['oat_min_c']:.1f} .. {summary['oat_max_c']:.1f}"
        )
    if summary["zone_min_c"] is not None:
        print(
            f"Zone mean C: {summary['zone_min_c']:.1f} .. {summary['zone_max_c']:.1f}"
        )
    print(f"Severe/Fatal: {summary['severe_errors']}/{summary['fatal_errors']}")
    print(f"Wrote {args.output / 'summary.json'}")


if __name__ == "__main__":
    main()
