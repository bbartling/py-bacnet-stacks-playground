"""``wattlab notebook`` — agent-owned ECM Excel + Studio mirror helpers."""

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
    if getattr(args, "building", None):
        overrides["display_name"] = str(args.building)
    profile.update(overrides)
    return profile


def _load_report(run_dir: Path | None) -> dict[str, Any]:
    """Merge Twin report + scorecard + optional g14_score (BUG-057)."""
    if run_dir is None:
        return {}
    root = Path(run_dir)
    out: dict[str, Any] = {}
    for name in (
        "report.json",
        "wattlab_report.json",
        "calibration_scorecard.json",
        "scorecard.json",
        "g14_score.json",
        "campaign_stamp.json",
    ):
        p = root / name
        if p.is_file():
            data = _load_json(p)
            if data:
                # Later files fill gaps; scorecard annual wins over sparse report
                for k, v in data.items():
                    if k not in out or out.get(k) in (None, {}, []):
                        out[k] = v
                    elif isinstance(out.get(k), dict) and isinstance(v, dict):
                        merged = dict(out[k])
                        merged.update({kk: vv for kk, vv in v.items() if vv is not None})
                        out[k] = merged
                    elif v is not None:
                        out[k] = v
    if root.name and not out.get("run_id"):
        out["run_id"] = root.name
    return out

