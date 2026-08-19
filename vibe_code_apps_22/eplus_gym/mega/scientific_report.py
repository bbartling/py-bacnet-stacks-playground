"""Phase 17: GitHub-renderable scientific report builder."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence


def build_scientific_report(
    *,
    phase_artifacts: Mapping[str, Any],
    claim_labels: Sequence[str] | None = None,
) -> str:
    labels = claim_labels or [
        "SIMULATION_ONLY_RL_RESEARCH",
        "A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED",
        "NO_BACNET_COMMAND_AUTHORITY",
        "Vibe19_untouched",
    ]
    lines = [
        "# Vibe22 mega-program v3 — scientific report",
        "",
        "## Claim labels",
        "",
    ]
    for lb in labels:
        lines.append(f"- `{lb}`")
    lines.extend(["", "## Phase evidence summary", ""])
    for phase, artifact in sorted(phase_artifacts.items()):
        lines.append(f"### {phase}")
        if isinstance(artifact, dict):
            sha = artifact.get("sha256") or artifact.get("diagnosis_sha256") or artifact.get("ledger_sha256")
            if sha:
                lines.append(f"- Artifact SHA256: `{sha[:16]}…`")
            if artifact.get("blocks_promotion") is not None:
                lines.append(f"- Blocks promotion: **{artifact['blocks_promotion']}**")
            if artifact.get("primary_root_cause_summary"):
                lines.append(f"- {artifact['primary_root_cause_summary']}")
        else:
            lines.append(f"- {artifact}")
        lines.append("")
    lines.extend(
        [
            "## Restrained conclusions",
            "",
            "This report documents simulation-only research under immutable A04 parent physics. "
            "W2A low-airflow remains a structural NO-GO for operational DSM until child-model "
            "physics repair passes load-shape gates. Tariff modes are illustrative unless "
            "explicitly verified. No BACnet command authority.",
            "",
        ]
    )
    return "\n".join(lines)


def write_scientific_report(path: Path, markdown: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
