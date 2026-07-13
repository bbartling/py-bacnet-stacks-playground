"""Serve prebuilt Word (.docx) reports from ``assets/reports`` (no python-docx).

Engineers replace the files in place; the UI only reads bytes from disk.
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
    "TEMPLATE_PACK_ZIP",
    "UNIVERSAL_FINDING_DOCX",
    "PORTFOLIO_EXECUTIVE_DOCX",
    "applicable_rules_for_equipment",
    "build_equipment_fdd_docx",
    "build_building_data_model_docx",
    "build_analytics_docx",
    "build_rcx_catalog_docx",
    "build_rcx_family_docx",
    "load_report_bytes",
    "fdd_report_filename",
    "rcx_family_report_filename",
    "report_path",
    "list_expected_report_files",
    "list_template_pack_members",
]

KEY_FINDINGS_PLACEHOLDER = (
    "[KEY FINDINGS — engineer summary: paste top issues, savings opportunities, "
    "and follow-ups here before distributing this report.]"
)

REPORTS_DIR = Path(__file__).resolve().parents[1] / "assets" / "reports"
TEMPLATE_PACK_ZIP = "Open-FDD_Vibe19_RCx_DOCX_Template_Pack.zip"
UNIVERSAL_FINDING_DOCX = "rcx_universal_finding_sheet.docx"
PORTFOLIO_EXECUTIVE_DOCX = "rcx_portfolio_executive.docx"

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

# RCx mechanical family → Word template (includes template-only Heat pump / Weather).
_RCX_BY_FAMILY: dict[str, str] = {
    "Zones / VAV": "rcx_zones_vav.docx",
    "AHU / air": "rcx_ahu_air.docx",
    "Boiler / HW": "rcx_boiler_hw.docx",
    "Chiller / CHW / tower": "rcx_chiller_chw_tower.docx",
    "Heat pump": "rcx_heat_pump.docx",
    "Metering": "rcx_metering.docx",
    "Weather": "rcx_weather.docx",
}

# Friendly download labels for primary mechanical-tab buttons.
_RCX_FAMILY_LABEL: dict[str, str] = {
    "Zones / VAV": "Download Zones/VAV RCx Word Template",
    "AHU / air": "Download AHU RCx Word Template",
    "Boiler / HW": "Download Boiler RCx Word Template",
    "Chiller / CHW / tower": "Download Chiller/Tower RCx Word Template",
    "Heat pump": "Download Heat Pump RCx Word Template",
    "Metering": "Download Metering RCx Word Template",
    "Weather": "Download Weather RCx Word Template",
}


def report_path(filename: str) -> Path:
    return REPORTS_DIR / filename


def load_report_bytes(filename: str) -> bytes:
    """Read a committed report from ``assets/reports``."""
    path = report_path(filename)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing prebuilt report `{filename}` under {REPORTS_DIR}. "
            "Paste your Word file there or restore from the template pack ZIP."
        )
    return path.read_bytes()


def fdd_report_filename(equipment_type: str = "") -> str:
    key = (equipment_type or "UNKNOWN").strip().upper().replace(" ", "_")
    return _FDD_BY_TYPE.get(key, "fdd_generic.docx")


def rcx_family_report_filename(family: str = "") -> str:
    if family in _RCX_BY_FAMILY:
        return _RCX_BY_FAMILY[family]
    for label, name in _RCX_BY_FAMILY.items():
        if family and family.lower() in label.lower():
            return name
    return "rcx_catalog.docx"


def rcx_family_download_label(family: str) -> str:
    return _RCX_FAMILY_LABEL.get(family, f"Download RCx Word Template — {family}")


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


def build_universal_finding_docx() -> bytes:
    return load_report_bytes(UNIVERSAL_FINDING_DOCX)


def build_portfolio_executive_docx() -> bytes:
    return load_report_bytes(PORTFOLIO_EXECUTIVE_DOCX)


def load_template_pack_zip_bytes() -> bytes:
    return load_report_bytes(TEMPLATE_PACK_ZIP)


def list_template_pack_members() -> list[str]:
    """DOCX (+ readme) members expected inside the complete template ZIP."""
    return sorted(
        set(_RCX_BY_FAMILY.values())
        | {
            "rcx_catalog.docx",
            "data_model.docx",
            "analytics.docx",
            UNIVERSAL_FINDING_DOCX,
            PORTFOLIO_EXECUTIVE_DOCX,
            "TEMPLATE_PACK_README.txt",
        }
    )


def list_expected_report_files() -> list[str]:
    """All filenames the app expects under assets/reports (excluding the ZIP)."""
    names = set(_FDD_BY_TYPE.values()) | set(_RCX_BY_FAMILY.values()) | {
        "rcx_catalog.docx",
        "data_model.docx",
        "analytics.docx",
        "fdd_generic.docx",
        UNIVERSAL_FINDING_DOCX,
        PORTFOLIO_EXECUTIVE_DOCX,
        TEMPLATE_PACK_ZIP,
    }
    return sorted(names)


def rcx_families() -> tuple[str, ...]:
    """UI family order — RCx chart families first, then template-only tabs."""
    chart = list(RCX_FAMILY_ORDER)
    extras = [f for f in ("Heat pump", "Weather") if f not in chart]
    return tuple(chart + extras)
