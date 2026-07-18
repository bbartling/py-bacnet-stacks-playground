"""EUI benchmark registry — "is this building obviously outside its peer group?"

Loads the public benchmark table (EPA Portfolio Manager national medians +
CBECS whole-commercial fallback) shipped in ``wattlab/data/benchmarks`` and
optionally merges user/portfolio registries. All comparisons are site EUI in
kBtu/ft²-year.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parents[1] / "data" / "benchmarks" / "benchmarks_public.json"

_ALIASES = {
    "office": "office",
    "offices": "office",
    "office_building": "office",
    "school": "k12_school",
    "k-12": "k12_school",
    "k12": "k12_school",
    "k12_school": "k12_school",
    "primary_school": "k12_school",
    "secondary_school": "k12_school",
    "retail": "retail_store",
    "retail_store": "retail_store",
    "store": "retail_store",
    "hotel": "hotel",
    "lodging": "hotel",
    "hospital": "hospital",
    "healthcare": "hospital",
    "medical_office": "medical_office",
    "clinic": "medical_office",
    "courthouse": "courthouse",
    "public_service": "courthouse",
    "warehouse": "warehouse_nonrefrigerated",
    "warehouse_nonrefrigerated": "warehouse_nonrefrigerated",
    "worship": "worship_facility",
    "church": "worship_facility",
    "worship_facility": "worship_facility",
    "senior_living": "senior_living",
    "mixed_use": "mixed_use",
    "mixed": "mixed_use",
}

_FALLBACK_TYPE = "commercial_all"


def load_registry(extra_paths: list[str | Path] | None = None) -> list[dict[str, Any]]:
    """Public benchmark rows, plus any user registries appended in order."""
    rows: list[dict[str, Any]] = []
    for p in [_DATA, *(extra_paths or [])]:
        doc = json.loads(Path(p).read_text(encoding="utf-8"))
        rows.extend(doc.get("rows", []))
    return rows


def normalize_property_type(property_type: str) -> str:
    key = str(property_type or "").strip().lower().replace(" ", "_").replace("-", "_")
    return _ALIASES.get(key, key)


def lookup(property_type: str, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Benchmark row for a property type, falling back to CBECS all-commercial.

    The returned row always includes ``property_type_matched`` so the UI can
    show whether the peer group was exact or a fallback.
    """
    rows = rows if rows is not None else load_registry()
    norm = normalize_property_type(property_type)
    for r in rows:
        if r.get("property_type") == norm:
            return {**r, "property_type_matched": "exact"}
    for r in rows:
        if r.get("property_type") == _FALLBACK_TYPE:
            return {**r, "property_type_matched": "fallback_commercial_all"}
    raise LookupError("benchmark registry has no fallback row")


def compare_eui(
    site_eui_kbtu_ft2: float,
    property_type: str,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare a site EUI against its peer-group band.

    ``band``: ``below_p20`` / ``within_band`` / ``above_p80``;
    ``vs_median_pct`` positive means worse (higher) than the median.
    """
    bm = lookup(property_type, rows)
    p50 = float(bm["p50"])
    p20 = float(bm.get("p20") or p50 * 0.65)
    p80 = float(bm.get("p80") or p50 * 1.35)
    eui = float(site_eui_kbtu_ft2)
    if eui < p20:
        band = "below_p20"
    elif eui > p80:
        band = "above_p80"
    else:
        band = "within_band"
    return {
        "site_eui_kbtu_ft2": round(eui, 1),
        "property_type": normalize_property_type(property_type),
        "property_type_matched": bm["property_type_matched"],
        "benchmark_name": bm.get("benchmark_name"),
        "p20": p20,
        "p50": p50,
        "p80": p80,
        "vs_median_pct": round((eui - p50) / p50 * 100.0, 1),
        "band": band,
        "source": bm.get("source"),
        "confidence": bm.get("confidence"),
    }
