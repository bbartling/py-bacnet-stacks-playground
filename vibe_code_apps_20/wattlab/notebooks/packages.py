"""Engineering notebook packages — least → radical ECM ladders (one .xlsx each)."""

from __future__ import annotations

from dataclasses import dataclass

from wattlab.ecm.packages import PACKAGES, resolve_package

# Liberty-style screening ladder. Each id → one downloadable workbook.
# ``file_stem`` = human-readable .xlsx name (narrative acts, not catalog jargon).
NOTEBOOK_PACKAGES: dict[str, dict] = {
    "controls_first": {
        "label": "1 · Controls-first (no capital RCx)",
        "file_stem": "01_controls_first_rcx",
        "story": "Controls-first RCx / schedules / sensors",
        "rank": 1,
        "catalog_package": "no-capital-rcx",
        "honesty": "screening — schedules / sensors / standby+DCV",
    },
    "schedules_economizer": {
        "label": "2 · Schedules + airside resets",
        "file_stem": "01_G36_airside_trim_respond",
        "story": "G36 trim-and-respond — SAT/DSP, schedules, standby+DCV, chiller lockout",
        "rank": 2,
        "catalog_package": "controls-only",
        "honesty": "screening — controls package before plant capital",
    },
    "plant_optimization": {
        "label": "3 · Plant optimization",
        "file_stem": "02_plant_chiller_boiler",
        "story": "Plant — chiller lockout (out of the 40s), CHW/CW/HW reset, pumps / boilers",
        "rank": 3,
        "catalog_package": "plant-optimization",
        "honesty": "screening — CHW/HW/CW resets + pump VFD",
    },
    "esco_top15": {
        "label": "4 · ESCO Top-15 HVAC",
        "file_stem": "04_esco_top15_hvac",
        "story": "Full ESCO Top-15 HVAC screening ladder",
        "rank": 4,
        "catalog_package": "esco-top15",
        "honesty": "screening — full ESCO Top-15 map (see Docs sheet)",
    },
    "deep_retrofit": {
        "label": "5 · Deep retrofit (DOAS + HP)",
        "file_stem": "03_ERV_IAQ_DOAS_heat_pump",
        "story": "ERV / IAQ + DOAS heat-pump capital what-if",
        "rank": 5,
        "catalog_package": "deep-doas-heat-pump",
        "honesty": "what-if — radical capital; not investment-grade",
        "extra_measure_ids": ("ECM-AWHP-SURROGATE",),
    },
}

REQUIRED_SHEETS = (
    "Cover",
    "Screening_Results",
    "Calibrated_Twin",
    "Inputs",
    "ESCO_Calcs",
    "EPlus_Results",
    "Compare",
    "ROI_Capital",
    "Guardrails",
    "Docs",
)

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
