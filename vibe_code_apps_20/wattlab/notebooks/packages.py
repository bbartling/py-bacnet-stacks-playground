"""Engineering notebook packages — least → radical ECM ladders (one .xlsx each)."""

from __future__ import annotations

from dataclasses import dataclass

from wattlab.ecm.packages import PACKAGES, resolve_package

# Liberty-style screening ladder. Each id → one downloadable workbook.
NOTEBOOK_PACKAGES: dict[str, dict] = {
    "controls_first": {
        "label": "1 · Controls-first (no capital RCx)",
        "rank": 1,
        "catalog_package": "no-capital-rcx",
        "honesty": "screening — schedules / sensors / standby+DCV",
    },
    "schedules_economizer": {
        "label": "2 · Schedules + airside resets",
        "rank": 2,
        "catalog_package": "controls-only",
        "honesty": "screening — controls package before plant capital",
    },
    "plant_optimization": {
        "label": "3 · Plant optimization",
        "rank": 3,
        "catalog_package": "plant-optimization",
        "honesty": "screening — CHW/HW/CW resets + pump VFD",
    },
    "esco_top15": {
        "label": "4 · ESCO Top-15 HVAC",
        "rank": 4,
        "catalog_package": "esco-top15",
        "honesty": "screening — full ESCO Top-15 map (see Docs sheet)",
    },
    "deep_retrofit": {
        "label": "5 · Deep retrofit (DOAS + HP)",
        "rank": 5,
        "catalog_package": "deep-doas-heat-pump",
        "honesty": "what-if — radical capital; not investment-grade",
        "extra_measure_ids": ("ECM-AWHP-SURROGATE",),
    },
}

REQUIRED_SHEETS = (
    "Cover",
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
)


@dataclass(frozen=True)
class NotebookPackage:
    id: str
    label: str
    rank: int
    catalog_package: str
    honesty: str
    measure_ids: tuple[str, ...]


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
            )
        )
    return out


def get_notebook_package(package_id: str) -> NotebookPackage:
    for p in list_notebook_packages():
        if p.id == package_id:
            return p
    known = ", ".join(NOTEBOOK_PACKAGES)
    raise KeyError(f"Unknown notebook package {package_id!r}. Known: {known}")


def catalog_package_ids() -> list[str]:
    return sorted(PACKAGES.keys())