def _parse_ecms(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    parts = [p.strip() for p in str(raw).replace(";", ",").split(",")]
    return [p for p in parts if p]


def _rate_overrides(args: argparse.Namespace) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if getattr(args, "elec_rate", None) is not None:
        overrides["elec_rate"] = float(args.elec_rate)
    if getattr(args, "gas_rate", None) is not None:
        overrides["gas_rate"] = float(args.gas_rate)
    return overrides


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="wattlab notebook",
        description="ECM engineering notebooks (Excel) — agent-owned; Studio mirrors disk",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list-packages", help="List least→radical notebook packages")
    sp.set_defaults(func=_cmd_list)

    bp = sub.add_parser("build", help="Build one package workbook + manifest")
    _add_build_args(bp)
    bp.set_defaults(func=_cmd_build)

    ab = sub.add_parser(
        "agent-build",
        help="Agent-owned workbook write (--ecms / --scenario / optional twin)",
    )
    _add_build_args(ab, package_required=False)
    ab.add_argument("--ecms", type=str, default=None, help="Comma-separated catalog ECM ids")
    ab.add_argument("--scenario", type=Path, help="ecm_scenario.json (v4)")
    ab.add_argument(
        "--twin-run",
        type=Path,
        dest="twin_run",
        help="Twin run dir (soft EPlus_Results paste; never fails build)",
    )
    ab.add_argument(
        "--write-scenario",
        action="store_true",
        help="Update scenario notebook_path / selected ids / twin_run",
    )
    ab.set_defaults(func=_cmd_agent_build)

    st = sub.add_parser(
        "sync-from-twin",
        help="Refresh EPlus_Results only from a Twin run (soft if missing)",
    )
    st.add_argument("--xlsx", type=Path, required=True)
    st.add_argument("--twin-run", type=Path, dest="twin_run", required=True)
    st.set_defaults(func=_cmd_sync_twin)

    pp = sub.add_parser("prefill", help="Rewrite Inputs yellow cells on an existing workbook")
    pp.add_argument("--xlsx", type=Path, required=True)
    pp.add_argument("--profile", type=Path)
    pp.add_argument("--answers", type=Path)
    pp.add_argument("--from-run", type=Path)
    pp.add_argument("--building", type=str, help="Cover Building label override")
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


def _add_build_args(bp: argparse.ArgumentParser, *, package_required: bool = True) -> None:
    bp.add_argument(
        "--package",
        required=package_required,
        default=None,
        help="Notebook package id (e.g. controls_first)",
    )
    bp.add_argument("--out", type=Path, required=True, help="Output directory")
    bp.add_argument("--profile", type=Path, help="building profile JSON")
    bp.add_argument("--answers", type=Path, help="answers.json (merged into profile)")
    bp.add_argument("--from-run", type=Path, help="Twin run dir with savings_by_measure")
    bp.add_argument("--building", type=str, help="Cover Building label (BUG-047)")
    bp.add_argument("--area", type=float, help="Override floor area ft²")
    bp.add_argument("--cooling-tons", type=float, dest="cooling_tons")
    bp.add_argument("--fan-hp", type=float, dest="fan_hp")
    bp.add_argument("--elec-rate", type=float, dest="elec_rate")
    bp.add_argument("--gas-rate", type=float, dest="gas_rate")
    bp.add_argument("--no-manifest", action="store_true")


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
    overrides = _rate_overrides(args)
    twin = getattr(args, "from_run", None)
    report = _load_report(twin)
    written = build_and_save_notebook(
        args.package,
        args.out,
        profile=profile,
        report=report,
        input_overrides=overrides or None,
        twin_run=str(twin) if twin else None,
        write_manifest=not args.no_manifest,
    )
    print(json.dumps({k: str(v) for k, v in written.items()}, indent=2))
    return 0


def _cmd_agent_build(args: argparse.Namespace) -> int:
    from wattlab.notebooks.builder import agent_build_notebook
    from wattlab.studio.ecm_scenario import load_ecm_scenario, save_ecm_scenario

    scen: dict[str, Any] = {}
    if getattr(args, "scenario", None):
        scen = load_ecm_scenario(args.scenario)

    package = args.package or scen.get("notebook_package_id") or "controls_first"
    ecms = _parse_ecms(getattr(args, "ecms", None))
    if not ecms and scen.get("selected_ecm_ids"):
        ecms = list(scen["selected_ecm_ids"])

    profile = _load_profile(args)
    overrides = dict(scen.get("input_overrides") or {})
    overrides.update(_rate_overrides(args))

    twin = getattr(args, "twin_run", None) or getattr(args, "from_run", None)
    if twin is None and scen.get("twin_run"):
        twin = Path(str(scen["twin_run"]))
    report = _load_report(Path(twin) if twin else None)

    written = agent_build_notebook(
        str(package),
        args.out,
        profile=profile,
        report=report,
        input_overrides=overrides or None,
        measure_ids=ecms,
        twin_run=twin,
        write_manifest=not args.no_manifest,
    )

    if getattr(args, "write_scenario", False) or getattr(args, "scenario", None):
        scen_path = args.scenario if getattr(args, "scenario", None) else None
        body = load_ecm_scenario(scen_path) if scen_path else dict(scen or {})
        body["notebook_package_id"] = str(package)
        body["notebook_path"] = str(written["xlsx"])
        body["selected_ecm_ids"] = list(ecms) if ecms else body.get("selected_ecm_ids") or []
        if twin:
            body["twin_run"] = str(twin)
        body["input_overrides"] = overrides
        save_ecm_scenario(body, path=scen_path)

    print(json.dumps({k: str(v) for k, v in written.items()}, indent=2))
    return 0


def _cmd_sync_twin(args: argparse.Namespace) -> int:
    from wattlab.notebooks.builder import sync_notebook_from_twin

    if not args.xlsx.is_file():
        print(f"missing workbook: {args.xlsx}", file=sys.stderr)
        return 2
    try:
        result = sync_notebook_from_twin(args.xlsx, twin_run=args.twin_run)
    except Exception as exc:
        print(f"sync-from-twin failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, default=str))
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
                "display_name",
                "project_id",
                "building_name",
                "building",
                "name",
                "building_id",
                "sched_hours_saved",
                "fan_hours",
                "fan_speed",
                "kw_per_ton",
                "lockout_hours",
            ):
                overrides[k] = v
            if k == "utility" and isinstance(v, dict):
                if v.get("elec_usd_per_kwh") is not None:
                    overrides["elec_rate"] = v["elec_usd_per_kwh"]
                if v.get("gas_usd_per_therm") is not None:
                    overrides["gas_rate"] = v["gas_usd_per_therm"]
    if getattr(args, "building", None):
        overrides["display_name"] = str(args.building)
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
