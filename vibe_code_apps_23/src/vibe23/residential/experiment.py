"""Frozen experiment state helpers and ranking artifact writers."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..grid import FrozenExperimentState, GridCandidate, enumerate_grid
from ..tariff import TariffScenario


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
        fieldnames = list(ordered[0].keys())
        with csv_out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in ordered:
                writer.writerow(dict(row))
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


def default_thermostat_candidates(*, season: str = "summer") -> tuple[GridCandidate, ...]:
    from ..grid import GridDimension

    if season == "winter":
        dims = (
            GridDimension("pre_start_hour", (5.0, 6.0)),
            GridDimension("event_start", (6.0, 7.0)),
            GridDimension("event_end", (9.0,)),
            GridDimension("pre_heat_f", (72.5, 73.5)),
            GridDimension("event_heat_f", (69.5, 70.5)),
        )
    else:
        dims = (
            GridDimension("pre_start_hour", (12.0, 13.0)),
            GridDimension("event_start", (14.0,)),
            GridDimension("event_end", (18.0,)),
            GridDimension("pre_cool_f", (70.5, 71.0)),
            GridDimension("event_cool_f", (73.5, 74.5)),
        )
    return enumerate_grid(dims)
