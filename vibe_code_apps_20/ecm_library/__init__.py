"""Deprecated shim — real package is :mod:`wattlab.measures`."""

import sys

from wattlab import measures as _measures  # noqa: F401
from wattlab.measures import measure_sets as _measure_sets

sys.modules[f"{__name__}.measure_sets"] = _measure_sets
