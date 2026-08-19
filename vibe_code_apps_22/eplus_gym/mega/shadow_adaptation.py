"""Phase 14: SIMULATED_SHADOW_ADAPTATION_ONLY on separate development dates."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Sequence

LABEL = "SIMULATED_SHADOW_ADAPTATION_ONLY"
SCHEMA = "vibe22.mega.shadow_adaptation.v1"


@dataclass
class ShadowAdaptationSpec:
    development_dates: list[str] = field(default_factory=list)
    label: str = LABEL
    inspect_locked_test_before_final: bool = False

    def validate_dates(self, *, forbidden: Sequence[str]) -> None:
        bad = set(self.development_dates) & set(forbidden)
        if bad:
            raise ValueError(f"adaptation dates overlap forbidden locked-test window: {sorted(bad)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "label": self.label,
            "development_dates": self.development_dates,
            "inspect_locked_test_before_final": self.inspect_locked_test_before_final,
            "limitations": [
                "Simulated shadow only — not operational BACnet adaptation",
                "Separate from validation model selection",
                "Never inspect locked test before final handoff",
            ],
        }


def default_adaptation_spec(*, forbidden_january: Sequence[str]) -> ShadowAdaptationSpec:
    # Use November dates outside RL train/val per phase1 ledger.
    spec = ShadowAdaptationSpec(
        development_dates=["2025-11-05", "2025-11-18"],
    )
    spec.validate_dates(forbidden=forbidden_january)
    return spec
