"""Example custom pandas rule — supply-air-temp hunting / instability.

Copy this file to author your own site rule. Flags rapid SAT swings that suggest
a hunting control loop or a flaky sensor. Pure pandas + Open-FDD confirm pattern.
"""

from __future__ import annotations

import pandas as pd

from rules.base import ParamSpec, RuleContext, RuleManifest, RuleResult, confirm_fault

RULE = RuleManifest(
    id="CUSTOM-SAT-HUNT",
    title="SAT hunting / instability",
    description=(
        "Confirmed fault when supply-air temperature swings more than the threshold "
        "between consecutive samples — a sign of a hunting loop or noisy sensor."
    ),
    kind="pandas",
    author="vibe-coder example",
    equipment_kinds=["ahu"],
    required_logical_cols=["sat"],
    params=[
        ParamSpec(key="swing_f", label="Max SAT step", unit="°F", min=0.5, max=15, step=0.5, default=4.0),
        ParamSpec(key="confirm_min", label="Confirm delay", unit="min", min=5, max=60, step=5, default=15.0),
    ],
)


def compute(ctx: RuleContext) -> RuleResult:
    sat = ctx.series("sat")
    if sat is None or sat.notna().sum() == 0:
        return RuleResult(message="No supply-air temperature column available for this equipment.")

    step = sat.diff().abs()
    raw = step > ctx.params["swing_f"]
    confirmed = confirm_fault(
        raw,
        poll_seconds=ctx.poll_seconds,
        confirm_seconds=ctx.params["confirm_min"] * 60,
    )

    return RuleResult(
        fault_series=confirmed,
        message=f"Peak SAT step {step.max():.1f}°F · threshold {ctx.params['swing_f']:.1f}°F.",
        plot_series={"SAT °F": sat, "SAT step °F": step},
    )
