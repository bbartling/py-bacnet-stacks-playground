"""Frozen experiment state helpers and ranking artifact writers."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..grid import FrozenExperimentState, GridCandidate, GridDimension, enumerate_grid
from ..tariff import TariffScenario
from .constants import (
    SUMMER_DR_EVENT_END,
    SUMMER_DR_EVENT_START,
    SUMMER_DR_PRE_START_HOUR,
    WINTER_DR_EVENT_END,
    WINTER_DR_EVENT_START,
    WINTER_DR_PRE_START_HOUR,
)
from .thermostat import center_search_values


def _sha256(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def make_frozen_state(
    *,
    decision_day: str,
    model_sha256: str,
    weather_sha256: str,
    tariff: TariffScenario,
    energyplus_version: str,
    calibration_run_sha256: str | None = None,
    initial_state_sha256: str | None = None,
    baseline_trajectory_sha256: str | None = None,
    occupancy_calendar_sha256: str | None = None,
) -> FrozenExperimentState:
    placeholder = "0" * 64
    return FrozenExperimentState(
        decision_day=decision_day,
        model_sha256=model_sha256,
        weather_sha256=weather_sha256,
        calibration_run_sha256=calibration_run_sha256 or placeholder,
        initial_state_sha256=initial_state_sha256 or placeholder,
        baseline_trajectory_sha256=baseline_trajectory_sha256 or placeholder,
        billing_state_sha256=tariff.fingerprint()[:0] + _sha256({"billing": "open_zero"}),
        tariff_sha256=tariff.fingerprint(),
        occupancy_calendar_sha256=occupancy_calendar_sha256 or placeholder,
        energyplus_version=energyplus_version,
    )


def candidate_id_for_action(action: Mapping[str, Any], ordinal: int) -> str:
    digest = _sha256(dict(action))
    return f"GRID_{ordinal:04d}_{digest[:12]}"


def save_ranking(
    rows: Sequence[Mapping[str, Any]],
    *,
    csv_path: Path | str,
    json_path: Path | str,
    winner_key: str = "billing_cost",
) -> dict[str, Any]:
    csv_out = Path(csv_path)
    json_out = Path(json_path)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda row: float(row.get(winner_key, float("inf"))))
    if ordered:
        fieldnames = [
            k
            for k in ordered[0].keys()
            if k not in {"facility_kw", "zone_temp_f", "purchased_kw", "soc"}
        ]
        with csv_out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in ordered:
                writer.writerow({k: row.get(k) for k in fieldnames})
    winner = ordered[0] if ordered else None
    payload = {
        "schema": "vibe23.residential_grid_ranking.v1",
        "claim_model": "HYPOTHETICAL_GL14_TUNED_DEMO_MODEL",
        "claim_tariff": "ILLUSTRATIVE_HIGH_VALUE_TOU_TARIFF",
        "winner_key": winner_key,
        "candidate_count": len(ordered),
        "winner": winner,
        "rows": list(ordered),
    }
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def default_thermostat_dimensions(*, season: str = "summer") -> tuple[GridDimension, ...]:
    """13×13 center search (±3°F from 72°F @ 0.5°F) with TOU-aligned fixed event hours."""
    centers = center_search_values()
    if season == "winter":
        return (
            GridDimension("pre_center_f", centers),
            GridDimension("event_center_f", centers),
            GridDimension("pre_start_hour", (WINTER_DR_PRE_START_HOUR,)),
            GridDimension("event_start", (WINTER_DR_EVENT_START,)),
            GridDimension("event_end", (WINTER_DR_EVENT_END,)),
        )
    return (
        GridDimension("pre_center_f", centers),
        GridDimension("event_center_f", centers),
        GridDimension("pre_start_hour", (SUMMER_DR_PRE_START_HOUR,)),
        GridDimension("event_start", (SUMMER_DR_EVENT_START,)),
        GridDimension("event_end", (SUMMER_DR_EVENT_END,)),
    )


def default_thermostat_candidates(*, season: str = "summer") -> tuple[GridCandidate, ...]:
    return enumerate_grid(default_thermostat_dimensions(season=season))
