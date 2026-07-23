"""Render Engineering Findings DOCX via python-docx (optional dependency)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.reporting.models import ReportArtifacts
from app.reporting.narrative import confidence_badge


def render_docx(artifacts: ReportArtifacts, path: Path | str) -> Path:
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Inches, Pt
    except ImportError as exc:
        raise RuntimeError(
            "python-docx is required for Engineering Findings DOCX. "
            "Install: pip install 'vibe19-fdd-demo[engineering-report]' or python-docx"
        ) from exc

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()

    # Cover
    title = doc.add_heading("Engineering Findings Report", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(artifacts.building)
    run.bold = True
    run.font.size = Pt(16)
    doc.add_paragraph(f"Analysis period: {artifacts.analysis_period or 'see assumptions'}")
    doc.add_paragraph(f"Generated: {artifacts.generated_at}")
    doc.add_paragraph(artifacts.disclaimer)
    doc.add_page_break()

    # Executive summary
    doc.add_heading("1. Executive summary", level=1)
    m = artifacts.metrics or {}
    doc.add_paragraph(
        f"Equipment / detections reviewed: {m.get('n_candidates', '—')}. "
        f"Strongly supported: {m.get('n_strongly_supported', 0)}; "
        f"probable: {m.get('n_probable', 0)}; "
        f"inconclusive: {m.get('n_inconclusive', 0)}; "
        f"suppressed likely FP: {m.get('n_suppressed', 0)}; "
        f"data-quality issues: {m.get('n_data_quality', 0)}."
    )
    doc.add_paragraph(
        "Detection ≠ finding: raw rule hits were evidence-reviewed before appearing below."
    )
    doc.add_heading("Prioritized findings", level=2)
    for f in artifacts.findings:
        if not f.include_in_report:
            continue
        doc.add_paragraph(
            f"PRIORITY {f.priority} — {f.title} [{confidence_badge(f.effective_classification)}]",
            style="List Number",
        )
        if f.evidence_bullets:
            doc.add_paragraph(f"Evidence: {f.evidence_bullets[0]}")
        if f.field_verification:
            doc.add_paragraph(f"Check first: {f.field_verification[0]}")

    # Building at a glance
    doc.add_heading("2. Building at a glance", level=1)
    _add_chart_if_any(doc, artifacts, "confidence_summary")
    _add_chart_if_any(doc, artifacts, "comfort_ranking")

    # Prioritized findings detail
    doc.add_heading("3. Prioritized engineering findings", level=1)
    for f in artifacts.findings:
        if not f.include_in_report:
            continue
        doc.add_heading(f"{f.finding_id}: {f.title}", level=2)
        doc.add_paragraph(f"Status: {confidence_badge(f.effective_classification)}")
        doc.add_paragraph(f"Why it matters: {f.why_it_matters}")
        doc.add_paragraph(f"Observed behavior: {f.observed_behavior}")
        doc.add_paragraph("Evidence:")
        for b in f.evidence_bullets:
            doc.add_paragraph(b, style="List Bullet")
        if f.chart_path and Path(f.chart_path).is_file():
            try:
                doc.add_picture(f.chart_path, width=Inches(5.8))
            except Exception:
                pass
        doc.add_paragraph("Contradicting evidence:")
        for b in f.contradicting_evidence:
            doc.add_paragraph(b, style="List Bullet")
        doc.add_paragraph("Likely causes:")
        for b in f.likely_causes:
            doc.add_paragraph(b, style="List Bullet")
        doc.add_paragraph("Recommended field verification:")
        for b in f.field_verification:
            doc.add_paragraph(b, style="List Bullet")
        doc.add_paragraph("Possible corrective action:")
        for b in f.possible_corrective:
            doc.add_paragraph(b, style="List Bullet")
        doc.add_paragraph(f"Rule evidence: {', '.join(f.rule_ids)} on {', '.join(f.equipment_ids)}")
        if f.engineer_override:
            doc.add_paragraph(
                f"Engineer override: {f.engineer_override} (automated assessment retained in JSON)"
            )

    # Comfort
    doc.add_heading("4. Comfort / zone performance", level=1)
    cs = artifacts.comfort_summary or {}
    doc.add_paragraph(
        f"VAVs: {cs.get('n_vav', '—')}; below threshold: {cs.get('n_below', '—')}. "
        "Dead/implausible sensors are excluded from comfort conclusions."
    )
    _add_chart_if_any(doc, artifacts, "comfort_ranking")
    dq_zones = [r for r in artifacts.data_quality if "zone" in " ".join(r.get("reasons") or []).lower() or r.get("mean_zone_t")]
    if dq_zones:
        doc.add_paragraph("Instrumentation exclusions (not comfort complaints):")
        for r in dq_zones[:8]:
            doc.add_paragraph(
                f"{r.get('equipment_id')}: {'; '.join(r.get('reasons') or [])}",
                style="List Bullet",
            )

    # Systems
    doc.add_heading("5. AHU / plant / system findings", level=1)
    sys_findings = [f for f in artifacts.findings if f.include_in_report and any(s in f.systems for s in ("AHU", "CHW", "HW"))]
    if not sys_findings:
        doc.add_paragraph("No separate system-level findings beyond prioritized list.")
    for f in sys_findings:
        doc.add_paragraph(f"{f.finding_id} ({', '.join(f.systems)}): {f.title}", style="List Bullet")

    # Data quality
    doc.add_heading("6. Data quality", level=1)
    if not artifacts.data_quality:
        doc.add_paragraph("No major data-quality exclusions beyond suppressed rows.")
    for r in artifacts.data_quality[:15]:
        doc.add_paragraph(
            f"{r.get('equipment_id')} / {r.get('rule_id')}: {'; '.join(r.get('reasons') or [])}",
            style="List Bullet",
        )

    # Field checklist
    doc.add_heading("7. Recommended field checklist", level=1)
    for item in artifacts.field_checklist[:12]:
        doc.add_paragraph(f"[ ] {item}", style="List Bullet")

    # Appendix A
    doc.add_page_break()
    doc.add_heading("Appendix A — Full rule / detection results", level=1)
    doc.add_paragraph(
        "Raw detections and suppressed classifications. Clients should not need this appendix "
        "to understand the building."
    )
    table = doc.add_table(rows=1, cols=5)
    hdr = table.rows[0].cells
    hdr[0].text = "Equipment"
    hdr[1].text = "Rule"
    hdr[2].text = "Hours"
    hdr[3].text = "Pct"
    hdr[4].text = "Class"
    for c in artifacts.candidates[:80]:
        row = table.add_row().cells
        row[0].text = str(c.get("equipment_id") or "")
        row[1].text = str(c.get("rule_id") or "")
        row[2].text = str(c.get("fault_hours") or "")
        row[3].text = str(c.get("fault_pct") or "")
        row[4].text = ""
    for s in artifacts.suppressed[:40]:
        row = table.add_row().cells
        row[0].text = str(s.get("equipment_id") or "")
        row[1].text = str(s.get("rule_id") or "")
        row[2].text = ""
        row[3].text = ""
        row[4].text = str(s.get("classification") or "")

    # Appendix B
    doc.add_heading("Appendix B — Methods / assumptions", level=1)
    for k, v in (artifacts.assumptions or {}).items():
        doc.add_paragraph(f"{k}: {v}")
    qg = artifacts.quality_gate or {}
    doc.add_paragraph(f"Quality gate OK: {qg.get('ok')}; warnings: {qg.get('warnings')}")

    # Footer page numbers via sections
    section = doc.sections[0]
    footer = section.footer
    footer.paragraphs[0].text = f"{artifacts.building} — Engineering Findings Report (advisory)"

    doc.save(str(path))
    return path


def _add_chart_if_any(doc, artifacts: ReportArtifacts, name: str) -> None:
    for ch in artifacts.charts or []:
        if ch.get("name") == name and ch.get("path") and Path(ch["path"]).is_file():
            try:
                from docx.shared import Inches

                doc.add_picture(ch["path"], width=Inches(5.8))
            except Exception:
                pass
            return
