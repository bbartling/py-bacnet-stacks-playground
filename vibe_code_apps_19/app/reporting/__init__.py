"""Engineering Findings Report — detection ≠ finding.

Deterministic evidence review before client-facing conclusions.
"""

from __future__ import annotations

from app.reporting.models import (
    CandidateDetection,
    Classification,
    EngineeringFinding,
    EvidenceItem,
    EvidencePacket,
    FindingAssessment,
    ReportArtifacts,
)
from app.reporting.pipeline import (
    build_engineering_findings,
    render_engineering_report,
)

__all__ = [
    "CandidateDetection",
    "Classification",
    "EngineeringFinding",
    "EvidenceItem",
    "EvidencePacket",
    "FindingAssessment",
    "ReportArtifacts",
    "build_engineering_findings",
    "render_engineering_report",
]
