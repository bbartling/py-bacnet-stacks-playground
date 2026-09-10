"""Thin wrappers around Open-FDD PID-HUNT-1 for the tutorial notebook."""

from __future__ import annotations

import pandas as pd
from open_fdd.rules.pid_hunting import PidHuntingParams, hunting_fault_mask

from .synth import COLUMN, POLL_SECONDS


def run_pid_hunt(
    df: pd.DataFrame,
    *,
    column: str = COLUMN,
    poll_seconds: float = POLL_SECONDS,
    params: PidHuntingParams | None = None,
) -> pd.DataFrame:
    """Return detector metrics + boolean ``fault`` column aligned to ``df``."""
    fault, metrics = hunting_fault_mask(
        df[column],
        params=params or PidHuntingParams(),
        poll_seconds=poll_seconds,
    )
    out = metrics.copy()
    out["fault"] = fault.astype(bool)
    return out


def fault_summary(metrics: pd.DataFrame) -> dict[str, float | int | bool]:
    """One-line numbers a tech can read off a trend."""
    faulted = metrics["fault"].fillna(False)
    return {
        "any_fault": bool(faulted.any()),
        "fault_minutes": int(faulted.sum()),
        "max_tv_1h": float(metrics["total_variation_1h"].fillna(0).max()),
        "max_span_1h": float(metrics["output_span_1h"].fillna(0).max()),
    }
