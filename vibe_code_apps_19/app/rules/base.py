"""Shared rule helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


def norm_cmd(s: pd.Series | None) -> pd.Series:
    if s is None:
        return pd.Series(dtype=float)
    s = pd.to_numeric(s, errors="coerce")
    return s.where(s <= 1.0, s / 100.0)


def confirm_fault(raw: pd.Series, *, poll_seconds: float, confirm_seconds: float = 300.0) -> pd.Series:
    raw = raw.fillna(False).astype(bool)
    rows = max(1, int(np.ceil(confirm_seconds / max(poll_seconds, 1))))
    groups = (raw != raw.shift()).cumsum()
    streak = raw.groupby(groups).cumcount() + 1
    return raw & (streak >= rows)


def hours_true(mask: pd.Series, poll_seconds: float) -> float:
    return float(mask.fillna(False).astype(bool).sum()) * poll_seconds / 3600.0


@dataclass
class RuleResult:
    rule_id: str
    equipment_id: str
    raw_fault: pd.Series
    confirmed_fault: pd.Series
    fault_hours: float
    fault_pct: float
    total_hours: float
    debug: pd.DataFrame | None = None
    plot_series: dict[str, pd.Series] = field(default_factory=dict)
    message: str = ""


def finalize(rule_id: str, equipment_id: str, raw: pd.Series, poll_seconds: float, confirm_seconds: float) -> RuleResult:
    confirmed = confirm_fault(raw, poll_seconds=poll_seconds, confirm_seconds=confirm_seconds)
    total_h = len(raw) * poll_seconds / 3600.0
    fault_h = hours_true(confirmed, poll_seconds)
    pct = 100.0 * fault_h / total_h if total_h else 0.0
    return RuleResult(
        rule_id=rule_id,
        equipment_id=equipment_id,
        raw_fault=raw,
        confirmed_fault=confirmed,
        fault_hours=round(fault_h, 2),
        fault_pct=round(pct, 2),
        total_hours=round(total_h, 2),
    )
