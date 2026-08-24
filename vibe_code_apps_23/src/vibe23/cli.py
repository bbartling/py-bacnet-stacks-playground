from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .download import download_dataset
from .grid import GridDimension, enumerate_grid, rllib_energyplus_adapter_provenance
from .ingest import aggregate_power_kw, build_inventory, load_point_csv
from .metrics import score_calibration
from .model import read_parameter_ledger, render_idf_seed, validate_parameter_ledger
from .openfdd import build_openfdd_package
from .rllib_adapter import inspect_rllib_energyplus_checkout
from .tariff import load_tariff


def _emit_json(value: Any, output: str | None = None) -> None:
    body = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        print(f"wrote JSON -> {path}")
    else:
        print(body, end="")


def _download(args: argparse.Namespace) -> None:
    result = download_dataset(
        Path(args.data_dir),
        force=args.force,
        source_release=Path(args.source_release) if args.source_release else None,
        download_url=args.download_url,
    )
    _emit_json(result, args.out)


def _inventory(args: argparse.Namespace) -> None:
    frame = build_inventory(Path(args.root))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    print(f"wrote {len(frame)} rows -> {out}")


def _aggregate(args: argparse.Namespace) -> None:
    series = load_point_csv(Path(args.csv), args.timestamp_column, args.value_column)
    frame = aggregate_power_kw(series, args.rule, max_gap_factor=args.max_gap_factor)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index_label="timestamp")
    print(f"wrote {len(frame)} rows -> {out}")


def _score(args: argparse.Namespace) -> None:
    frame = pd.read_csv(args.csv)
    result = score_calibration(
        frame[args.measured_column], frame[args.simulated_column], args.interval, p=args.parameters
    )
    payload = result.as_dict()
    payload["metric_threshold_passes"] = payload.pop("passes")
    payload["minimum_complete_months"] = 12 if args.interval == "monthly" else None
    payload["minimum_complete_month_count_passes"] = (
        result.n >= 12 if args.interval == "monthly" else None
    )
    payload["calibration_claim_eligible"] = False
    payload["claim_reason"] = (
        "Standalone metrics are diagnostic only. Use the provenance-bearing calibration scorecard; "
        "monthly claims also require at least 12 complete paired months, and hourly claims require physics gates."
    )
    _emit_json(payload, args.out)


def _export_openfdd(args: argparse.Namespace) -> None:
    result = build_openfdd_package(Path(args.mapping), Path(args.raw_root), Path(args.out))
    _emit_json(result, args.report)


def _validate_ledger(args: argparse.Namespace) -> None:
    result = validate_parameter_ledger(read_parameter_ledger(Path(args.ledger)))
    result["claim_boundary"] = "Ledger validation does not prove that an EnergyPlus model runs or is calibrated."
    _emit_json(result, args.out)


def _parse_replacements(values: list[str]) -> dict[str, str]:
    replacements: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Replacement must be TOKEN=VALUE: {item!r}")
        token, value = item.split("=", 1)
        token = token.strip()
        if not token or not value.strip():
            raise ValueError(f"Replacement must contain a non-empty token and value: {item!r}")
        if token in replacements:
            raise ValueError(f"Replacement token supplied more than once: {token}")
        replacements[token] = value
    return replacements


def _render_seed(args: argparse.Namespace) -> None:
    destination = render_idf_seed(Path(args.template), Path(args.out), _parse_replacements(args.set))
    print(f"rendered CALIBRATION_BOOTSTRAP seed -> {destination}")


def _inspect_rllib(args: argparse.Namespace) -> None:
    _emit_json(inspect_rllib_energyplus_checkout(Path(args.root)), args.out)


def _rllib_provenance(args: argparse.Namespace) -> None:
    _emit_json(rllib_energyplus_adapter_provenance(), args.out)


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibe23", description="LBNL Building 59 calibration utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("download", help="Acquire and safely extract the Dryad dataset")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--source-release", help="Manual Dryad release directory, wrapper ZIP, or Building_59.zip")
    p.add_argument("--download-url", help="Authorized Dryad-compatible download URL override")
    p.add_argument("--force", action="store_true")
    p.add_argument("--out", help="Optional acquisition report JSON")
    p.set_defaults(func=_download)

    p = sub.add_parser("inventory", help="Inventory CSV files and candidate columns")
    p.add_argument("--root", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=_inventory)

    p = sub.add_parser("aggregate-power", help="Integrate a sampled kW point into energy/peak targets")
    p.add_argument("--csv", required=True)
    p.add_argument("--timestamp-column")
    p.add_argument("--value-column")
    p.add_argument("--rule", default="1h")
    p.add_argument("--max-gap-factor", type=float, default=4.0)
    p.add_argument("--out", required=True)
    p.set_defaults(func=_aggregate)

    p = sub.add_parser("score", help="Compute Guideline-14-style calibration metrics")
    p.add_argument("--csv", required=True)
    p.add_argument("--measured-column", default="measured")
    p.add_argument("--simulated-column", default="simulated")
    p.add_argument("--interval", choices=["monthly", "hourly"], required=True)
    p.add_argument("--parameters", type=int, default=1)
    p.add_argument("--out", help="Optional metric JSON")
    p.set_defaults(func=_score)

    p = sub.add_parser("export-openfdd", help="Build an openfdd_package_v1 ZIP from explicit bindings")
    p.add_argument("--mapping", required=True)
    p.add_argument("--raw-root", required=True)
    p.add_argument("--out", required=True, help="Destination ZIP")
    p.add_argument("--report", help="Optional adapter report JSON")
    p.set_defaults(func=_export_openfdd)

    p = sub.add_parser("validate-model-ledger", help="Validate parameter evidence and report freeze blockers")
    p.add_argument("--ledger", required=True)
    p.add_argument("--out", help="Optional validation JSON")
    p.set_defaults(func=_validate_ledger)

    p = sub.add_parser("render-model-seed", help="Render explicit tokens in the non-runnable seed template")
    p.add_argument("--template", default="model/b59_seed.idf.template")
    p.add_argument("--set", action="append", default=[], metavar="TOKEN=VALUE", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=_render_seed)

    p = sub.add_parser("inspect-rllib", help="Verify the reviewed airboxlab/rllib-energyplus checkout pin")
    p.add_argument("--root", required=True)
    p.add_argument("--out", help="Optional inspection JSON")
    p.set_defaults(func=_inspect_rllib)

    p = sub.add_parser("rllib-provenance", help="Print the reviewed upstream repository and pin")
    p.add_argument("--out", help="Optional provenance JSON")
    p.set_defaults(func=_rllib_provenance)

    p = sub.add_parser("inspect-tariff", help="Validate a tariff contract and print its evidence gates")
    p.add_argument("--tariff", required=True)
    p.add_argument("--out", help="Optional tariff report JSON")
    p.set_defaults(func=_inspect_tariff)

    p = sub.add_parser("enumerate-grid", help="Deterministically enumerate a grid without simulation")
    p.add_argument("--grid", required=True)
    p.add_argument("--out", help="Optional candidate manifest JSON")
    p.set_defaults(func=_enumerate_grid)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
