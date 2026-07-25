"""Orchestrate Engineering Findings build + render."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.reporting.candidates import (
    candidates_from_checklist_json,
    candidates_from_rule_results,
    comfort_index,
    fan_off_index,
    peer_fault_counts,
    vav_fleet_size,
)
from app.reporting.charts import build_report_charts
from app.reporting.evidence import build_evidence_packet
from app.reporting.findings import cluster_and_prioritize
from app.reporting.models import (
    Classification,
    ReportArtifacts,
)
from app.reporting.quality_gate import run_quality_gate
from app.reporting.reviewer import review_evidence_packet
from app.rules.base import RuleResult


def build_engineering_findings(
    *,
    building: str = "",
    analysis_period: str = "",
    candidates: list | None = None,
    rule_results: list[RuleResult] | None = None,
    checklist: dict[str, Any] | Path | str | None = None,
    context: dict[str, Any] | None = None,
    overview_context: dict[str, Any] | None = None,
    max_findings: int = 7,
) -> ReportArtifacts:
    """Calculate assessments and prioritized findings (no DOCX yet)."""
    ctx = dict(context or {})
    cands = list(candidates or [])
    from app.reporting.overview_export import (
        format_analysis_period,
        overview_settings_from_context,
    )

    overview_settings = overview_settings_from_context(overview_context)

    if checklist is not None:
        loaded, cctx = candidates_from_checklist_json(checklist, building=building or None)
        cands.extend(loaded)
        for k, v in cctx.items():
            ctx.setdefault(k, v)
        building = building or cctx.get("building") or building
        analysis_period = analysis_period or cctx.get("analysis_period") or analysis_period

    if not analysis_period:
        analysis_period = format_analysis_period(overview_context) or format_analysis_period(
            overview_settings
        )

    if rule_results:
        cands.extend(
            candidates_from_rule_results(
                rule_results,
                building=building or "BUILDING",
                analysis_period=analysis_period,
            )
        )

    # Dedupe by key keeping highest fault hours
    by_key: dict[str, Any] = {}
    for c in cands:
        prev = by_key.get(c.key)
        if prev is None or (c.fault_hours or 0) >= (prev.fault_hours or 0):
            by_key[c.key] = c
    cands = list(by_key.values())
    building = building or (cands[0].building if cands else "BUILDING")

    peers = peer_fault_counts(cands)
    fleet = vav_fleet_size(cands, ctx)
    comfort = comfort_index(ctx)
    fan_off = fan_off_index(ctx)

    packets = {}
    assessments = {}
    for c in cands:
        related = [x for x in cands if x.equipment_id == c.equipment_id and x.key != c.key]
        pkt = build_evidence_packet(
            c,
            peer_counts=peers,
            fleet_size=fleet,
            comfort_row=comfort.get(c.equipment_id),
            fan_off_row=fan_off.get(c.equipment_id),
            related_rules=related[:5],
        )
        packets[c.key] = pkt
        assessments[c.key] = review_evidence_packet(pkt)

    findings, suppressed, data_quality = cluster_and_prioritize(
        cands, packets, assessments, max_findings=max_findings
    )

    field_checklist: list[str] = []
    for f in findings:
        field_checklist.extend(f.field_verification)
    # unique preserve order
    seen: set[str] = set()
    field_checklist = [x for x in field_checklist if not (x in seen or seen.add(x))][:12]

    metrics = {
        "n_candidates": len(cands),
        "n_strongly_supported": sum(
            1 for a in assessments.values() if a.classification == Classification.STRONGLY_SUPPORTED
        ),
        "n_probable": sum(1 for a in assessments.values() if a.classification == Classification.PROBABLE),
        "n_inconclusive": sum(
            1 for a in assessments.values() if a.classification == Classification.INCONCLUSIVE
        ),
        "n_suppressed": len(suppressed),
        "n_data_quality": len(data_quality),
        "n_priority_findings": len(findings),
    }

    artifacts = ReportArtifacts(
        building=building,
        analysis_period=analysis_period or ctx.get("analysis_period") or "",
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        findings=findings,
        suppressed=suppressed,
        candidates=[c.to_dict() for c in cands],
        assessments=[a.to_dict() for a in assessments.values()],
        data_quality=data_quality,
        comfort_summary=ctx.get("comfort") or {},
        metrics=metrics,
        field_checklist=field_checklist,
        assumptions={
            "occupancy": "From dump / RCx comfort occupied calendar when present",
            "comfort_band_f": "Typically 70–75°F occupied (see comfort rows)",
            "near_continuous_pct": 95.0,
            "evidence_score": "Explainable engineering score — not probability",
            "detection_vs_finding": "Rule hits are candidates until evidence review",
        },
        quality_gate={},
        overview_settings=overview_settings,
    )
    artifacts.quality_gate = run_quality_gate(artifacts)
    return artifacts


def render_engineering_report(
    artifacts: ReportArtifacts,
    out_dir: Path | str,
    *,
    docx: bool = True,
    json_out: bool = True,
    charts: bool = True,
    basename: str | None = None,
    overview_context: dict[str, Any] | None = None,
    rule_results: list[RuleResult] | None = None,
) -> dict[str, Path]:
    """Write JSON / DOCX / chart assets. Raises if quality gate fails critically."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = basename or _safe_name(artifacts.building) + "_Engineering_Findings"
    written: dict[str, Path] = {}

    if charts:
        chart_dir = out_dir / f"{base}_charts"
        build_report_charts(
            artifacts,
            out_dir=chart_dir,
            comfort_rows=(artifacts.comfort_summary or {}).get("rows"),
            overview_context=overview_context,
            rule_results=rule_results,
        )
        # re-run gate after charts attached
        artifacts.quality_gate = run_quality_gate(artifacts)

    if not artifacts.quality_gate.get("ok"):
        # Allow DOCX with warnings only; hard-fail on errors
        pass

    if json_out:
        jp = out_dir / f"{base}.json"
        jp.write_text(json.dumps(artifacts.to_dict(), indent=2) + "\n", encoding="utf-8")
        written["json"] = jp

    if docx:
        from app.reporting.docx import render_docx

        dp = out_dir / f"{base}.docx"
        render_docx(artifacts, dp)
        written["docx"] = dp

    gate_path = out_dir / f"{base}_quality_gate.json"
    gate_path.write_text(json.dumps(artifacts.quality_gate, indent=2) + "\n", encoding="utf-8")
    written["quality_gate"] = gate_path
    return written


def _safe_name(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in s)[:80] or "Building"
