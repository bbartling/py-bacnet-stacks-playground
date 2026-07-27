"""Engineering notebook packages — least → radical ECM ladders (one .xlsx each)."""

from __future__ import annotations

from dataclasses import dataclass

from wattlab.ecm.packages import PACKAGES, resolve_package

# Liberty-style screening ladder. Each id → one downloadable workbook.
# ``file_stem`` = human-readable .xlsx name (narrative acts, not catalog jargon).
NOTEBOOK_PACKAGES: dict[str, dict] = {
    "g36_airside_controls": {
        "label": "1 · G36 airside + chiller lockout",
        "file_stem": "01_G36_DSP_SAT_chiller_lockout",
        "story": "DSP reset + SAT reset + chiller lockout <60°F — controls $/sf + VAV/TAB mechanical",
        "rank": 1,
        "catalog_package": "g36-airside-three",
        "honesty": "screening — ESCO Calc_* vs Twin Crosscheck; package cost not per-sensor fluff",
        "polished": True,
    },
    # Aliases → same polished 3-ECM workbook (Studio / old agent recipes)
    "controls_first": {
        "label": "1 · G36 airside + chiller lockout (alias)",
        "file_stem": "01_G36_DSP_SAT_chiller_lockout",
        "story": "Alias of g36_airside_controls",
        "rank": 11,
        "catalog_package": "g36-airside-three",
        "honesty": "alias → g36_airside_controls",
        "polished": True,
        "alias_of": "g36_airside_controls",
    },
    "schedules_economizer": {
        "label": "1 · G36 airside + chiller lockout (alias)",
        "file_stem": "01_G36_DSP_SAT_chiller_lockout",
        "story": "Alias of g36_airside_controls",
        "rank": 12,
        "catalog_package": "g36-airside-three",
        "honesty": "alias → g36_airside_controls",
        "polished": True,
        "alias_of": "g36_airside_controls",
    },
    "plant_optimization": {
        "label": "2 · Plant + boilers + ERV",
        "file_stem": "03_plant_chiller_boiler_erv",
        "story": "Plant — chiller lockout, CHW/CW/HW reset, pumps/VFD, high-eff boiler, ERV",
        "rank": 2,
        "catalog_package": "plant-optimization",
        "honesty": "screening — CHW/HW/CW resets + pump VFD + ERV",
        "extra_measure_ids": ("ECM-ERV", "ECM-CONDENSING-BOILER"),
    },
    "envelope_code": {
        "label": "3 · Envelope to current energy code",
        "file_stem": "04_envelope_code_windows_insulation",
        "story": "Architectural — high-performance glazing + wall/roof insulation to code (conceptual E+ proxy)",
        "rank": 3,
        "catalog_package": "envelope-code",
        "honesty": "what-if — envelope capital; simple-glazing + insulation screening ≠ bid",
    },
    "esco_top15": {
        "label": "4 · ESCO Top-15 HVAC",
        "file_stem": "05_esco_top15_hvac",
        "story": "Full ESCO Top-15 HVAC screening ladder",
        "rank": 4,
        "catalog_package": "esco-top15",
        "honesty": "screening — full ESCO Top-15 map (see Docs sheet)",
    },
    "deep_retrofit": {
        "label": "5 · Deep retrofit (DOAS + HP)",
        "file_stem": "06_ERV_IAQ_DOAS_heat_pump",
        "story": "Radical capital — ERV / IAQ + DOAS heat-pump what-if",
        "rank": 5,
        "catalog_package": "deep-doas-heat-pump",
        "honesty": "what-if — radical capital; not investment-grade",
        "extra_measure_ids": ("ECM-AWHP-SURROGATE",),
    },
}

# Polished G36 workbook sheet contract
REQUIRED_SHEETS = (
    "Baseline",
    "Crosscheck",
    "Charts",
    "Calc_DSP",
    "Calc_SAT",
    "Calc_Lockout",
    "Calc_Cost",
    "Twin_Measures",
    "Guardrails",
    "Docs",
)

G36_SHEET_ORDER = REQUIRED_SHEETS

