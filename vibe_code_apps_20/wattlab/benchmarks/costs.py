"""Retrofit-cost registry — scope taxonomy with explicit unit basis and vintage.

Every band carries ``unit_basis`` (building_ft2 / glazing_ft2 / …),
``currency_year`` and ``confidence`` so ROI math never silently compares
windows priced per glazing-ft² against chillers priced per building-ft², and
so historical LBNL medians are never presented as 2026 bids.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parents[1] / "data" / "benchmarks" / "retrofit_costs_public.json"

# Map WattLab measure ids onto cost scopes for guardrail checks.
_MEASURE_SCOPE_HINTS: list[tuple[str, str]] = [
    ("SCHED", "rcx_tuning"),
    ("LOCKOUT", "rcx_tuning"),
    ("RESET", "rcx_tuning"),
    ("GL36", "bas_overlay"),
    ("PNEU-DDC", "bas_overlay"),
    ("ADVANCED-RTU", "minor_hvac_controls"),
    ("DOAS-HP", "deep_electrification"),
    ("AWHP", "deep_electrification"),
    ("ERV", "major_hvac_renewal"),
    ("DCV", "minor_hvac_controls"),
    ("ECON", "minor_hvac_controls"),
    ("FAN", "major_hvac"),
    ("BAS", "bas_overlay"),
    ("CHILLER-REPLACE", "major_hvac"),
    ("CONDENSING-BOILER", "major_hvac"),
    ("BOILER", "major_hvac"),
    ("WINDOW", "windows_full_replacement"),
    ("ENVELOPE", "deep_retrofit"),
]


def load_registry(extra_paths: list[str | Path] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in [_DATA, *(extra_paths or [])]:
        doc = json.loads(Path(p).read_text(encoding="utf-8"))
        rows.extend(doc.get("rows", []))
    return rows


def lookup(scope: str, rows: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    rows = rows if rows is not None else load_registry()
    for r in rows:
        if r.get("scope") == scope:
            return dict(r)
    return None


def scope_for_measure(measure_id: str) -> str:
    """Best-effort cost scope for a WattLab measure id (default rcx_tuning)."""
    mid = str(measure_id or "").upper()
    for needle, scope in _MEASURE_SCOPE_HINTS:
        if needle in mid:
            return scope
    return "rcx_tuning"


def check_cost(
    *,
    cost_usd: float,
    scope: str,
    floor_area_ft2: float,
    glazing_area_ft2: float | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare an implementation cost against its scope's reference band.

    ``band``: ``below_band`` / ``within_band`` / ``above_band`` /
    ``no_reference``. Below-band controls costs are common (small point fixes),
    so callers should treat ``above_band`` as the actionable flag.
    """
    ref = lookup(scope, rows)
    if ref is None:
        return {"scope": scope, "band": "no_reference", "cost_usd": cost_usd}

    basis = ref.get("unit_basis") or "building_ft2"
    denom = glazing_area_ft2 if basis == "glazing_ft2" else floor_area_ft2
    if not denom or denom <= 0:
        return {"scope": scope, "band": "no_reference", "cost_usd": cost_usd, "unit_basis": basis}

    per_unit = float(cost_usd) / float(denom)
    lo, hi = float(ref["lo"]), float(ref["hi"])
    if per_unit < lo:
        band = "below_band"
    elif per_unit > hi:
        band = "above_band"
    else:
        band = "within_band"
    return {
        "scope": scope,
        "label": ref.get("label"),
        "unit_basis": basis,
        "cost_usd": round(float(cost_usd), 2),
        "cost_per_unit": round(per_unit, 2),
        "ref_lo": lo,
        "ref_p50": float(ref["p50"]),
        "ref_hi": hi,
        "currency_year": ref.get("currency_year"),
        "confidence": ref.get("confidence"),
        "band": band,
        "source": ref.get("source"),
    }
