"""Engineering notebook packages — least → radical ECM ladders (one .xlsx each)."""

from __future__ import annotations

from dataclasses import dataclass

from wattlab.ecm.packages import PACKAGES, resolve_package

# Liberty-style screening ladder. Each id → one downloadable workbook.
# ``file_stem`` = human-readable .xlsx name (narrative acts, not catalog jargon).
NOTEBOOK_PACKAGES: dict[str, dict] = {
    "controls_first": {
        "label": "1 · Easy controls (minimal modification)",
        "file_stem": "01_easy_controls_rcx",
        "story": "Easy RCx — schedules, sensors, standby+DCV, chiller lockout (no major capital)",
        "rank": 1,
        "catalog_package": "no-capital-rcx",
        "honesty": "screening — lowest-touch package before G36 airside",
    },
    "schedules_economizer": {
        "label": "2 · G36 airside trim-and-respond",
        "file_stem": "02_G36_airside_trim_respond",
        "story": "G36 — SAT/DSP reset, schedules, standby+DCV, VAV improvements, chiller lockout",
        "rank": 2,
        "catalog_package": "controls-only",
        "honesty": "screening — controls package before plant capital",
    },
    "plant_optimization": {
        "label": "3 · Plant + boilers + ERV",
        "file_stem": "03_plant_chiller_boiler_erv",
        "story": "Plant — chiller lockout, CHW/CW/HW reset, pumps/VFD, high-eff boiler, ERV",
        "rank": 3,
        "catalog_package": "plant-optimization",
        "honesty": "screening — CHW/HW/CW resets + pump VFD + ERV",
        "extra_measure_ids": ("ECM-ERV", "ECM-CONDENSING-BOILER"),
    },
    "envelope_code": {
        "label": "4 · Envelope to current energy code",
        "file_stem": "04_envelope_code_windows_insulation",
        "story": "Architectural — high-performance glazing + wall/roof insulation to code (conceptual E+ proxy)",
        "rank": 4,
        "catalog_package": "envelope-code",
        "honesty": "what-if — envelope capital; simple-glazing + insulation screening ≠ bid",
    },
    "esco_top15": {
        "label": "5 · ESCO Top-15 HVAC",
        "file_stem": "05_esco_top15_hvac",
        "story": "Full ESCO Top-15 HVAC screening ladder",
        "rank": 5,
        "catalog_package": "esco-top15",
        "honesty": "screening — full ESCO Top-15 map (see Docs sheet)",
    },
    "deep_retrofit": {
        "label": "6 · Deep retrofit (DOAS + HP)",
        "file_stem": "06_ERV_IAQ_DOAS_heat_pump",
        "story": "Radical capital — ERV / IAQ + DOAS heat-pump what-if",
        "rank": 6,
        "catalog_package": "deep-doas-heat-pump",
        "honesty": "what-if — radical capital; not investment-grade",
        "extra_measure_ids": ("ECM-AWHP-SURROGATE",),
    },
}

# ECM Notebook v2 sheet contract (see vibe20_agent_spec/docs/ECM_NOTEBOOK_V2.md)
REQUIRED_SHEETS = (
    "Baseline",
    "Measures",
    "Calc_Energy",
    "Calc_Cost",
    "Twin_Measures",
    "Crosscheck",
    "Charts",
    "Guardrails",
    "Docs",
)

# Legacy aliases — Studio / validators accept either until all workbooks rebuilt
LEGACY_SHEET_ALIASES = {
    "Baseline": ("Cover", "Calibrated_Twin", "Inputs"),
    "Measures": ("Screening_Results",),
    "Calc_Energy": ("ESCO_Calcs",),
    "Calc_Cost": ("ROI_Capital",),
    "Twin_Measures": ("EPlus_Results",),
    "Crosscheck": ("Compare",),
    "Charts": ("Charts",),  # v1+v2 same name
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
    "inp_usd_per_ft2",
    "inp_coverage",
    "inp_sched_hours_saved",
    "inp_fan_hours",
    "inp_fan_speed",
    "inp_kw_per_ton",
    "inp_lockout_hours",
    "inp_standby_hours",
    "inp_sat_hours",
    "inp_erv_cfm",
    "inp_erv_eff",
    "inp_erv_hours",
    "inp_heating_mmbtu",
    "inp_boiler_eff_base",
    "inp_boiler_eff_prop",
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


def list_notebook_packages() -> list[NotebookPackage]:
    out: list[NotebookPackage] = []
    for pid, meta in sorted(NOTEBOOK_PACKAGES.items(), key=lambda kv: kv[1]["rank"]):
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


def get_notebook_package(package_id: str) -> NotebookPackage:
    for p in list_notebook_packages():
        if p.id == package_id:
            return p
    known = ", ".join(NOTEBOOK_PACKAGES)
    raise KeyError(f"Unknown notebook package {package_id!r}. Known: {known}")


def catalog_package_ids() -> list[str]:
    return sorted(PACKAGES.keys())
