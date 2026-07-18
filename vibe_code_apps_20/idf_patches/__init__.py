"""Deprecated shim — real package is :mod:`wattlab.energyplus.patches`."""

import sys

from wattlab.energyplus import patches as _patches
from wattlab.energyplus.patches import *  # noqa: F401,F403

# Keep `from idf_patches.schedules import ...` style imports working.
for _name in (
    "chiller_lockout",
    "gl36_proxy",
    "hourly_outputs",
    "run_period",
    "sat_reset",
    "schedules",
):
    _mod = getattr(
        _patches, _name, None
    ) or __import__(f"wattlab.energyplus.patches.{_name}", fromlist=[_name])
    sys.modules[f"{__name__}.{_name}"] = _mod
