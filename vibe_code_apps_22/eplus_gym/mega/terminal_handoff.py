"""Phase 20: terminal handoff with honest readiness flags."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from eplus_gym.mega._json import sha256_obj

SCHEMA = "vibe22.mega.terminal_handoff.v1"


def build_terminal_handoff(
    *,
    phase_status: Mapping[str, str],
    readiness_flags: Mapping[str, bool] | None = None,
    vibe19_untouched: bool = True,
    bacnet_authority: int = 0,
) -> dict[str, Any]:
    flags = dict(readiness_flags or {})
    flags.setdefault("SIMULATION_TRAINING_READY", False)
    flags.setdefault("OPERATIONAL_DSM_READY", False)
    flags.setdefault("long_campaign_allowed", False)
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "handoff_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase_status": dict(phase_status),
        "readiness_flags": flags,
        "vibe19_untouched": vibe19_untouched,
        "bacnet_command_authority": bacnet_authority,
        "locked_test": "NO_PRISTINE_LOCKED_TEST_AVAILABLE",
        "honest_notes": [
            "A04 parent W2A low-airflow structural — physics repair required before operational claims",
            "Multi-seed mega config defined (≥5); full training bundle NOT RUN in this session",
            "Illustrative tariff modes in observation contract — not verified billing",
        ],
    }
    body["handoff_sha256"] = sha256_obj(body)
    return body


def write_terminal_handoff(path: Path, handoff: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
