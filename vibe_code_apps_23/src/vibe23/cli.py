from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .charts import build_calibration_chart_pack, build_gl14_campaign_progress
from .download import download_dataset
from .energyplus import (
    DEFAULT_DOCKER_IMAGE,
    energyplus_capability,
    inspect_energyplus_run,
    run_energyplus_smoke,
)
from .grid import GridDimension, enumerate_grid, rllib_energyplus_adapter_provenance
from .ingest import aggregate_power_kw, build_inventory, load_point_csv
from .metrics import score_calibration
from .model import read_parameter_ledger, render_idf_seed, validate_parameter_ledger
from .openfdd import build_openfdd_package
from .rllib_adapter import inspect_rllib_energyplus_checkout
from .tariff import load_tariff


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _reject_same_path(output: str | Path | None, *inputs: str | Path | None) -> None:
    if output is None:
        return
    target = _resolved(output)
    for source in inputs:
        if source is not None and target == _resolved(source):
            raise ValueError(f"output must not overwrite input artifact: {target}")


def _reject_within(output: str | Path | None, protected_root: str | Path, *, label: str) -> None:
    if output is None:
        return
    target = _resolved(output)
    root = _resolved(protected_root)
    if target == root or root in target.parents:
        raise ValueError(f"output must be outside {label}: {root}")


def _reject_input_inside_output(input_path: str | Path, output_root: str | Path, *, label: str) -> None:
    source = _resolved(input_path)
    root = _resolved(output_root)
    if source == root or root in source.parents:
        raise ValueError(f"{label} must not contain the input artifact: {source}")


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
    _reject_same_path(args.out, args.source_release)
    result = download_dataset(
        Path(args.data_dir),
        force=args.force,
        source_release=Path(args.source_release) if args.source_release else None,
        download_url=args.download_url,
    )
    _emit_json(result, args.out)


def _inventory(args: argparse.Namespace) -> None:
    _reject_within(args.out, args.root, label="the inventory source root")
    frame = build_inventory(Path(args.root))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    print(f"wrote {len(frame)} rows -> {out}")


def _aggregate(args: argparse.Namespace) -> None:
    _reject_same_path(args.out, args.csv)
    series = load_point_csv(Path(args.csv), args.timestamp_column, args.value_column)
    frame = aggregate_power_kw(series, args.rule, max_gap_factor=args.max_gap_factor)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index_label="timestamp")
    print(f"wrote {len(frame)} rows -> {out}")


def _score(args: argparse.Namespace) -> None:
    _reject_same_path(args.out, args.csv)
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
    _reject_same_path(args.out, args.mapping)
    _reject_same_path(args.report, args.mapping, args.out)
    _reject_within(args.out, args.raw_root, label="the immutable raw-data root")
    _reject_within(args.report, args.raw_root, label="the immutable raw-data root")
    result = build_openfdd_package(Path(args.mapping), Path(args.raw_root), Path(args.out))
    _emit_json(result, args.report)


def _validate_ledger(args: argparse.Namespace) -> None:
    _reject_same_path(args.out, args.ledger)
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
    _reject_same_path(args.out, args.template)
    destination = render_idf_seed(Path(args.template), Path(args.out), _parse_replacements(args.set))
    print(f"rendered CALIBRATION_BOOTSTRAP seed -> {destination}")


def _inspect_rllib(args: argparse.Namespace) -> None:
    _reject_within(args.out, args.root, label="the inspected RLlib checkout")
    _emit_json(inspect_rllib_energyplus_checkout(Path(args.root)), args.out)


def _rllib_provenance(args: argparse.Namespace) -> None:
    _emit_json(rllib_energyplus_adapter_provenance(), args.out)


def _inspect_tariff(args: argparse.Namespace) -> None:
    _reject_same_path(args.out, args.tariff)
    _emit_json(load_tariff(Path(args.tariff)).to_dict(), args.out)


def _enumerate_grid(args: argparse.Namespace) -> None:
    _reject_same_path(args.out, args.grid)
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
    result = energyplus_capability(
        docker_image=args.docker_image,
        mcp_vendor_path=Path(args.mcp_vendor) if args.mcp_vendor else None,
    )
    _emit_json(result.to_dict(), args.out)


def _run_eplus_smoke(args: argparse.Namespace) -> None:
    _reject_within(args.out, args.output_dir, label="the EnergyPlus run directory")
    _reject_same_path(args.out, args.idf, args.epw)
    result = run_energyplus_smoke(
        Path(args.idf),
        Path(args.epw),
        Path(args.output_dir),
        engine=args.engine,
        docker_image=args.docker_image,
        timeout_seconds=args.timeout_seconds,
    )
    _emit_json(result, args.out)


