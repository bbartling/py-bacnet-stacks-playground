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

    args = p.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
