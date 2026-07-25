"""Headless CLI: Engineering Findings from checklist JSON and/or WattLab dump package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _overview_context_from_dataset(ds) -> dict:
    """Build overview_context from an AgentDataset (frames + session knobs)."""
    from app.analytics import dataset_time_span
    from app.occupancy import OccupancySchedule, occupied_hours_per_week
    from app.reporting.overview_export import build_overview_context

    frames = getattr(ds, "frames", None) or {}
    span = dataset_time_span(frames) if frames else {}
    session = getattr(ds, "session_config", None) or {}
    params = getattr(ds, "params", None) or session.get("params") or {}
    oat_err = 5.0
    try:
        oat_err = float((params.get("OAT-METEO") or {}).get("oat_err", 5.0))
    except (TypeError, ValueError):
        oat_err = 5.0
    sched = OccupancySchedule.from_dict(session.get("occupancy_schedule"))
    return build_overview_context(
        frames=frames,
        role_map=getattr(ds, "role_map", None) or {},
        weather=getattr(ds, "weather", None),
        prefer_web_oat=bool(getattr(ds, "prefer_web_oat", session.get("prefer_web_oat", True))),
        oat_err=oat_err,
        chw_leave_max_f=float(
            getattr(ds, "chw_leave_max_f", None) or session.get("chw_leave_max_f", 48.0)
        ),
        use_status_proof=bool(
            getattr(
                ds,
                "use_mech_cooling_status_proof",
                session.get("use_mech_cooling_status_proof", True),
            )
        ),
        zone_lo_f=float(session.get("zone_lo_f", 70.0)),
        zone_hi_f=float(session.get("zone_hi_f", 75.0)),
        bare_min_occ_hours=float(occupied_hours_per_week(sched)),
        occupancy_schedule=sched.to_dict(),
        dataset_start=span.get("start"),
        dataset_end=span.get("end"),
        span_hours=span.get("span_hours"),
    )


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
    overview_context = None
    building = args.building
    if args.dump:
        from app.agent_api import load_package_path, run_rules

        ds = load_package_path(args.dump)
        building = building or getattr(ds, "building_id", "") or ""
        try:
            overview_context = _overview_context_from_dataset(ds)
        except Exception as exc:  # soft-fail Overview export path
            print(f"overview_context unavailable: {exc}", file=sys.stderr)
            overview_context = None
        if args.run_rules:
            run = run_rules(ds)
            rule_results = run.results

    artifacts = build_engineering_findings(
        building=building,
        checklist=args.checklist_json,
        rule_results=rule_results,
        overview_context=overview_context,
        max_findings=args.max_findings,
    )
    written = render_engineering_report(
        artifacts,
        args.out_dir,
        docx=args.docx,
        json_out=args.json_out or not args.docx,
        charts=not args.no_charts,
        overview_context=overview_context,
        rule_results=rule_results,
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
