"""Custom / ML rule plugin system for Open FDD Vibe Coder.

Fork-friendly: drop a `.py` file in `rules/plugins/` exporting a module-level
`RULE` (RuleManifest) and a `compute(ctx) -> RuleResult` function. The FastAPI
layer only ever runs registered rule ids with validated numeric params — never
arbitrary code from an HTTP request.
"""

from .base import ParamSpec, RuleContext, RuleManifest, RuleResult, confirm_fault, hours_true
from .registry import RuleRegistry, get_registry

__all__ = [
    "ParamSpec",
    "RuleContext",
    "RuleManifest",
    "RuleResult",
    "confirm_fault",
    "hours_true",
    "RuleRegistry",
    "get_registry",
]
