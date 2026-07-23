"""Client-safe narrative helpers (no invented certainty)."""

from __future__ import annotations

from typing import Any

from app.reporting.models import CandidateDetection, Classification, EvidencePacket, FindingAssessment


def finding_title(members: list[CandidateDetection], best: FindingAssessment) -> str:
    m0 = members[0]
    if m0.rule_id == "FAN-OFF-STATIC" or any((m.extras or {}).get("fan_off_anomaly") for m in members):
        return f"{m0.equipment_id} duct static sensor likely failed or mis-scaled"
    if best.classification == Classification.DATA_QUALITY:
        return f"{m0.equipment_id} temperature signal is instrumentation/data-quality — not ordinary comfort"
    if len(members) > 1 and best.common_mode_review:
        return f"Common-mode {m0.rule_id} across {len({m.equipment_id for m in members})} devices — verify mapping/threshold before fleet work orders"
    if m0.rule_id in {"VAV-5", "VAV5"}:
        return f"{m0.equipment_id} airflow measurement/control requires field verification"
    if m0.rule_id.startswith("CHW"):
        return f"{m0.equipment_id} / {m0.rule_id} near-continuous — verify compressor proof before operational finding"
    label = m0.rule_label or m0.rule_id
    return f"{m0.equipment_id}: {label}"


def why_it_matters(members: list[CandidateDetection], best: FindingAssessment) -> str:
    if best.classification == Classification.DATA_QUALITY:
        return (
            "Untrustworthy sensors distort comfort rankings and can generate false work orders. "
            "Fix instrumentation before tuning boxes or plants."
        )
    if any(m.rule_id == "FAN-OFF-STATIC" for m in members):
        return (
            "A duct static signal that reads high with the fan proven OFF undermines static-pressure control "
            "and any FDD that trusts that point."
        )
    if any(m.rule_id in {"VAV-5", "VAV5"} for m in members):
        return (
            "Airflow indicated with a closed damper suggests sensor bias or bad damper feedback, "
            "which affects minimums, comfort, and energy."
        )
    return (
        "Telemetry suggests an operational or instrumentation issue that may waste energy or degrade comfort; "
        "field verification is required before corrective work."
    )


def observed_behavior(
    members: list[CandidateDetection],
    best: FindingAssessment,
    packets: dict[str, EvidencePacket],
) -> str:
    m0 = members[0]
    pkt = packets.get(m0.key)
    parts: list[str] = []
    if m0.fault_hours is not None:
        parts.append(f"Rule {m0.rule_id} reports ~{m0.fault_hours:.0f} fault hours")
        if m0.fault_pct is not None:
            parts[-1] += f" ({m0.fault_pct:.1f}% of active samples)"
    if pkt:
        for s in best.supporting[:2]:
            parts.append(s)
    if not parts:
        parts.append(m0.notes or m0.rule_label or m0.rule_id)
    return ". ".join(parts) + "."


def confidence_badge(c: Classification) -> str:
    return {
        Classification.STRONGLY_SUPPORTED: "STRONGLY SUPPORTED",
        Classification.PROBABLE: "PROBABLE",
        Classification.INCONCLUSIVE: "INCONCLUSIVE — NEEDS FIELD VERIFICATION",
        Classification.LIKELY_FALSE_POSITIVE: "LIKELY FALSE POSITIVE / RULE OR MAPPING ISSUE",
        Classification.DATA_QUALITY: "DATA QUALITY / SENSOR ISSUE",
        Classification.NOT_ACTIONABLE: "NOT ACTIONABLE",
    }.get(c, c.value)
