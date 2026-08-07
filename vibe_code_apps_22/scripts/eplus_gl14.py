"""ASHRAE Guideline 14 monthly NMBE / CVRMSE helpers (delegates to multires engine).

Formulas live in ``ml/eplus_multires_metrics`` — do not diverge.
"""
from __future__ import annotations

import sys
from pathlib import Path as _PathForLakeside
from typing import Iterable

_APP = _PathForLakeside(__file__).resolve().parents[1]
_ML = _APP / "ml"
for _p in (_APP, _ML):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lakeside.paths import (  # noqa: E402
    BUILDING_LABEL,
    CAMPUS_ID,
    REGION_LABEL,
    app_root,
    clean_data_building_dir,
    eplus_dir,
    packages_dir,
    reports_dir,
    site_root,
    utilities_dir,
)
from lakeside.paths import BUILDING_ID as _LAKESIDE_BUILDING_ID  # noqa: E402
from lakeside.paths import SITE_REF as _LAKESIDE_SITE_REF  # noqa: E402

from eplus_multires_metrics import (  # noqa: E402
    MONTHLY_CVRMSE_MAX as CVRMSE_PASS,
    MONTHLY_NMBE_ABS_MAX as NMBE_PASS,
    gate_monthly,
    gl14_distance,
    nmbe_cvrmse_pct,
)

# Re-export for callers that imported constants from this module
__all__ = [
    "NMBE_PASS",
    "CVRMSE_PASS",
    "nmbe_cvrmse",
    "pass_fail",
    "gl14_distance",
    "BUILDING_LABEL",
    "CAMPUS_ID",
    "REGION_LABEL",
    "app_root",
    "clean_data_building_dir",
    "eplus_dir",
    "packages_dir",
    "reports_dir",
    "site_root",
    "utilities_dir",
    "_LAKESIDE_BUILDING_ID",
    "_LAKESIDE_SITE_REF",
]


def nmbe_cvrmse(observed: Iterable[float], simulated: Iterable[float], *, p: int = 1) -> dict:
    """NMBE and CVRMSE in percent — authoritative engine."""
    stats = nmbe_cvrmse_pct(observed, simulated, p=p)
    return {
        "n": stats["n"],
        "p": stats["p"],
        "nmbe_pct": round(stats["nmbe_pct"], 3) if stats["n"] else stats["nmbe_pct"],
        "cvrmse_pct": round(stats["cvrmse_pct"], 3) if stats["n"] else stats["cvrmse_pct"],
        "mean_obs": round(stats["mean_obs"], 3) if stats["n"] else stats["mean_obs"],
    }


def pass_fail(stats: dict) -> str:
    return gate_monthly(stats)