# Legacy aliases — Studio / validators accept either until all workbooks rebuilt
LEGACY_SHEET_ALIASES = {
    "Baseline": ("Cover", "Calibrated_Twin", "Inputs"),
    "Crosscheck": ("Compare",),
    "Calc_Cost": ("ROI_Capital",),
    "Twin_Measures": ("EPlus_Results",),
    "Charts": ("Charts",),
    # Old multi-measure energy sheet → any Calc_*
    "Calc_DSP": ("ESCO_Calcs", "Calc_Energy"),
    "Calc_SAT": ("ESCO_Calcs", "Calc_Energy"),
    "Calc_Lockout": ("ESCO_Calcs", "Calc_Energy"),
}


def notebook_has_sheet(sheetnames: list[str] | tuple[str, ...], required: str) -> bool:
    """True when v2 sheet or any legacy alias is present."""
    names = set(sheetnames)
    if required in names:
        return True
    return any(alias in names for alias in LEGACY_SHEET_ALIASES.get(required, ()))


INPUT_NAMED_RANGES = (
    "inp_area_ft2",
    "inp_cooling_tons",
    "inp_fan_hp",
    "inp_elec_rate",
    "inp_gas_rate",
    "inp_discount",
    "inp_escalation",
    "inp_life_years",
    "inp_controls_usd_sf",
    "inp_mech_vav_balance_usd",
    "inp_fan_hours",
    "inp_fan_speed_old",
    "inp_fan_speed_new",
    "inp_kw_per_ton",
    "inp_lockout_hours",
    "inp_lockout_oat_f",
    "inp_sat_hours",
    "inp_sat_frac",
)


@dataclass(frozen=True)
class NotebookPackage:
    id: str
    label: str
    rank: int
    catalog_package: str
    honesty: str
    measure_ids: tuple[str, ...]
    file_stem: str = ""
    story: str = ""
    polished: bool = False


def list_notebook_packages(*, include_aliases: bool = False) -> list[NotebookPackage]:
    out: list[NotebookPackage] = []
    for pid, meta in sorted(NOTEBOOK_PACKAGES.items(), key=lambda kv: kv[1]["rank"]):
        if not include_aliases and meta.get("alias_of"):
            continue
        ids = list(resolve_package(meta["catalog_package"]))
        for extra in meta.get("extra_measure_ids") or ():
            if extra not in ids:
                ids.append(extra)
        out.append(
            NotebookPackage(
                id=pid,
                label=str(meta["label"]),
                rank=int(meta["rank"]),
                catalog_package=str(meta["catalog_package"]),
                honesty=str(meta["honesty"]),
                measure_ids=tuple(ids),
                file_stem=str(meta.get("file_stem") or pid),
                story=str(meta.get("story") or meta.get("label") or pid),
                polished=bool(meta.get("polished")),
            )
        )
    return out


def notebook_file_stem(package_id: str) -> str:
    """Human-readable workbook stem for ``reports/notebooks/{stem}.xlsx``."""
    meta = NOTEBOOK_PACKAGES.get(package_id) or {}
    return str(meta.get("file_stem") or package_id)


def notebook_story(package_id: str) -> str:
    meta = NOTEBOOK_PACKAGES.get(package_id) or {}
    return str(meta.get("story") or meta.get("label") or package_id)


def resolve_notebook_package_id(package_id: str) -> str:
    meta = NOTEBOOK_PACKAGES.get(package_id) or {}
    return str(meta.get("alias_of") or package_id)


def get_notebook_package(package_id: str) -> NotebookPackage:
    resolved = resolve_notebook_package_id(package_id)
    for p in list_notebook_packages(include_aliases=True):
        if p.id == resolved:
            return p
    # Also accept human-readable file stem (e.g. 01_G36_DSP_SAT_chiller_lockout)
    for p in list_notebook_packages(include_aliases=False):
        if p.file_stem == package_id or p.file_stem == resolved:
            return p
    known = ", ".join(NOTEBOOK_PACKAGES)
    raise KeyError(f"Unknown notebook package {package_id!r}. Known: {known}")


def catalog_package_ids() -> list[str]:
    return sorted(PACKAGES.keys())
