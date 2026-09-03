"""Vibe 23 residential heat-pump DSM CLI (native EnergyPlus)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .energyplus import (
    DEFAULT_DOCKER_IMAGE,
    DEFAULT_WINDOWS_ENERGYPLUS,
    energyplus_capability,
    inspect_energyplus_run,
    run_energyplus_smoke,
)
from .grid import GridDimension, enumerate_grid
from .residential.campaign import run_battery_grid, run_thermostat_grid
from .residential.constants import CLAIM_ASSUMPTIONS, CLAIM_MODEL, CLAIM_TARIFF
from .residential.dr import run_july_dr
from .residential.model import MODEL_IDF, equipment_provenance, find_denver_epw
from .residential.runner import run_residential_day
from .tariff import load_tariff


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _emit_json(value: Any, output: str | None = None) -> None:
    body = json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        print(f"wrote JSON -> {path}")
    else:
        print(body, end="")


def _residential_doctor(args: argparse.Namespace) -> None:
    from .energyplus import resolve_native_energyplus
    from .envfile import load_energyplus_env

    load_energyplus_env()
    cap = energyplus_capability(
        docker_image=args.docker_image,
        eplus_path=args.eplus_path,
    )
    epw = find_denver_epw(args.epw)
    native = resolve_native_energyplus(args.eplus_path)
    root = Path(os.environ["ENERGYPLUS_ROOT"]).expanduser() if os.environ.get("ENERGYPLUS_ROOT") else (
        native.parent if native else DEFAULT_WINDOWS_ENERGYPLUS.parent
    )
    datasets = root / "DataSets"
    result = {
        "schema": "vibe23.residential_doctor.v1",
        "ok": bool(cap.native_version),
        "native_required": True,
        "docker_required": False,
        "wsl_required": False,
        "platform": sys.platform,
        "env_energyplus_exe": os.environ.get("ENERGYPLUS_EXE"),
        "env_energyplus_root": os.environ.get("ENERGYPLUS_ROOT"),
        "env_energyplus_weather": os.environ.get("ENERGYPLUS_WEATHER"),
        "native_executable": cap.native_executable,
        "native_version": cap.native_version,
        "default_eplus_path": str(DEFAULT_WINDOWS_ENERGYPLUS),
        "datasets_path": str(datasets),
        "datasets_present": datasets.is_dir(),
        "rooftop_dataset": str(datasets / "RooftopPackagedHeatPump.idf"),
        "rooftop_dataset_present": (datasets / "RooftopPackagedHeatPump.idf").is_file(),
        "model_idf": str(MODEL_IDF),
        "model_idf_present": MODEL_IDF.is_file(),
        "epw": str(epw) if epw else None,
        "epw_present": bool(epw),
        "equipment": equipment_provenance(),
        "claim_model": CLAIM_MODEL,
        "claim_assumptions": CLAIM_ASSUMPTIONS,
        "claim_tariff": CLAIM_TARIFF,
        "capability": cap.to_dict(),
        "note": "Copy .env.example to .env. Docker/WSL is optional; native EnergyPlus is used when present. Streamlit Community Cloud runs fixture-only demo mode.",
    }
    _emit_json(result, args.out)
    if not result["ok"]:
        raise SystemExit(2)


def _residential_smoke(args: argparse.Namespace) -> None:
    season = args.season.lower()
    month, day = (1, 15) if season in {"jan", "january", "winter"} else (7, 15)
    out_dir = Path(args.output_dir) if args.output_dir else Path("campaigns/runs/residential_smoke") / season
    result = run_residential_day(
        Path(args.idf) if args.idf else MODEL_IDF,
        epw=args.epw,
        output_dir=out_dir,
        eplus_path=args.eplus_path,
        month=month,
        day=day,
    )
    slim = {k: v for k, v in result.items() if k not in {"facility_kw", "zone_temp_f", "inspection"}}
    slim["n_facility"] = len(result.get("facility_kw") or [])
    slim["n_zone_temp"] = len(result.get("zone_temp_f") or [])
    _emit_json(slim, args.out)
    if not result.get("soft_ok"):
        raise SystemExit(2)


def _residential_dr(args: argparse.Namespace) -> None:
    if args.season.lower() not in {"summer", "jul", "july"}:
        raise SystemExit("residential-dr currently supports --season summer only")
    root = Path(args.output_dir) if args.output_dir else Path("reports/dr/summer")
    result = run_july_dr(output_root=root, eplus_path=args.eplus_path, idf=args.idf)
    slim = {
        "schema": result["schema"],
        "action": result["action"],
        "comparison": result["comparison"],
        "plot": result["plot"],
        "baseline_ok": result["baseline"].get("soft_ok"),
        "event_ok": result["event"].get("soft_ok"),
        "claim_model": result["claim_model"],
    }
    _emit_json(slim, args.out)


def _residential_grid(args: argparse.Namespace) -> None:
    root = Path(args.output_dir) if args.output_dir else Path("campaigns/runs/residential_grid") / args.season
    result = run_thermostat_grid(
        season=args.season,
        output_root=root,
        eplus_path=args.eplus_path,
        max_candidates=args.max_candidates,
        idf=args.idf,
    )
    slim = {k: v for k, v in result.items() if k != "baseline"}
    _emit_json(slim, args.out)


def _residential_battery_grid(args: argparse.Namespace) -> None:
    root = (
        Path(args.output_dir)
        if args.output_dir
        else Path("campaigns/runs/residential_battery_grid") / args.season
    )
    result = run_battery_grid(
        season=args.season,
        output_root=root,
        eplus_path=args.eplus_path,
        max_candidates=args.max_candidates,
        idf=args.idf,
    )
    slim = {k: v for k, v in result.items() if k != "thermal"}
    slim["thermal_winner"] = (result.get("thermal") or {}).get("winner_schedule")
    _emit_json(slim, args.out)


def _residential_report(args: argparse.Namespace) -> None:
    root = Path(args.root) if args.root else Path("campaigns/runs")
    report = {
        "schema": "vibe23.residential_report.v1",
        "claim_model": CLAIM_MODEL,
        "claim_assumptions": CLAIM_ASSUMPTIONS,
        "claim_tariff": CLAIM_TARIFF,
        "equipment": equipment_provenance(),
        "artifacts": {},
    }
    for name in (
        "residential_smoke",
        "residential_grid",
        "residential_battery_grid",
    ):
        path = root / name
        report["artifacts"][name] = {"exists": path.exists(), "path": str(path)}
    dr = Path("reports/dr")
    report["artifacts"]["dr"] = {"exists": dr.exists(), "path": str(dr)}
    compute_host = Path("reports/compute/host.json")
    report["artifacts"]["compute_host"] = {
        "exists": compute_host.exists(),
        "path": str(compute_host),
    }
    _emit_json(report, args.out)


def _inspect_tariff(args: argparse.Namespace) -> None:
    _emit_json(load_tariff(Path(args.tariff)).to_dict(), args.out)


def _enumerate_grid(args: argparse.Namespace) -> None:
    raw = json.loads(Path(args.grid).read_text(encoding="utf-8"))
    if raw.get("schema") != "vibe23.grid_declaration.v1":
        raise ValueError("grid schema must be vibe23.grid_declaration.v1")
    dimensions = []
    for index, item in enumerate(raw.get("dimensions") or []):
        if not isinstance(item, dict):
            raise ValueError(f"dimensions[{index}] must be an object")
        dimensions.append(GridDimension(str(item.get("name") or ""), tuple(item.get("values") or ())))
    candidates = enumerate_grid(dimensions)
    result = {
        "schema": "vibe23.grid_enumeration.v1",
        "claim_status": "ENUMERATION_ONLY_NOT_RUN",
        "source_grid": str(Path(args.grid)),
        "candidate_count": len(candidates),
        "candidates": [candidate.to_dict() for candidate in candidates],
        "warning": "Candidate enumeration is not an EnergyPlus simulation or DSM result.",
    }
    _emit_json(result, args.out)


def _energyplus_doctor(args: argparse.Namespace) -> None:
    result = energyplus_capability(docker_image=args.docker_image, eplus_path=args.eplus_path)
    _emit_json(result.to_dict(), args.out)


def _run_eplus_smoke(args: argparse.Namespace) -> None:
    result = run_energyplus_smoke(
        Path(args.idf),
        Path(args.epw),
        Path(args.output_dir),
        engine=args.engine,
        docker_image=args.docker_image,
        timeout_seconds=args.timeout_seconds,
        eplus_path=args.eplus_path,
    )
    _emit_json(result, args.out)


def _inspect_eplus_run(args: argparse.Namespace) -> None:
    result = inspect_energyplus_run(
        Path(args.run_dir),
        idf=Path(args.idf) if args.idf else None,
        epw=Path(args.epw) if args.epw else None,
        energyplus_version=args.energyplus_version,
        require_zero_warnings=False,
    )
    _emit_json(result, args.out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vibe23",
        description="Residential heat-pump EnergyPlus DSM laboratory (native Windows)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("residential-doctor", help="Probe native EnergyPlus + model/EPW readiness")
    p.add_argument("--eplus-path", default=str(DEFAULT_WINDOWS_ENERGYPLUS))
    p.add_argument("--epw", help="Optional EPW override")
    p.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    p.add_argument("--out", help="Optional JSON report")
    p.set_defaults(func=_residential_doctor)

    p = sub.add_parser("residential-smoke", help="Run Jan or Jul residential baseline day")
    p.add_argument("--season", choices=["jan", "jul", "winter", "summer"], default="jul")
    p.add_argument("--idf")
    p.add_argument("--epw")
    p.add_argument("--eplus-path")
    p.add_argument("--output-dir")
    p.add_argument("--out")
    p.set_defaults(func=_residential_smoke)

    p = sub.add_parser("residential-dr", help="July hot-afternoon DR demo")
    p.add_argument("--season", default="summer")
    p.add_argument("--idf")
    p.add_argument("--eplus-path")
    p.add_argument("--output-dir")
    p.add_argument("--out")
    p.set_defaults(func=_residential_dr)

    p = sub.add_parser("residential-grid", help="Thermostat TOU grid search")
    p.add_argument("--season", choices=["winter", "summer"], required=True)
    p.add_argument("--max-candidates", type=int, default=5)
    p.add_argument("--idf")
    p.add_argument("--eplus-path")
    p.add_argument("--output-dir")
    p.add_argument("--out")
    p.set_defaults(func=_residential_grid)

    p = sub.add_parser("residential-battery-grid", help="Thermal + battery co-optimization")
    p.add_argument("--season", choices=["winter", "summer"], required=True)
    p.add_argument("--max-candidates", type=int, default=3)
    p.add_argument("--idf")
    p.add_argument("--eplus-path")
    p.add_argument("--output-dir")
    p.add_argument("--out")
    p.set_defaults(func=_residential_battery_grid)

    p = sub.add_parser("residential-report", help="Summarize residential campaign artifacts")
    p.add_argument("--root", default="campaigns/runs")
    p.add_argument("--out")
    p.set_defaults(func=_residential_report)

    p = sub.add_parser("inspect-tariff", help="Validate a tariff contract JSON")
    p.add_argument("--tariff", required=True)
    p.add_argument("--out")
    p.set_defaults(func=_inspect_tariff)

    p = sub.add_parser("enumerate-grid", help="Deterministically enumerate a grid without simulation")
    p.add_argument("--grid", required=True)
    p.add_argument("--out")
    p.set_defaults(func=_enumerate_grid)

    p = sub.add_parser("energyplus-doctor", help="Probe native/Docker EnergyPlus capability")
    p.add_argument("--eplus-path")
    p.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    p.add_argument("--out")
    p.set_defaults(func=_energyplus_doctor)

    p = sub.add_parser("run-eplus-smoke", help="Run a hash-bearing EnergyPlus engine smoke test")
    p.add_argument("--idf", required=True)
    p.add_argument("--epw", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--engine", choices=["auto", "native", "docker"], default="native")
    p.add_argument("--eplus-path")
    p.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    p.add_argument("--timeout-seconds", type=int, default=3600)
    p.add_argument("--out")
    p.set_defaults(func=_run_eplus_smoke)

    p = sub.add_parser("inspect-eplus-run", help="Inspect an existing EnergyPlus run directory")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--idf")
    p.add_argument("--epw")
    p.add_argument("--energyplus-version")
    p.add_argument("--out")
    p.set_defaults(func=_inspect_eplus_run)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
