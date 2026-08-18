"""Finite 96-row facility kW guards for LIVE and research-PoC paths."""
from __future__ import annotations

import math
from typing import Sequence

N_INTERVALS = 96
KW_PLAUSIBILITY_MAX = 400.0


class TrajectoryGuardError(ValueError):
    """Crashed/incomplete/implausible trajectory. Not a learnable transition."""


def validate_96_row_facility(facility_kw: Sequence[float], *, max_kw: float = KW_PLAUSIBILITY_MAX) -> list[float]:
    vals = [float(x) for x in facility_kw]
    if len(vals) != N_INTERVALS:
        raise TrajectoryGuardError(f"expected {N_INTERVALS} rows, got {len(vals)}")
    if any(math.isnan(v) for v in vals):
        raise TrajectoryGuardError("facility_kw contains NaN")
    if any(math.isinf(v) for v in vals):
        raise TrajectoryGuardError("facility_kw contains Inf")
    if any(v < 0 for v in vals):
        raise TrajectoryGuardError("facility_kw is negative")
    if any(v > float(max_kw) for v in vals):
        raise TrajectoryGuardError(f"unexplained facility_kw above {max_kw:g} kW")
    return vals
