"""``wattlab notebook`` — build / prefill / validate / summarize ECM Excel notebooks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_profile(args: argparse.Namespace) -> dict[str, Any]:
    profile = _load_json(getattr(args, "profile", None))
    answers = _load_json(getattr(args, "answers", None))
    for k, v in answers.items():
        if profile.get(k) is None and v is not None:
            profile[k] = v
    overrides = {}
    if getattr(args, "area", None):
        overrides["conditioned_floor_area_ft2"] = float(args.area)
    if getattr(args, "cooling_tons", None):
        overrides["cooling_tons"] = float(args.cooling_tons)
    if getattr(args, "fan_hp", None):
        overrides["fan_hp"] = float(args.fan_hp)
    profile.update(overrides)
    return profile


def _load_report(run_dir: Path | None) -> dict[str, Any]:
    if run_dir is None:
        return {}
    root = Path(run_dir)
    for name in ("report.json", "wattlab_report.json", "calibration_scorecard.json"):
        p = root / name
        if p.is_file():
            return _load_json(p)
    return {}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="wattlab notebook",
        description="ECM engineering notebooks (Excel) — ESCO vs EnergyPlus + ROI",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list-packages", help="List least→radical notebook packages")
    sp.set_defaults(func=_cmd_list)

    bp = sub.add_parser("build", help="Build one package workbook + manifest")
    bp.add_argument("--package", required=True, help="Notebook package id (e.g. controls_first)")
    bp.add_argument("--out", type=Path, required=True, help="Output directory")
    bp.add_argument("--profile", type=Path, help="building profile JSON")
    bp.add_argument("--answers", type=Path, help="answers.json (merged into profile)")
    bp.add_argument("--from-run", type=Path, help="Twin run dir with savings_by_measure")
    bp.add_argument("--area", type=float, help="Override floor area ft²")
    bp.add_argument("--cooling-tons", type=float, dest="cooling_tons")
    bp.add_argument("--fan-hp", type=float, dest="fan_hp")
    bp.add_argument("--elec-rate", type=float, dest="elec_rate")
    bp.add_argument("--gas-rate", type=float, dest="gas_rate")
    bp.add_argument("--no-manifest", action="store_true")
    bp.set_defaults(func=_cmd_build)

    pp = sub.add_parser("prefill", help="Rewrite Inputs yellow cells on an existing workbook")
    pp.add_argument("--xlsx", type=Path, required=True)
    pp.add_argument("--profile", type=Path)
    pp.add_argument("--answers", type=Path)
    pp.add_argument("--from-run", type=Path)
    pp.add_argument("--area", type=float)
    pp.add_argument("--cooling-tons", type=float, dest="cooling_tons")
    pp.add_argument("--fan-hp", type=float, dest="fan_hp")
    pp.add_argument("--elec-rate", type=float, dest="elec_rate")
    pp.add_argument("--gas-rate", type=float, dest="gas_rate")
    pp.set_defaults(func=_cmd_prefill)

    vp = sub.add_parser("validate", help="Check required sheets + named ranges")
    vp.add_argument("--xlsx", type=Path, required=True)
    vp.set_defaults(func=_cmd_validate)

    sm = sub.add_parser("summarize", help="Write / print notebook_manifest.json")
    sm.add_argument("--xlsx", type=Path, required=True)
    sm.add_argument("--write", action="store_true", help="Write sidecar next to xlsx")
    sm.set_defaults(func=_cmd_summarize)

    rc = sub.add_parser(
        "refresh-caches",
        help="Recompute npv_usd_at_build from Inputs without wiping formulas (BUG-044)",
    )
    rc.add_argument("--xlsx", type=Path, required=True)
    rc.set_defaults(func=_cmd_refresh)

    sf = sub.add_parser("show-formulas", help="Dump Excel formula cells as JSON (BUG-044)")
    sf.add_argument("--xlsx", type=Path, required=True)
    sf.add_argument("--sheet", type=str, default=None, help="Limit to one sheet (e.g. ROI_Capital)")
    sf.set_defaults(func=_cmd_show_formulas)

    tp = sub.add_parser("write-template", help="Write scaffold template xlsx under templates/")
    tp.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Default: wattlab/notebooks/templates/ecm_package_v1.xlsx",
    )
    tp.set_defaults(func=_cmd_template)

    args = p.parse_args(argv)
    return int(args.func(args) or 0)


def _cmd_list(_args: argparse.Namespace) -> int:
    from wattlab.notebooks.packages import list_notebook_packages

    rows = [
        {
            "id": p.id,
            "rank": p.rank,
            "label": p.label,
            "n_measures": len(p.measure_ids),
            "catalog_package": p.catalog_package,
        }
        for p in list_notebook_packages()
    ]
    print(json.dumps(rows, indent=2))
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    from wattlab.notebooks.builder import build_and_save_notebook

    profile = _load_profile(args)
    overrides: dict[str, Any] = {}
    if args.elec_rate is not None:
        overrides["elec_rate"] = float(args.elec_rate)
    if args.gas_rate is not None:
        overrides["gas_rate"] = float(args.gas_rate)
    report = _load_report(args.from_run)
    written = build_and_save_notebook(
        args.package,
        args.out,
        profile=profile,
        report=report,
        input_overrides=overrides or None,
        write_manifest=not args.no_manifest,
    )
    print(json.dumps({k: str(v) for k, v in written.items()}, indent=2))
    return 0


def _cmd_prefill(args: argparse.Namespace) -> int:
    """Patch Inputs yellow cells in-place — never rebuilds (BUG-030)."""
    from wattlab.notebooks.builder import prefill_notebook_inputs

    if not args.xlsx.is_file():
        print(f"missing workbook: {args.xlsx}", file=sys.stderr)
        return 2

    overrides: dict[str, Any] = {}
    # Explicit keys from profile / answers JSON only (no default fill)
    for src in (_load_json(getattr(args, "profile", None)), _load_json(getattr(args, "answers", None))):
        for k, v in src.items():
            if v is None:
                continue
            if k in (
                "conditioned_floor_area_ft2",
                "floor_area_ft2",
                "area_ft2",
                "cooling_tons",
                "fan_hp",
                "supply_fan_hp",
                "elec_rate",
                "gas_rate",
                "discount",
                "escalation",
                "life_years",
                "usd_per_ft2",
                "coverage",
            ):
                overrides[k] = v
            if k == "utility" and isinstance(v, dict):
                if v.get("elec_usd_per_kwh") is not None:
                    overrides["elec_rate"] = v["elec_usd_per_kwh"]
                if v.get("gas_usd_per_therm") is not None:
                    overrides["gas_rate"] = v["gas_usd_per_therm"]
    if getattr(args, "area", None) is not None:
        overrides["area_ft2"] = float(args.area)
    if getattr(args, "cooling_tons", None) is not None:
        overrides["cooling_tons"] = float(args.cooling_tons)
    if getattr(args, "fan_hp", None) is not None:
        overrides["fan_hp"] = float(args.fan_hp)
    if args.elec_rate is not None:
        overrides["elec_rate"] = float(args.elec_rate)
    if args.gas_rate is not None:
        overrides["gas_rate"] = float(args.gas_rate)

    try:
        result = prefill_notebook_inputs(args.xlsx, overrides=overrides)
    except Exception as exc:
        print(f"prefill failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, default=str))
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    from wattlab.notebooks.builder import validate_notebook

    result = validate_notebook(args.xlsx)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 2


def _cmd_summarize(args: argparse.Namespace) -> int:
    from wattlab.notebooks.builder import summarize_notebook

    man = summarize_notebook(args.xlsx)
    print(json.dumps(man, indent=2))
    if args.write:
        mp = args.xlsx.parent / f"{args.xlsx.stem}.notebook_manifest.json"
        mp.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {mp}", file=sys.stderr)
    return 0


def _cmd_refresh(args: argparse.Namespace) -> int:
    from wattlab.notebooks.builder import refresh_notebook_caches

    if not args.xlsx.is_file():
        print(f"missing workbook: {args.xlsx}", file=sys.stderr)
        return 2
    try:
        result = refresh_notebook_caches(args.xlsx)
    except Exception as exc:
        print(f"refresh-caches failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, default=str))
    return 0


def _cmd_show_formulas(args: argparse.Namespace) -> int:
    from wattlab.notebooks.builder import show_formulas

    if not args.xlsx.is_file():
        print(f"missing workbook: {args.xlsx}", file=sys.stderr)
        return 2
    print(json.dumps(show_formulas(args.xlsx, sheet=args.sheet), indent=2))
    return 0


def _cmd_template(args: argparse.Namespace) -> int:
    from wattlab.notebooks.builder import write_template_stub

    root = Path(__file__).resolve().parent / "templates" / "ecm_package_v1.xlsx"
    out = args.out or root
    path = write_template_stub(out)
    print(json.dumps({"template": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
