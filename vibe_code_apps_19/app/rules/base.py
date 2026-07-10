"""Shared rule helpers and standard result contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

RuleStatus = Literal[
    "PASS",
    "FAULT",
    "SKIPPED_MISSING_ROLES",
    "SKIPPED_EQUIPMENT_OFF",
    "NOT_APPLICABLE_EQUIPMENT_TYPE",
    "ERROR",
]


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
    status: RuleStatus
    applicable: bool
    site_id: str = ""
    building_id: str = ""
    equipment_type: str = "UNKNOWN"
    missing_roles: list[str] = field(default_factory=list)
    fault_hours: float | None = None
    fault_pct: float | None = None
    sample_count: int = 0
    fault_sample_count: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    debug: pd.DataFrame | None = None
    notes: str = ""
    raw_fault: pd.Series | None = None
    confirmed_fault: pd.Series | None = None
    plot_series: dict[str, pd.Series] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "equipment_id": self.equipment_id,
            "site_id": self.site_id,
            "building_id": self.building_id,
            "equipment_type": self.equipment_type,
            "status": self.status,
            "applicable": self.applicable,
            "missing_roles": list(self.missing_roles),
            "fault_hours": self.fault_hours,
            "fault_pct": self.fault_pct,
            "sample_count": self.sample_count,
            "fault_sample_count": self.fault_sample_count,
            "metrics": dict(self.metrics),
            "debug": self.debug,
            "notes": self.notes,
        }


def skipped(
    rule_id: str,
    equipment_id: str,
    missing: list[str],
    notes: str = "",
    *,
    site_id: str = "",
    building_id: str = "",
    equipment_type: str = "UNKNOWN",
) -> RuleResult:
    msg = f"SKIPPED — missing roles: {', '.join(missing)}"
    return RuleResult(
        rule_id=rule_id,
        equipment_id=equipment_id,
        site_id=site_id,
        building_id=building_id,
        equipment_type=equipment_type,
        status="SKIPPED_MISSING_ROLES",
        applicable=False,
        missing_roles=missing,
        fault_hours=None,
        fault_pct=None,
        notes=notes or msg,
    )


def not_applicable(
    rule_id: str,
    equipment_id: str,
    equipment_kind: str,
    *,
    site_id: str = "",
    building_id: str = "",
    equipment_type: str = "UNKNOWN",
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        equipment_id=equipment_id,
        site_id=site_id,
        building_id=building_id,
        equipment_type=equipment_type,
        status="NOT_APPLICABLE_EQUIPMENT_TYPE",
        applicable=False,
        missing_roles=[],
        notes=f"NOT_APPLICABLE — rule not applicable to equipment kind '{equipment_kind}'",
    )


def error_result(
    rule_id: str,
    equipment_id: str,
    exc: Exception,
    *,
    site_id: str = "",
    building_id: str = "",
    equipment_type: str = "UNKNOWN",
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        equipment_id=equipment_id,
        site_id=site_id,
        building_id=building_id,
        equipment_type=equipment_type,
        status="ERROR",
        applicable=False,
        notes=f"ERROR — {type(exc).__name__}: {exc}",
    )


def equipment_off(
    rule_id: str,
    equipment_id: str,
    *,
    notes: str = "",
    site_id: str = "",
    building_id: str = "",
    equipment_type: str = "UNKNOWN",
    metrics: dict[str, Any] | None = None,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        equipment_id=equipment_id,
        site_id=site_id,
        building_id=building_id,
        equipment_type=equipment_type,
        status="SKIPPED_EQUIPMENT_OFF",
        applicable=False,
        fault_hours=None,
        fault_pct=None,
        metrics=metrics or {},
        notes=notes
        or "SKIPPED_EQUIPMENT_OFF — equipment was not proven on during the analysis period.",
    )


def finalize_result(
    rule_id: str,
    equipment_id: str,
    raw: pd.Series,
    poll_seconds: float,
    confirm_seconds: float,
    *,
    site_id: str = "",
    building_id: str = "",
    equipment_type: str = "UNKNOWN",
    metrics: dict[str, Any] | None = None,
    plot_series: dict[str, pd.Series] | None = None,
    active_mask: pd.Series | None = None,
) -> RuleResult:
    raw = raw.fillna(False).astype(bool)
    if active_mask is not None:
        active = active_mask.reindex(raw.index).fillna(False).astype(bool)
        raw = raw & active
    else:
        active = pd.Series(True, index=raw.index)

    confirmed = confirm_fault(raw, poll_seconds=poll_seconds, confirm_seconds=confirm_seconds)
    n_total = len(raw)
    n_active = int(active.sum())
    fault_n = int(confirmed.sum())
    active_h = hours_true(active, poll_seconds)
    fault_h = hours_true(confirmed, poll_seconds)
    pct = 100.0 * fault_h / active_h if active_h else 0.0
    status: RuleStatus = "FAULT" if fault_n > 0 else "PASS"
    metrics_out = dict(metrics or {})
    metrics_out.setdefault("active_sample_count", n_active)
    metrics_out.setdefault("total_sample_count", n_total)
    return RuleResult(
        rule_id=rule_id,
        equipment_id=equipment_id,
        site_id=site_id,
        building_id=building_id,
        equipment_type=equipment_type,
        status=status,
        applicable=True,
        fault_hours=round(fault_h, 2),
        fault_pct=round(pct, 2),
        sample_count=n_active if active_mask is not None else n_total,
        fault_sample_count=fault_n,
        metrics=metrics_out,
        raw_fault=raw,
        confirmed_fault=confirmed,
        plot_series=plot_series or {},
        notes=f"{fault_h:.1f}h fault ({pct:.1f}% of active)" if fault_n else "No confirmed faults",
    )
