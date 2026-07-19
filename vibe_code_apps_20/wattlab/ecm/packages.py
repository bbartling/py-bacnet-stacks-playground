"""Named, ordered ECM packages for hypothesis-lab screening."""

from __future__ import annotations

from .catalog import ECMCatalog, load_catalog

PACKAGES: dict[str, tuple[str, ...]] = {
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