def _inspect_eplus_run(args: argparse.Namespace) -> None:
    _reject_within(args.out, args.run_dir, label="the EnergyPlus evidence directory")
    _reject_same_path(args.out, args.idf, args.epw)
    result = inspect_energyplus_run(
        Path(args.run_dir),
        idf=Path(args.idf) if args.idf else None,
        epw=Path(args.epw) if args.epw else None,
        energyplus_version=args.energyplus_version,
    )
    _emit_json(result, args.out)


def _plot_calibration(args: argparse.Namespace) -> None:
    _reject_input_inside_output(args.csv, args.output_dir, label="the chart output directory")
    _reject_within(args.out, args.output_dir, label="the chart output directory")
    _reject_same_path(args.out, args.csv)
    result = build_calibration_chart_pack(
        Path(args.csv),
        Path(args.output_dir),
        timestamp_column=args.timestamp_column,
        measured_column=args.measured_column,
        simulated_column=args.simulated_column,
        data_kind=args.data_kind,
        unit=args.unit,
        energy_unit=args.energy_unit,
        interval_hours=args.interval_hours,
        timezone=args.timezone,
        title=args.title,
        parameters=args.parameters,
    )
    _emit_json(result, args.out)


def _plot_calibration_campaign(args: argparse.Namespace) -> None:
    _reject_input_inside_output(
        args.campaign_log, args.output_dir, label="the campaign chart output directory"
    )
    _reject_within(args.out, args.output_dir, label="the campaign chart output directory")
    _reject_same_path(args.out, args.campaign_log)
    result = build_gl14_campaign_progress(
        Path(args.campaign_log),
        Path(args.output_dir),
        title=args.title,
    )
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

    p = sub.add_parser("energyplus-doctor", help="Probe native, Docker, and EnergyPlus-MCP prerequisites")
    p.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    p.add_argument("--mcp-vendor", help="Optional LBNL EnergyPlus-MCP checkout to verify")
    p.add_argument("--out", help="Optional capability report JSON")
    p.set_defaults(func=_energyplus_doctor)

    p = sub.add_parser("run-eplus-smoke", help="Run a hash-bearing EnergyPlus engine smoke test")
    p.add_argument("--idf", required=True)
    p.add_argument("--epw", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--engine", choices=["auto", "native", "docker"], default="auto")
    p.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    p.add_argument("--timeout-seconds", type=int, default=3600)
    p.add_argument("--out", help="Optional second copy of the run manifest JSON")
    p.set_defaults(func=_run_eplus_smoke)

    p = sub.add_parser(
        "inspect-eplus-run",
        help="Apply the hash-bound Building 59 calibration-ready evidence gate without rerunning",
    )
    p.add_argument("--run-dir", required=True)
    p.add_argument("--idf", help="Optional source IDF to hash")
    p.add_argument("--epw", help="Optional source EPW to hash")
    p.add_argument("--energyplus-version", help="Pinned/runtime version recorded for the run")
    p.add_argument("--out", help="Optional inspection JSON")
    p.set_defaults(func=_inspect_eplus_run)

    p = sub.add_parser("plot-calibration", help="Publish hashed measured-vs-EnergyPlus chart diagnostics")
    p.add_argument("--csv", required=True, help="Paired timestamp/measured/simulated CSV")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--timestamp-column", default="timestamp")
    p.add_argument("--measured-column", default="measured")
    p.add_argument("--simulated-column", default="simulated")
    p.add_argument("--data-kind", choices=["mean_power", "interval_energy"], default="mean_power")
    p.add_argument("--unit", default="kW", help="Native paired-value unit")
    p.add_argument("--energy-unit", default="kWh", help="Monthly integrated energy unit")
    p.add_argument("--interval-hours", type=float, help="Override interval duration for mean-power integration")
    p.add_argument("--timezone", help="Explicit IANA timezone for naive or mixed-DST-offset timestamps")
    p.add_argument("--parameters", type=int, default=1, help="Fitted parameter count p used in metrics")
    p.add_argument("--title", default="LBNL Building 59 calibration")
    p.add_argument("--out", help="Optional second copy of chart manifest JSON")
    p.set_defaults(func=_plot_calibration)

    p = sub.add_parser("plot-calibration-campaign", help="Plot monthly GL14 metrics across hashed iterations")
    p.add_argument("--campaign-log", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--title", default="LBNL Building 59 monthly calibration campaign")
    p.add_argument("--out", help="Optional second copy of campaign chart manifest JSON")
    p.set_defaults(func=_plot_calibration_campaign)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
