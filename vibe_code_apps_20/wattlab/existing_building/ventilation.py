"""Ventilation hypothesis scenario builders (minimum-OA screening grid).

Each scenario answers "what if the minimum outdoor air were operated like
this?" and returns ready-to-use ``outdoor_air_fraction`` patch params (see
:func:`wattlab.energyplus.patches.ventilation.apply_outdoor_air_fraction`)
plus explicit warnings and control-surface metadata.

Honesty rules baked into every scenario:

- Zero-OA scenarios are *diagnostic bounds*, never operating recommendations.
- Envelope infiltration is never zeroed: the underlying patch preserves all
  ``ZoneInfiltration:*`` objects, so ``metadata["infiltration_zero"]`` is
  always ``False``.
- Metadata distinguishes the three separate air paths — mechanical minimum
  outdoor air, envelope infiltration, and economizer high-limit operation —
  so a screen can never silently conflate them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

ZERO_OA_WARNING = (
    "Zero outdoor air is a diagnostic hypothesis used to bound ventilation "
    "energy; it is not a recommended or code-compliant operating mode."
)
INFILTRATION_NOTE = (
    "Envelope infiltration is unchanged: ZoneInfiltration objects are "
    "preserved by the patch; only mechanical minimum outdoor air is varied."
)
_SCHEDULE_SURROGATE_WARNING = (
    "The constant-fraction outdoor_air_fraction patch cannot vary OA by hour; "
    "pair this scenario with a weather-responsive Schedule:File surrogate "
    "(wattlab.existing_building.schedules) or treat results as approximate."
)


@dataclass(frozen=True)
class _Spec:
    fraction: float
    hypothesis: str
    minimum_outdoor_air: str
    stuck_closed: bool = False
    economizer_disabled: bool = False
    economizer: str = "as modeled (unchanged)"
    schedule_surrogate: str | None = None
    zero_oa_possible: bool = False
    extra_warnings: tuple[str, ...] = field(default_factory=tuple)


_SCENARIOS: dict[str, _Spec] = {
    "archetype": _Spec(
        fraction=1.0,
        hypothesis="Archetype design minimum OA, operated as designed.",
        minimum_outdoor_air="design minimum OA as modeled (fraction 1.0 of design min OA)",
    ),
    "1.0": _Spec(
        fraction=1.0,
        hypothesis="Minimum OA damper delivers 100% of design minimum OA.",
        minimum_outdoor_air="constant fraction 1.0 of design minimum OA",
    ),
    "0.75": _Spec(
        fraction=0.75,
        hypothesis="Minimum OA damper delivers 75% of design minimum OA.",
        minimum_outdoor_air="constant fraction 0.75 of design minimum OA",
    ),
    "0.5": _Spec(
        fraction=0.5,
        hypothesis="Minimum OA damper delivers 50% of design minimum OA.",
        minimum_outdoor_air="constant fraction 0.5 of design minimum OA",
    ),
    "0.25": _Spec(
        fraction=0.25,
        hypothesis="Minimum OA damper delivers 25% of design minimum OA.",
        minimum_outdoor_air="constant fraction 0.25 of design minimum OA",
    ),
    "0.1": _Spec(
        fraction=0.1,
        hypothesis="Minimum OA damper delivers 10% of design minimum OA.",
        minimum_outdoor_air="constant fraction 0.1 of design minimum OA",
    ),
    "0.0": _Spec(
        fraction=0.0,
        hypothesis="Diagnostic bound: mechanical minimum OA fully closed.",
        minimum_outdoor_air="constant fraction 0.0 of design minimum OA (diagnostic bound)",
        zero_oa_possible=True,
    ),
    "stuck_closed": _Spec(
        fraction=1.0,
        stuck_closed=True,
        hypothesis="Fault hypothesis: OA damper stuck closed (effective fraction 0.0).",
        minimum_outdoor_air=(
            "design minimum OA commanded, but damper stuck closed "
            "(effective fraction 0.0)"
        ),
        zero_oa_possible=True,
    ),
    "occupied_only": _Spec(
        fraction=1.0,
        hypothesis="Design minimum OA during occupied hours only; closed otherwise.",
        minimum_outdoor_air=(
            "design minimum OA during occupied hours; 0.0 when unoccupied "
            "(requires schedule surrogate)"
        ),
        schedule_surrogate="normal_fixed",
        zero_oa_possible=True,
        extra_warnings=(_SCHEDULE_SURROGATE_WARNING,),
    ),
    "mild_weather_only": _Spec(
        fraction=1.0,
        hypothesis=(
            "Design minimum OA only when OAT is between the cold and hot "
            "thresholds (mild weather); closed during extremes."
        ),
        minimum_outdoor_air=(
            "design minimum OA when OAT within [cold, hot] thresholds; "
            "0.0 outside (requires schedule surrogate)"
        ),
        schedule_surrogate="mild_weather_only",
        zero_oa_possible=True,
        extra_warnings=(_SCHEDULE_SURROGATE_WARNING,),
    ),
    "off_during_extremes": _Spec(
        fraction=1.0,
        hypothesis=(
            "Design minimum OA normally, but OA shut off whenever OAT crosses "
            "a hot or cold extreme threshold."
        ),
        minimum_outdoor_air=(
            "design minimum OA except 0.0 during hot/cold extreme hours "
            "(requires schedule surrogate)"
        ),
        schedule_surrogate="off_during_extremes",
        zero_oa_possible=True,
        extra_warnings=(_SCHEDULE_SURROGATE_WARNING,),
    ),
    "economizer_disabled": _Spec(
        fraction=1.0,
        economizer_disabled=True,
        hypothesis="Economizer disabled; minimum OA held at design minimum.",
        minimum_outdoor_air="constant fraction 1.0 of design minimum OA",
        economizer="disabled (Economizer Control Type = NoEconomizer)",
    ),
    "economizer_with_zero_min_oa": _Spec(
        fraction=0.0,
        hypothesis=(
            "Diagnostic bound: no mechanical minimum OA, but economizer left "
            "enabled so OA flows only on free-cooling demand."
        ),
        minimum_outdoor_air="constant fraction 0.0 of design minimum OA (diagnostic bound)",
        economizer="enabled as modeled; outdoor air admitted only on economizer demand",
        zero_oa_possible=True,
    ),
}

_NUMERIC_KEYS = ("1.0", "0.75", "0.5", "0.25", "0.1", "0.0")


def _normalize(name: object) -> str:
    key = str(name).strip()
    if key in _SCENARIOS:
        return key
    try:
        value = float(key)
    except ValueError:
        raise ValueError(
            f"Unknown ventilation scenario {name!r}; "
            f"expected one of {sorted(_SCENARIOS)}"
        ) from None
    for numeric in _NUMERIC_KEYS:
        if float(numeric) == value:
            return numeric
    raise ValueError(
        f"Unknown ventilation OA fraction {name!r}; expected one of {_NUMERIC_KEYS}"
    )


def list_ventilation_scenarios() -> list[str]:
    """All scenario names, in grid order."""
    return list(_SCENARIOS)


def build_ventilation_scenario(name: object) -> dict:
    """Build one named ventilation hypothesis.

    Returns a dict with ``patch`` + ``params`` directly consumable by the
    ``outdoor_air_fraction`` patch registry entry, plus ``warnings`` and
    control-surface ``metadata``.
    """
    key = _normalize(name)
    spec = _SCENARIOS[key]
    effective_zero = spec.stuck_closed or spec.fraction == 0.0

    warnings: list[str] = []
    if effective_zero or spec.zero_oa_possible:
        warnings.append(ZERO_OA_WARNING)
    warnings.append(INFILTRATION_NOTE)
    warnings.extend(spec.extra_warnings)

    return {
        "scenario": key,
        "hypothesis": spec.hypothesis,
        "patch": "outdoor_air_fraction",
        "params": {
            "min_oa_fraction": spec.fraction,
            "stuck_closed": spec.stuck_closed,
            "economizer_disabled": spec.economizer_disabled,
        },
        "warnings": warnings,
        "metadata": {
            "minimum_outdoor_air": spec.minimum_outdoor_air,
            "infiltration": "unchanged (ZoneInfiltration:* objects preserved)",
            "infiltration_zero": False,
            "economizer": spec.economizer,
            "requires_schedule_surrogate": spec.schedule_surrogate is not None,
            "schedule_surrogate": spec.schedule_surrogate,
            "diagnostic_only": effective_zero,
            "conceptual_surrogate": True,
        },
    }


def build_all_ventilation_scenarios() -> dict[str, dict]:
    """The full screening grid, keyed by scenario name."""
    return {name: build_ventilation_scenario(name) for name in _SCENARIOS}
