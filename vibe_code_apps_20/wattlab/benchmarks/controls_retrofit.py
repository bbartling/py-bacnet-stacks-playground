"""Public controls-retrofit savings benchmarks — load and query by class.

Data lives in ``wattlab/data/benchmarks/controls_retrofit_public.json``:
literature-derived screening bands (percent of a stated ``savings_basis``)
with public-report citations, or explicit ``screening_placeholder`` markers
where no public number has been adopted yet (those entries are always
``confidence: low``). These bands are plausibility checks for proxy and
EnergyPlus estimates, never publishable savings on their own.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parents[1] / "data" / "benchmarks" / "controls_retrofit_public.json"

CONFIDENCE_LEVELS = ("high", "medium", "low")
SOURCE_KINDS = ("public_report", "screening_placeholder")


def load_benchmarks(extra_paths: list[str | Path] | None = None) -> list[dict[str, Any]]:
    """All benchmark classes (bundled data plus optional extra JSON files)."""
    rows: list[dict[str, Any]] = []
    for p in [_DATA, *(extra_paths or [])]:
        doc = json.loads(Path(p).read_text(encoding="utf-8"))
        rows.extend(doc.get("classes", []))
    return rows


def list_classes(rows: list[dict[str, Any]] | None = None) -> list[str]:
    rows = rows if rows is not None else load_benchmarks()
    return sorted(str(r.get("retrofit_class")) for r in rows)


def lookup_class(
    retrofit_class: str,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """One class's band (a copy), or None if unknown."""
    rows = rows if rows is not None else load_benchmarks()
    for r in rows:
        if r.get("retrofit_class") == retrofit_class:
            return dict(r)
    return None


def is_placeholder(entry: dict[str, Any]) -> bool:
    """True when any cited source is a screening placeholder (low-trust band)."""
    return any(
        s.get("kind") == "screening_placeholder" for s in entry.get("sources", [])
    )


def check_savings_pct(
    *,
    retrofit_class: str,
    savings_pct: float,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare an estimated savings percent against the class's public band.

    ``savings_pct`` must be on the same basis as the class's ``savings_basis``
    (e.g. percent of HVAC energy, not whole-building, for ``sat_reset``).
    ``band``: ``below_band`` / ``within_band`` / ``above_band`` /
    ``no_reference``. ``above_band`` is the actionable flag before publishing.
    """
    ref = lookup_class(retrofit_class, rows)
    if ref is None:
        return {
            "retrofit_class": retrofit_class,
            "band": "no_reference",
            "savings_pct": savings_pct,
        }
    lo, hi = float(ref["lo_pct"]), float(ref["hi_pct"])
    if savings_pct < lo:
        band = "below_band"
    elif savings_pct > hi:
        band = "above_band"
    else:
        band = "within_band"
    return {
        "retrofit_class": retrofit_class,
        "label": ref.get("label"),
        "savings_basis": ref.get("savings_basis"),
        "savings_pct": round(float(savings_pct), 2),
        "ref_lo_pct": lo,
        "ref_typical_pct": float(ref["typical_pct"]),
        "ref_hi_pct": hi,
        "confidence": ref.get("confidence"),
        "screening_placeholder": is_placeholder(ref),
        "band": band,
        "sources": ref.get("sources", []),
    }
