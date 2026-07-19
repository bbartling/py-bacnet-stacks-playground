"""ECM incompatibility and interaction reporting."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from .catalog import ECMCatalog, load_catalog
from .packages import resolve_package


@dataclass(frozen=True, slots=True)
class InteractionIssue:
    ecm_ids: tuple[str, str]
    note: str


def detect_incompatibilities(
    ecm_ids: list[str] | tuple[str, ...],
    *,
    catalog: ECMCatalog | None = None,
) -> list[InteractionIssue]:
    """Return each selected incompatible pair once; reject unknown IDs."""

    registry = catalog or load_catalog()
    entries = {ecm_id: registry.get(ecm_id) for ecm_id in dict.fromkeys(ecm_ids)}
    issues: list[InteractionIssue] = []
    for left, right in combinations(entries, 2):
        if (
            right in entries[left].incompatibilities
            or left in entries[right].incompatibilities
        ):
            issues.append(
                InteractionIssue(
                    ecm_ids=(left, right),
                    note=(
                        f"{entries[left].short_name} conflicts with "
                        f"{entries[right].short_name}; screen as alternatives."
                    ),
                )
            )
    return issues


def expand_package(package_name: str) -> list[str]:
    """Compatibility alias for package resolution."""

    return resolve_package(package_name)


def interaction_notes(ecm_ids: list[str] | tuple[str, ...]) -> list[str]:
    """Generate concise dependency and incompatibility notes."""

    registry = load_catalog()
    notes: list[str] = []
    for ecm_id in dict.fromkeys(ecm_ids):
        entry = registry.get(ecm_id)
        if entry.dependencies:
            notes.append(
                f"{ecm_id} depends on {', '.join(entry.dependencies)}."
            )
    notes.extend(issue.note for issue in detect_incompatibilities(ecm_ids))
    if len(set(ecm_ids)) > 1:
        notes.append(
            "Interacting savings must be evaluated incrementally, not summed "
            "from independent estimates."
        )
    return notes
