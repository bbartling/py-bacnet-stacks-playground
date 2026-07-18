from __future__ import annotations
import argparse, csv, json
from .runner import run_config
from .benchmark import calibration_metrics
from .registry import names
from . import algorithms  # noqa: F401

def _dump(data, pretty: bool):
    print(json.dumps(data, indent=2 if pretty else None, sort_keys=pretty))

def _read_column(path: str, column: str) -> list[float]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = csv.DictReader(f)
        return [float(r[column]) for r in rows]

def main():
    parser = argparse.ArgumentParser(prog="hvac-bench")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list")

    p_run = sub.add_parser("run")
    p_run.add_argument("config")
    p_run.add_argument("--pretty", action="store_true")

    p_bench = sub.add_parser("benchmark")
    p_bench.add_argument("actual_csv")
    p_bench.add_argument("modeled_csv")
    p_bench.add_argument("--actual-col", default="actual_kwh")
    p_bench.add_argument("--modeled-col", default="modeled_kwh")
    p_bench.add_argument("--parameters", type=int, default=1)
    p_bench.add_argument("--pretty", action="store_true")

    p_xlsx = sub.add_parser("inspect-xlsx")
    p_xlsx.add_argument("workbook")
    p_xlsx.add_argument("--pretty", action="store_true")

    args = parser.parse_args()
    if args.command == "list":
        _dump({"algorithms": names()}, True)
    elif args.command == "run":
        _dump(run_config(args.config), args.pretty)
    elif args.command == "benchmark":
        actual = _read_column(args.actual_csv, args.actual_col)
        modeled = _read_column(args.modeled_csv, args.modeled_col)
        _dump(calibration_metrics(actual, modeled, args.parameters), args.pretty)
    elif args.command == "inspect-xlsx":
        from .excel import inspect_workbook
        _dump(inspect_workbook(args.workbook), args.pretty)

if __name__ == "__main__":
    main()
