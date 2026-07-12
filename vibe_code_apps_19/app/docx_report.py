"""Serve prebuilt Word (.docx) reports from ``assets/reports`` (no python-docx).

Engineers replace the dummy files in place; the UI only reads bytes from disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.rule_card import PLACE_PLOT_HERE, PLACE_RCX_PLOT_HERE
from app.rules import RULES
from app.rules.cookbook_catalog import CookbookRule
from app.rules.runner import infer_equipment_kind
from app.rcx_plots import RCX_FAMILY_ORDER

# Re-export plot stubs for tests / docs that imported them from this module.
__all__ = [
    "PLACE_PLOT_HERE",
    "PLACE_RCX_PLOT_HERE",
    "KEY_FINDINGS_PLACEHOLDER",
    "REPORTS_DIR",
    "applicable_rules_for_equipment",
    "build_equipment_fdd_docx",
    "build_building_data_model_docx",
    "build_analytics_docx",
    "build_rcx_catalog_docx",
    "build_rcx_family_docx",
    "load_report_bytes",
    "fdd_report_filename",
    "rcx_family_report_filename",
]

KEY_FINDINGS_PLACEHOLDER = (
    "[KEY FINDINGS — engineer summary: paste top issues, savings opportunities, "
    "and follow-ups here before distributing this report.]"
)

REPORTS_DIR = Path(__file__).resolve().parents[1] / "assets" / "reports"

# Equipment type → static FDD file (CHILLER / CHW_PLANT share chiller template).
_FDD_BY_TYPE: dict[str, str] = {
    "AHU": "fdd_ahu.docx",
    "VAV": "fdd_vav.docx",
    "BOILER": "fdd_boiler.docx",
    "CHILLER": "fdd_chiller.docx",
    "CHW_PLANT": "fdd_chiller.docx",
    "COOLING_TOWER": "fdd_cooling_tower.docx",
    "HP": "fdd_hp.docx",
    "HEATPUMP": "fdd_hp.docx",
    "METER": "fdd_meter.docx",
    "WEATHER": "fdd_weather.docx",
    "UNKNOWN": "fdd_generic.docx",
}

_RCX_BY_FAMILY: dict[str, str] = {
    "Zones / VAV": "rcx_zones_vav.docx",
    "AHU / air": "rcx_ahu_air.docx",
    "Boiler / HW": "rcx_boiler_hw.docx",
    "Chiller / CHW / tower": "rcx_chiller_chw_tower.docx",
    "Metering": "rcx_metering.docx",
}


def load_report_bytes(filename: str) -> bytes:
    """Read a committed report from ``assets/reports``."""
    path = REPORTS_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing prebuilt report `{filename}` under {REPORTS_DIR}. "
            "Run `python scripts/gen_dummy_docx_reports.py` or paste your Word file there."
        )
    return path.read_bytes()


def fdd_report_filename(equipment_type: str = "") -> str:
    key = (equipment_type or "UNKNOWN").strip().upper().replace(" ", "_")
    return _FDD_BY_TYPE.get(key, "fdd_generic.docx")


def rcx_family_report_filename(family: str = "") -> str:
    if family in _RCX_BY_FAMILY:
        return _RCX_BY_FAMILY[family]
    # Tolerate slight label drift
    for label, name in _RCX_BY_FAMILY.items():
        if family and family.lower() in label.lower():
            return name
    return "rcx_catalog.docx"


def applicable_rules_for_equipment(
    equipment_id: str,
    *,
    equipment_type: str = "",
    mapped_df: pd.DataFrame | None = None,
    role_map: dict | None = None,
) -> list[CookbookRule]:
    """Canonical cookbook rules applicable to this device's equipment kind."""
    kind = infer_equipment_kind(
        equipment_id,
        equipment_type=equipment_type,
        df=mapped_df,
        role_map=role_map,
    )
    if kind == "unknown":
        return list(RULES)
    return [r for r in RULES if kind in r.equipment_kinds]


def build_equipment_fdd_docx(
    *args: Any,
    equipment_type: str = "",
    **kwargs: Any,
) -> bytes:
    """Serve the prebuilt FDD Word file for this equipment type (args ignored)."""
    if not equipment_type and len(args) >= 3 and isinstance(args[2], str):
        equipment_type = args[2]
    return load_report_bytes(fdd_report_filename(equipment_type))


def build_building_data_model_docx(*args: Any, **kwargs: Any) -> bytes:
    """Serve prebuilt data_model.docx (session tree ignored)."""
    return load_report_bytes("data_model.docx")


def build_analytics_docx(*args: Any, **kwargs: Any) -> bytes:
    """Serve prebuilt analytics.docx (session frames ignored)."""
    return load_report_bytes("analytics.docx")


def build_rcx_family_docx(family: str) -> bytes:
    """Serve the prebuilt RCx Word file for one mechanical family."""
    return load_report_bytes(rcx_family_report_filename(family))


def build_rcx_catalog_docx(*args: Any, family: str | None = None, **kwargs: Any) -> bytes:
    """Serve RCx catalog stub, or a family file when ``family`` is set."""
    if family:
        return build_rcx_family_docx(family)
    return load_report_bytes("rcx_catalog.docx")


def list_expected_report_files() -> list[str]:
    """All filenames the app expects under assets/reports."""
    names = set(_FDD_BY_TYPE.values()) | set(_RCX_BY_FAMILY.values()) | {
        "rcx_catalog.docx",
        "data_model.docx",
        "analytics.docx",
        "fdd_generic.docx",
    }
    return sorted(names)


def rcx_families() -> tuple[str, ...]:
    return RCX_FAMILY_ORDER
