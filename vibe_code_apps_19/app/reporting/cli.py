"""Headless CLI: Engineering Findings from checklist JSON and/or WattLab dump package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Generate an FDD Engineering Findings Report (evidence-reviewed). "
            "Detection ≠ finding; likely false positives stay in Appendix C."
        )
    )
    p.add_argument("--checklist-json", type=Path, help="controls_service_checklist JSON")
    p.add_argument("--dump", type=Path, help="WattLab dump / vibe19 package zip or folder")
    p.add_argument("--building", default="", help="Override building name")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--docx", action="store_true")
    p.add_argument("--json", action="store_true", dest="json_out")
    p.add_argument("--no-charts", action="store_true")
    p.add_argument("--max-findings", type=int, default=7)
    p.add_argument("--run-rules", action="store_true", help="With --dump, also run cookbook FAULTs")
    args = p.parse_args(argv)

    if not args.checklist_json and not args.dump:
        p.error("Provide --checklist-json and/or --dump")

    from app.reporting.pipeline import build_engineering_findings, render_engineering_report

    rule_results = None
    if args.dump:
        from app.agent_api import load_package_path, run_rules

        ds = load_package_path(args.dump)
        if args.run_rules:
            run = run_rules(ds)
            rule_results = run.results

    artifacts = build_engineering_findings(
        building=args.building,
        checklist=args.checklist_json,
        rule_results=rule_results,
        max_findings=args.max_findings,
    )
    written = render_engineering_report(
        artifacts,
        args.out_dir,
        docx=args.docx,
        json_out=args.json_out or not args.docx,
        charts=not args.no_charts,
    )
    print(json.dumps({k: str(v) for k, v in written.items()}, indent=2))
    print("metrics", json.dumps(artifacts.metrics))
    print("quality_gate", json.dumps(artifacts.quality_gate))
    if not artifacts.quality_gate.get("ok"):
        print("QUALITY_GATE_ERRORS", artifacts.quality_gate.get("errors"), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
