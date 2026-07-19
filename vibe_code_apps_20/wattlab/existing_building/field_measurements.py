"""Prioritize field measurements that can discriminate hypotheses."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


_MEASUREMENTS = {
    "operating_hours": ("Trend fan status and occupancy for two representative weeks", 5),
    "ventilation": ("Measure outdoor-air flow or damper position at representative AHUs", 5),
    "capacity": ("Record equipment nameplates and peak-stage/runtime behavior", 4),
    "weather": ("Verify site weather station and EPW representativeness", 3),
    "loads": ("Spot-measure lighting and plug-load power densities", 3),
}


def rank_recommended_measurements(
    uncertain_parameters: Sequence[Mapping[str, Any]],
    sensitivities: Mapping[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Rank measurements by uncertainty, sensitivity and practical value."""
    sensitivities = sensitivities or {}
    rows: list[dict[str, Any]] = []
    for item in uncertain_parameters:
        parameter = str(item.get("parameter") or item.get("name") or "unknown")
        family = parameter.split(".", 1)[0]
        recommendation, value = _MEASUREMENTS.get(
            family, (f"Measure or verify {parameter}", 2)
        )
        uncertainty = float(item.get("uncertainty", 0.5))
        sensitivity = abs(float(sensitivities.get(parameter, item.get("sensitivity", 0.5))))
        score = round(uncertainty * sensitivity * value, 4)
        rows.append(
            {
                "parameter": parameter,
                "recommendation": recommendation,
                "priority_score": score,
                "uncertainty": uncertainty,
                "sensitivity": sensitivity,
                "reason": "Reduces uncertainty in a hypothesis with material modeled sensitivity.",
            }
        )
    rows.sort(key=lambda row: (-row["priority_score"], row["parameter"]))
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows
