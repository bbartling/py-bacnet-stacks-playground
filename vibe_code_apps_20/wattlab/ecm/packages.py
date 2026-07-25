"""Named, ordered ECM packages for hypothesis-lab screening."""

from __future__ import annotations

from .catalog import ECMCatalog, load_catalog

# Canonical DOE/FEMP/PNNL-style "Top 15" ESCO HVAC ECMs → catalog IDs.
# Order matches screening rank (schedules/RCx first; capital plant last).
ESCO_TOP15: tuple[str, ...] = (
    "ECM-AHU-SCHED-ALIGN",       # 1 HVAC scheduling / optimum start-stop
    "ECM-RCX-SETPOINT-REVIEW",   # 2 Retro-commissioning / controls optimization
    "ECM-PREMIUM-FAN-VFD",       # 3 VFDs on AHU supply/return fans
    "ECM-PUMP-VFD",              # 4 VFDs on CHW/HW/condenser pumps
    "ECM-DSP-RESET",             # 5 Duct static-pressure reset
    "ECM-SAT-RESET",             # 6 Supply-air-temperature reset
    "ECM-VAV-MIN-RESET",         # 7 VAV minimum-airflow reduction
    "ECM-ECON-REPAIR",           # 8 Economizer repair / optimization
    "ECM-DCV-CO2",               # 9 Demand-controlled ventilation
    "ECM-BOILER-RESET",          # 10 Hot-water reset / boiler optimization
    "ECM-CHW-RESET",             # 11a Chilled-water plant optimization
    "ECM-CW-RESET",              # 11b
    "ECM-CHILLER-LOCKOUT",       # 11c
    "ECM-BOILER-TUNE",           # 12 Boiler burner / combustion controls
    "ECM-ADVANCED-RTU",          # 13 Advanced RTU controls
    "ECM-CONDENSING-BOILER",     # 14 High-efficiency boiler replacement
    "ECM-CHILLER-REPLACE-HIEFF", # 15 Chiller replacement / plant modernization
)

PACKAGES: dict[str, tuple[str, ...]] = {
    "esco-top15": ESCO_TOP15,
    "pneumatic-to-ddc": (
        "ECM-SENSOR-CRITICAL-REFRESH",
        "ECM-PNEU-DDC-CONVERT",
        "ECM-AHU-SCHED-ALIGN",
    ),
    "partial-g36": (
        "ECM-AHU-SCHED-ALIGN",
        "ECM-SAT-RESET",
        "ECM-GL36-AIRSIDE",
    ),
    "full-g36-conceptual": (
        "ECM-AHU-SCHED-ALIGN",
        "ECM-OA-RESET",
        "ECM-SAT-RESET",
        "ECM-DSP-RESET",
        "ECM-VAV-MIN-RESET",
        "ECM-GL36-AIRSIDE",
    ),
    "controls-only": (
        "ECM-AHU-SCHED-ALIGN",
        "ECM-CHILLER-LOCKOUT",
        "ECM-SAT-RESET",
        "ECM-DSP-RESET",
    ),
    "low-cost": (
        "ECM-AHU-SCHED-ALIGN",
        "ECM-OA-DAMPER-REPAIR",
        "ECM-BOILER-TUNE",
        "ECM-SENSOR-CALIBRATION",
    ),
    "plant-optimization": (
        "ECM-CHILLER-LOCKOUT",
        "ECM-CHW-RESET",
        "ECM-CW-RESET",
        "ECM-BOILER-RESET",
        "ECM-PUMP-VFD",
    ),
    "no-capital-rcx": (
        "ECM-AHU-SCHED-ALIGN",
        "ECM-OA-DAMPER-REPAIR",
        "ECM-CHILLER-LOCKOUT",
        "ECM-SENSOR-CALIBRATION",
        "ECM-RCX-SETPOINT-REVIEW",
    ),
}


def resolve_package(
    package_name: str, *, catalog: ECMCatalog | None = None
) -> list[str]:
    """Resolve a package and recursively prepend each ECM's dependencies."""

    try:
        requested = PACKAGES[package_name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown ECM package: {package_name}; available: {sorted(PACKAGES)}"
        ) from exc
    registry = catalog or load_catalog()
    resolved: list[str] = []
    visiting: set[str] = set()

    def add(ecm_id: str) -> None:
        if ecm_id in resolved:
            return
        if ecm_id in visiting:
            raise ValueError(f"ECM dependency cycle at {ecm_id}")
        visiting.add(ecm_id)
        entry = registry.get(ecm_id)
        for dependency in entry.dependencies:
            add(dependency)
        visiting.remove(ecm_id)
        resolved.append(ecm_id)

    for measure_id in requested:
        add(measure_id)
    return resolved
