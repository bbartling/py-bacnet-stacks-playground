"""Pydantic boundary models + shared helpers for rule plugins."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


class ParamSpec(BaseModel):
    """One tunable numeric parameter exposed to the analyst UI."""

    key: str
    label: str
    unit: str = ""
    min: float
    max: float
    step: float = 1.0
    default: float


class RuleManifest(BaseModel):
    """Declarative description of a custom / ML rule. Safe to serialize to JSON."""

    id: str
    title: str
    description: str = ""
    kind: str = "pandas"  # "pandas" | "ml"
    author: str = ""
    equipment_kinds: list[str] = Field(default_factory=lambda: ["ahu"])
    required_logical_cols: list[str] = Field(default_factory=list)
    params: list[ParamSpec] = Field(default_factory=list)

    def defaults(self) -> dict[str, float]:
        return {p.key: float(p.default) for p in self.params}

    def clamp(self, overrides: dict[str, Any] | None) -> dict[str, float]:
        out = self.defaults()
        if overrides:
            for p in self.params:
                if p.key in overrides and overrides[p.key] is not None:
                    out[p.key] = max(p.min, min(p.max, float(overrides[p.key])))
        return out


class RuleContext(BaseModel):
    """Everything a plugin needs — a normalized wide frame + resolved params."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    equipment_id: str
    df: Any  # pandas DataFrame with logical columns (sat, mat, oat, rat, fan_on, …)
    poll_seconds: float = 300.0
    tz: str = "UTC"
    params: dict[str, float] = Field(default_factory=dict)

    def series(self, logical: str) -> pd.Series | None:
        if logical in self.df.columns:
            return pd.to_numeric(self.df[logical], errors="coerce")
        return None

    def numeric_frame(self, cols: list[str] | None = None) -> pd.DataFrame:
        frame = self.df
        if cols:
            cols = [c for c in cols if c in frame.columns]
            frame = frame[cols]
        num = frame.select_dtypes(include=[np.number]).copy()
        return num


class RuleResult(BaseModel):
    """Plugin output — a confirmed fault mask plus optional series to chart."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    fault_series: Any = None  # boolean pd.Series aligned to ctx.df
    total_hours: float = 0.0
    fault_hours: float = 0.0
    fault_pct: float = 0.0
    message: str = ""
    plot_series: dict[str, Any] = Field(default_factory=dict)  # {label: pd.Series}
    extra: dict[str, Any] = Field(default_factory=dict)

    def finalize(self, poll_seconds: float) -> "RuleResult":
        if self.fault_series is not None:
            mask = self.fault_series.fillna(False).astype(bool)
            self.total_hours = round(len(mask) * poll_seconds / 3600.0, 2)
            self.fault_hours = round(hours_true(mask, poll_seconds), 2)
            self.fault_pct = round(100.0 * self.fault_hours / self.total_hours, 2) if self.total_hours else 0.0
        return self


ComputeFn = Callable[[RuleContext], RuleResult]


def confirm_fault(raw: pd.Series, *, poll_seconds: float, confirm_seconds: float = 300.0) -> pd.Series:
    """Open-FDD confirm pattern — fault true only after a sustained streak."""
    raw = raw.fillna(False).astype(bool)
    rows = max(1, int(np.ceil(confirm_seconds / max(poll_seconds, 1))))
    groups = (raw != raw.shift()).cumsum()
    streak = raw.groupby(groups).cumcount() + 1
    return raw & (streak >= rows)


def hours_true(mask: pd.Series, poll_seconds: float) -> float:
    return float(mask.fillna(False).astype(bool).sum()) * poll_seconds / 3600.0
