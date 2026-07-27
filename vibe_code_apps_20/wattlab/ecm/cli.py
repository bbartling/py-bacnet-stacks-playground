"""CLI helpers for the canonical ECM catalog."""

from __future__ import annotations

import argparse
import json
from typing import Any

from wattlab.ecm.catalog import get_ecm, list_ecms, load_catalog
from wattlab.ecm.interactions import detect_incompatibilities, expand_package
from wattlab.ecm.packages import PACKAGES


def _as_dict(entry: Any) -> dict[str, Any]:
    if hasattr(entry, "model_dump"):
        return entry.model_dump()
    if isinstance(entry, dict):
        return entry
    return dict(entry)


def _cmd_list(_: argparse.Namespace) -> int:
    rows = [
        {
            "ecm_id": e.ecm_id,
            "display_name": e.display_name,
            "category": e.category,
            "status": e.status,
        }
        for e in list_ecms()
    ]
    print(json.dumps(rows, indent=2))
    return 0


def _cmd_describe(args: argparse.Namespace) -> int:
    print(json.dumps(_as_dict(get_ecm(args.ecm_id)), indent=2))
    return 0


def _cmd_package(args: argparse.Namespace) -> int:
    print(json.dumps(expand_package(args.package_id), indent=2))
    return 0


def _cmd_packages(_: argparse.Namespace) -> int:
    print(json.dumps(sorted(PACKAGES), indent=2))
    return 0


def _cmd_audit(_: argparse.Namespace) -> int:
    entries = list_ecms()
    ids = [e.ecm_id for e in entries]
    conflicts = [
        {"ecm_ids": list(issue.ecm_ids), "note": issue.note}
        for issue in detect_incompatibilities(ids)
    ]
    production = [
        e.ecm_id
        for e in entries
        if str(e.status).startswith("PRODUCTION")
        or e.status == "CONCEPTUAL_ENERGYPLUS_PROXY"
    ]
    report: dict[str, Any] = {
        "n_ecms": len(entries),
        "n_production_or_conceptual": len(production),
        "unique_ids": len(ids) == len(set(ids)),
        "packages": sorted(PACKAGES),
        "sample_incompatibilities": conflicts[:20],
    }
    print(json.dumps(report, indent=2))
    return 0 if report["unique_ids"] else 1


def _cmd_run_on_twin(args: argparse.Namespace) -> int:
    from wattlab.ecm.run_on_twin import run_ecms_on_twin

    mids = [x.strip() for x in str(args.ecms).split(",") if x.strip()] if args.ecms else None
    result = run_ecms_on_twin(
        workspace=args.workspace,
        measure_ids=mids,
        twin_run=args.twin_run,
        prefix=args.prefix,
        answers_path=args.answers,
        dry_run=args.dry_run,
    )
    # Drop bulky nested plan/cascade noise for stdout
    slim = {k: v for k, v in result.items() if k not in {"plan"}}
    print(json.dumps(slim, indent=2, default=str))
    return 0 if result.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wattlab ecm", description="Canonical ECM catalog tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List ECM ids").set_defaults(func=_cmd_list)
    d = sub.add_parser("describe", help="Describe one ECM")
    d.add_argument("ecm_id")
    d.set_defaults(func=_cmd_describe)
    pk = sub.add_parser("package", help="Expand a named package")
    pk.add_argument("package_id")
    pk.set_defaults(func=_cmd_package)
    sub.add_parser("packages", help="List packages").set_defaults(func=_cmd_packages)
    sub.add_parser("audit", help="Catalog integrity audit").set_defaults(func=_cmd_audit)

    rt = sub.add_parser(
        "run-on-twin",
        help="Patch+simulate ECMs on best G14 Twin (EnergyPlus MCP/DinD) → ecm_compare.json",
    )
    rt.add_argument("--workspace", default="/data")
    rt.add_argument("--twin-run", default=None)
    rt.add_argument("--prefix", default=None)
    rt.add_argument("--answers", default=None)
    rt.add_argument("--ecms", default=None, help="Comma ids (default G36 three)")
    rt.add_argument("--dry-run", action="store_true")
    rt.set_defaults(func=_cmd_run_on_twin)

    args = p.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
