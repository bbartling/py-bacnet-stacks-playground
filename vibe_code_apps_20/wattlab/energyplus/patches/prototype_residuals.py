"""Honest stub registry for EnergyPlus prototypes not yet productized in cascade.

Entries here are discoverable as ``HAS_EP_PROTOTYPE`` but are **not** registered
in ``apply_patch`` / ``known_patch_names``. Twin cascade must keep ``NO_EP`` /
``no_energyplus_patch`` honesty until Twin topology + a product IDF patch land.

See ECM-ERV-001 (Liberty soak turnkey P2).
"""

from __future__ import annotations

from typing import Any

# Stub patch names are intentional — never wire these into ``_REGISTRY``.
PROTOTYPE_RESIDUALS: dict[str, dict[str, Any]] = {
    "erv_ahu_prototype": {
        "status": "HAS_EP_PROTOTYPE",
        "ticket": "ECM-ERV-001",
        "catalog_ids": ("ECM-ERV",),
        "workbook_aliases": ("ECM-AHU-ERV",),
        # Liberty full-parity Compare row (screening, not M&V).
        "screening_kwh_hint": 29848.0,
        "product_patch": None,
        "residual": (
            "AHU ERV HX on the Twin OA↔exhaust path needs ducted recovery topology "
            "(HeatExchanger:AirToAir:* + balanced exhaust adjacency). Current stacked "
            "1-zone/floor G14 Twins lack that path, so product cascade stays proxy-only "
            "/ NO_EP. Full-parity workbook / MCP can screen (~29.8k kWh on Liberty B100). "
            "Toilet-zone ERV (ECM-TOILET-EXH-ERV) is an optional later topology ask."
        ),
        "preferred_ss_path": (
            "reports/notebooks/full_parity_ecm/ECM_FULL_PARITY.xlsx via "
            "tools/build_full_parity_ecm_workbook_v2.py"
        ),
    },
}


def list_prototype_residuals() -> list[dict[str, Any]]:
    """Return stub entries with the registry key attached."""
    out: list[dict[str, Any]] = []
    for name, meta in PROTOTYPE_RESIDUALS.items():
        row = dict(meta)
        row["stub_patch_name"] = name
        out.append(row)
    return out


def residual_for_measure(measure_id: str) -> dict[str, Any] | None:
    """Lookup by catalog id or full-parity workbook alias (e.g. ECM-AHU-ERV)."""
    mid = str(measure_id or "").strip()
    if not mid:
        return None
    for name, meta in PROTOTYPE_RESIDUALS.items():
        ids = set(meta.get("catalog_ids") or ()) | set(
            meta.get("workbook_aliases") or ()
        )
        if mid in ids:
            row = dict(meta)
            row["stub_patch_name"] = name
            return row
    return None


def is_prototype_residual_patch(name: str) -> bool:
    """True when ``name`` is a stub, not a product ``apply_patch`` target."""
    return str(name or "").strip() in PROTOTYPE_RESIDUALS
