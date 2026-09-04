"""Exportable methods appendix from run provenance + studio assumptions."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping


def methods_appendix_markdown(
    *,
    day: Mapping[str, Any] | None = None,
    equipment: Mapping[str, Any] | None = None,
    battery: Mapping[str, Any] | None = None,
    economics: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Vibe 23 methods appendix",
        "",
        f"- Generated (UTC): `{now}`",
        "- Model claim: `HYPOTHETICAL_GL14_TUNED_DEMO_MODEL`",
        "- Tariff / money claim: `ILLUSTRATIVE_*` unless a layer is explicitly evidence-gated",
        "- Do not treat demo-day dollars as calibrated GL14 savings",
        "",
        "## Studio day fixture",
    ]
    if day:
        lines.extend(
            [
                f"- Label: {day.get('label', '—')}",
                f"- Season / class: {day.get('season', '—')} / {day.get('day_class', '—')}",
                f"- Calendar: {day.get('month', '—')}/{day.get('day', '—')}",
                f"- Intervals: {day.get('intervals', '—')} · dt_hours={day.get('dt_hours', '—')}",
                f"- Baseline kWh: {day.get('baseline_daily_kwh', '—')} · Event kWh: {day.get('event_daily_kwh', '—')}",
                f"- Energy note: {day.get('energy_note', '—')}",
            ]
        )
    else:
        lines.append("- (no day payload)")

    lines.extend(["", "## Equipment / internal gains provenance"])
    if equipment:
        for key in sorted(equipment):
            lines.append(f"- `{key}`: {equipment[key]}")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Battery params (if used)"])
    if battery:
        lines.append("```json")
        lines.append(json.dumps(dict(battery), indent=2, sort_keys=True))
        lines.append("```")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Economics snapshot"])
    if economics:
        lines.append("```json")
        lines.append(json.dumps(dict(economics), indent=2, sort_keys=True, default=str))
        lines.append("```")
    else:
        lines.append("- (none)")

    if extra:
        lines.extend(["", "## Extra provenance"])
        lines.append("```json")
        lines.append(json.dumps(dict(extra), indent=2, sort_keys=True, default=str))
        lines.append("```")

    lines.extend(
        [
            "",
            "## Reproducibility",
            "- Prefer `idf_sha256`, `epw_sha256`, `patched_idf_sha256`, and EnergyPlus version from live runs",
            "- Fixture demos are regenerated via `scripts/export_studio_extreme_days.py`",
            "",
        ]
    )
    return "\n".join(lines) + "\n"
