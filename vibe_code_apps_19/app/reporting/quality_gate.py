"""Pre-emit report quality audit."""

from __future__ import annotations

import re
from typing import Any

from app.reporting.models import Classification, EngineeringFinding, ReportArtifacts

CLIENT_OK = {
    Classification.STRONGLY_SUPPORTED,
    Classification.PROBABLE,
    Classification.INCONCLUSIVE,
    Classification.DATA_QUALITY,
}

# Negations that contain the substring "replace" but are honesty language, not a fix action.
_ANTI_REPLACE = re.compile(
    r"\b(?:do\s+not|don't|dont|never|avoid)\s+replace\b",
    re.IGNORECASE,
)
# Proactive replace of equipment / instrumentation (weak classes need stronger evidence).
_PROACTIVE_REPLACE = re.compile(
    r"\breplace\b.{0,40}\b(?:equipment|sensor|actuator|damper|valve|transmitter|transducer)\b"
    r"|\b(?:equipment|sensor|actuator|damper|valve|transmitter|transducer)\b.{0,40}\breplace\b",
    re.IGNORECASE,
)


def _has_proactive_replace(corrective: list[str] | None) -> bool:
    """True when corrective text recommends replacing hardware (not 'do not replace…')."""
    for raw in corrective or []:
        text = str(raw or "").strip()
        if not text:
            continue
        if _ANTI_REPLACE.search(text):
            # Strip anti-replace clauses; leftover may still recommend replace.
            text = _ANTI_REPLACE.sub(" ", text)
        if "replace" not in text.lower():
            continue
        if _PROACTIVE_REPLACE.search(text):
            return True
        # Bare "replace …" without gear noun still counts if not anti-replace only.
        if re.search(r"\breplace\b", text, re.IGNORECASE):
            return True
    return False


def run_quality_gate(artifacts: ReportArtifacts) -> dict[str, Any]:
    """Return {ok, errors, warnings}. Reject if critical errors."""
    errors: list[str] = []
    warnings: list[str] = []

    findings = [f for f in artifacts.findings if f.include_in_report]
    if len(findings) > 7:
        errors.append(f"More than 7 priority findings ({len(findings)}) without explicit raise")

    for f in findings:
        cls = f.effective_classification
        if cls not in CLIENT_OK and cls != Classification.DATA_QUALITY:
            errors.append(f"{f.finding_id}: non-client classification in body: {cls.value}")
        if not f.evidence_bullets:
            errors.append(f"{f.finding_id}: high-priority finding has no supporting evidence")
        if cls in {Classification.STRONGLY_SUPPORTED, Classification.PROBABLE}:
            if f.chart_spec is None and f.chart_path is None:
                warnings.append(f"{f.finding_id}: chartable finding has no chart_spec")
        title_l = f.title.lower()
        if "comfort" in title_l and cls != Classification.DATA_QUALITY:
            # dead sensor comfort
            if any("implausible" in (b or "").lower() or "instrumentation" in (b or "").lower() for b in f.evidence_bullets):
                errors.append(f"{f.finding_id}: dead/impossible sensor described as comfort problem")
        if _has_proactive_replace(f.possible_corrective) and cls not in {
            Classification.STRONGLY_SUPPORTED,
            Classification.PROBABLE,
        }:
            errors.append(f"{f.finding_id}: 'replace' recommendation without sufficient evidence class")
        # Near-100% confirmed without common-mode note
        score = float(f.automated_assessment.get("score") or 0)
        if cls == Classification.STRONGLY_SUPPORTED and f.automated_assessment.get("common_mode_review"):
            if not any("common" in r.lower() or "near" in r.lower() for r in (f.data_confidence_notes or [])):
                warnings.append(f"{f.finding_id}: strongly supported + common_mode — ensure skepticism documented")

    if not artifacts.analysis_period:
        warnings.append("Analysis period missing")
    if not artifacts.disclaimer:
        errors.append("Educational disclaimer missing")

    # FP mixed into findings
    for f in findings:
        if f.effective_classification == Classification.LIKELY_FALSE_POSITIVE:
            errors.append(f"{f.finding_id}: likely false positive mixed into client findings")

    ok = len(errors) == 0
    return {"ok": ok, "errors": errors, "warnings": warnings}
