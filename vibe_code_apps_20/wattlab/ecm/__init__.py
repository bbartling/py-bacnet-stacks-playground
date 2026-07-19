"""Canonical ECM catalog, packages, and interaction checks."""

from .catalog import (
    CATALOG_PATH,
    PRODUCTION_STATUSES,
    ECMCatalog,
    ECMEntry,
    get_ecm,
    list_ecms,
    load_catalog,
)
from .interactions import (
    InteractionIssue,
    detect_incompatibilities,
    expand_package,
    interaction_notes,
)
from .packages import PACKAGES, resolve_package

__all__ = [
    "CATALOG_PATH",
    "PACKAGES",
    "PRODUCTION_STATUSES",
    "ECMCatalog",
    "ECMEntry",
    "InteractionIssue",
    "detect_incompatibilities",
    "expand_package",
    "get_ecm",
    "interaction_notes",
    "list_ecms",
    "load_catalog",
    "resolve_package",
]
