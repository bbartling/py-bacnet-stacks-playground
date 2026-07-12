"""Equipment-specific operational gates for the 50-rule pandas cookbook.

Do not use one universal motor filter. Prefer status/proof roles over command.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from app.rules.cookbook_catalog import as_bool, norm_cmd

GateKind = Literal[
    "always",
    "fan_running",
    "hydronic_flow",
    "compressor",
    "conditional",
    "control_loop",
]


@dataclass(frozen=True)
class GateSpec:
    kind: GateKind
    startup_delay_seconds: float = 0.0
    minimum_active_coverage_pct: float = 80.0
    command_fallback_allowed: bool = True


# Registry: every canonical rule id → gate (PID-HUNT-1 replaced SV-4).
RULE_GATES: dict[str, GateSpec] = {
    "SV-RANGE": GateSpec("always"),
    "SV-FLATLINE": GateSpec("conditional", startup_delay_seconds=0),
    "SV-SPIKE": GateSpec("always"),
    "SV-STALE": GateSpec("always"),
    "PID-HUNT-1": GateSpec("control_loop", startup_delay_seconds=300),
    "FC1": GateSpec("fan_running", startup_delay_seconds=300),
    "FC2": GateSpec("fan_running", startup_delay_seconds=600),
    "FC3": GateSpec("fan_running", startup_delay_seconds=600),
    "FC4": GateSpec("control_loop", startup_delay_seconds=300),
    "FC5": GateSpec("fan_running", startup_delay_seconds=600),
    "FC6": GateSpec("fan_running", startup_delay_seconds=600),
    "FC7": GateSpec("fan_running", startup_delay_seconds=600),
    "FC8": GateSpec("fan_running", startup_delay_seconds=600),
    "FC9": GateSpec("fan_running", startup_delay_seconds=600),
    "FC10": GateSpec("fan_running", startup_delay_seconds=600),
    "FC11": GateSpec("fan_running", startup_delay_seconds=600),
    "FC12": GateSpec("fan_running", startup_delay_seconds=600),
    "FC13": GateSpec("fan_running", startup_delay_seconds=600),
    "FC14": GateSpec("fan_running", startup_delay_seconds=600),
    "FC15": GateSpec("fan_running", startup_delay_seconds=600),
    "AHU-SATDEV": GateSpec("fan_running", startup_delay_seconds=600),
    "AHU-DUCTHI": GateSpec("fan_running", startup_delay_seconds=300),
    "AHU-SIMUL": GateSpec("fan_running", startup_delay_seconds=300),
    "OAT-METEO": GateSpec("always"),
    "ECON-1": GateSpec("fan_running", startup_delay_seconds=600),
    "ECON-2": GateSpec("fan_running", startup_delay_seconds=300),
    "ECON-3": GateSpec("fan_running", startup_delay_seconds=600),
    "ECON-4": GateSpec("fan_running", startup_delay_seconds=600),
    "ECON-5": GateSpec("fan_running", startup_delay_seconds=600),
    "VAV-1": GateSpec("conditional"),
    "VAV-3": GateSpec("fan_running", startup_delay_seconds=300),
    "VAV-4": GateSpec("control_loop", startup_delay_seconds=300),
    "VAV-5": GateSpec("fan_running", startup_delay_seconds=300),
    "VAV-REHEAT": GateSpec("fan_running", startup_delay_seconds=600),
    "VAV-AHU-LEAVE": GateSpec("fan_running", startup_delay_seconds=600),
    "VAV-7": GateSpec("fan_running", startup_delay_seconds=300),
    "CHW-1": GateSpec("hydronic_flow", startup_delay_seconds=900),
    "CHW-2": GateSpec("hydronic_flow", startup_delay_seconds=300),
    "CHW-3": GateSpec("hydronic_flow", startup_delay_seconds=600),
    "CHW-4": GateSpec("hydronic_flow", startup_delay_seconds=300),
    "HP-1": GateSpec("compressor", startup_delay_seconds=600),
    "WX-1": GateSpec("always"),
    "CW-OPT-1": GateSpec("hydronic_flow", startup_delay_seconds=600),
    "TRIM-1": GateSpec("fan_running", startup_delay_seconds=300),
    "TRIM-3": GateSpec("hydronic_flow", startup_delay_seconds=600),
    "TRIM-4": GateSpec("hydronic_flow", startup_delay_seconds=600),
    "SCHED-1": GateSpec("always"),
    "CMD-1": GateSpec("always"),
    "OA-1": GateSpec("fan_running", startup_delay_seconds=600),
    "DMP-1": GateSpec("conditional", startup_delay_seconds=300),
    "VLV-1": GateSpec("conditional", startup_delay_seconds=300),
}


FAN_PROOF_ROLES = (
    "fan_status",
    "fan_speed_feedback",
    "fan_current",
    "fan_power",
    "airflow_proof",
)
FAN_CMD_FALLBACK = ("fan_cmd",)

PUMP_PROOF_ROLES = (
    "pump_status",
    "chw_pump_status",
    "hw_pump_status",
    "chw_pump_cmd",  # often used as status-like cmd in this demo
    "pump_speed_feedback",
    "pump_current",
    "chw_flow",
    "water_flow",
)
PUMP_CMD_FALLBACK = ("pump_cmd", "chw_pump_cmd", "hw_pump_cmd")

COMPRESSOR_ROLES = ("compressor_status", "equipment_enable", "fan_status", "fan_cmd")


def _series_on(series: pd.Series, *, threshold: float = 0.05) -> pd.Series:
    num = pd.to_numeric(series, errors="coerce")
    if num.notna().any():
        scaled = num.where(num <= 1.5, num / 100.0)
        return scaled.fillna(0) > threshold
    return as_bool(series)


def _first_present_on(
    df: pd.DataFrame,
    roles: tuple[str, ...],
    *,
    threshold: float = 0.05,
) -> tuple[pd.Series | None, str | None]:
    for role in roles:
        if role in df.columns and df[role].notna().any():
            return _series_on(df[role], threshold=threshold), role
    return None, None


def resolve_fan_running(df: pd.DataFrame, *, command_fallback: bool = True) -> tuple[pd.Series, str]:
    """Prefer proof/status over command. Returns (mask, source_role_or_note)."""
    mask, role = _first_present_on(df, FAN_PROOF_ROLES)
    if mask is not None and role is not None:
        return mask.fillna(False), role
    if command_fallback:
        mask, role = _first_present_on(df, FAN_CMD_FALLBACK)
        if mask is not None and role is not None:
            return mask.fillna(False), f"{role} (cmd fallback)"
    # VAV airflow proxy
    if "zone_flow" in df.columns and df["zone_flow"].notna().any():
        flow = pd.to_numeric(df["zone_flow"], errors="coerce").fillna(0)
        return (flow > 50.0), "zone_flow"
    return pd.Series(True, index=df.index), "ungated_no_proof_roles"


def resolve_hydronic_running(df: pd.DataFrame, *, command_fallback: bool = True) -> tuple[pd.Series, str]:
    mask, role = _first_present_on(df, PUMP_PROOF_ROLES, threshold=0.05)
    if mask is not None and role is not None:
        # chw_pump_cmd in proof list — treat like speed/cmd
        return mask.fillna(False), role
    if command_fallback:
        mask, role = _first_present_on(df, PUMP_CMD_FALLBACK)
        if mask is not None and role is not None:
            return mask.fillna(False), f"{role} (cmd fallback)"
    return pd.Series(True, index=df.index), "ungated_no_proof_roles"


def resolve_compressor_running(df: pd.DataFrame, *, command_fallback: bool = True) -> tuple[pd.Series, str]:
    for role in COMPRESSOR_ROLES:
        if role in df.columns and df[role].notna().any():
            if role == "fan_cmd" and not command_fallback:
                continue
            return _series_on(df[role]).fillna(False), role
    return pd.Series(True, index=df.index), "ungated_no_proof_roles"


def resolve_conditional(df: pd.DataFrame, rule_id: str) -> tuple[pd.Series, str]:
    """Point/context-aware gates for CONDITIONAL rules."""
    if rule_id == "VAV-1":
        if "occ_mode" in df.columns and df["occ_mode"].notna().any():
            occ = df["occ_mode"].astype(str).str.lower().isin({"occupied", "1", "true", "on"})
            return occ.fillna(False), "occ_mode"
        # Prefer evaluating comfort continuously if no schedule — do not hard-exclude.
        return pd.Series(True, index=df.index), "ungated_no_occ"
    if rule_id == "DMP-1":
        fan, src = resolve_fan_running(df)
        if "oa_damper_pct" in df.columns:
            cmd = norm_cmd(df["oa_damper_pct"]).fillna(0) > 0.01
            return (fan | cmd).fillna(False), f"damper_or_{src}"
        return fan, src
    if rule_id == "VLV-1":
        if "clg_valve_pct" in df.columns:
            valve = norm_cmd(df["clg_valve_pct"]).fillna(0)
            # Evaluate when valve has demand OR when commanded closed (leakage context).
            active = (valve > 0.01) | (valve <= 0.05)
            fan, _ = resolve_fan_running(df)
            return (active & fan).fillna(False), "valve_and_fan"
        fan, src = resolve_fan_running(df)
        return fan, src
    if rule_id == "SV-FLATLINE":
        # Soft gate: always allow OAT-like continuous sensors; runner still evaluates full mask.
        # Prefer fan-on periods when fan proof exists (reduces off-period stuck false positives).
        fan, src = resolve_fan_running(df)
        if src.startswith("ungated"):
            return pd.Series(True, index=df.index), "flatline_always"
        return fan, f"flatline_{src}"
    return pd.Series(True, index=df.index), "conditional_default"


def apply_startup_delay(active: pd.Series, poll_seconds: float, delay_seconds: float) -> pd.Series:
    """Require continuous run for delay_seconds before samples count as active."""
    if delay_seconds <= 0:
        return active.fillna(False)
    rows = max(1, int(np.ceil(delay_seconds / max(poll_seconds, 1.0))))
    on = active.fillna(False).astype(bool)
    groups = (on != on.shift()).cumsum()
    streak = on.groupby(groups).cumcount() + 1
    return on & (streak >= rows)


def resolve_operational_mask(
    df: pd.DataFrame,
    rule_id: str,
    *,
    poll_seconds: float,
    params: dict | None = None,
    gate_enabled: bool = True,
) -> tuple[pd.Series, dict]:
    """
    Return (active_mask, meta).

    When gate_enabled is False or kind is always → all True.
    When no proof roles exist → ungated (all True) with meta note (cannot prove off).
    """
    params = params or {}
    spec = RULE_GATES.get(rule_id, GateSpec("always"))
    meta: dict = {
        "gate_kind": spec.kind,
        "gate_applied": False,
        "gate_source": "always",
        "active_sample_count": int(len(df)),
        "active_coverage_pct": 100.0,
    }

    require = bool(int(float(params.get("require_operational_gate", 1 if spec.kind != "always" else 0))))
    if not gate_enabled or spec.kind == "always" or not require:
        active = pd.Series(True, index=df.index)
        meta["gate_source"] = "disabled" if not gate_enabled or not require else "always"
        return active, meta

    if spec.kind == "fan_running":
        active, src = resolve_fan_running(df, command_fallback=spec.command_fallback_allowed)
    elif spec.kind == "hydronic_flow":
        active, src = resolve_hydronic_running(df, command_fallback=spec.command_fallback_allowed)
    elif spec.kind == "compressor":
        active, src = resolve_compressor_running(df, command_fallback=spec.command_fallback_allowed)
    elif spec.kind == "control_loop":
        active, src = resolve_fan_running(df, command_fallback=spec.command_fallback_allowed)
        if "loop_enabled" in df.columns:
            active = active & _series_on(df["loop_enabled"])
            src = f"{src}+loop_enabled"
    elif spec.kind == "conditional":
        active, src = resolve_conditional(df, rule_id)
    else:
        active, src = pd.Series(True, index=df.index), "always"

    if src.startswith("ungated"):
        meta["gate_source"] = src
        return pd.Series(True, index=df.index), meta

    delay = float(params.get("startup_delay_min", spec.startup_delay_seconds / 60.0)) * 60.0
    active = apply_startup_delay(active, poll_seconds, delay)
    n_active = int(active.sum())
    cov = 100.0 * n_active / max(len(df), 1)
    meta.update(
        {
            "gate_applied": True,
            "gate_source": src,
            "active_sample_count": n_active,
            "active_coverage_pct": round(cov, 1),
            "startup_delay_seconds": delay,
        }
    )
    return active.fillna(False), meta


def should_skip_equipment_off(meta: dict, params: dict | None = None, spec: GateSpec | None = None) -> bool:
    """True when gate applied but almost no active samples in the window."""
    params = params or {}
    if not meta.get("gate_applied"):
        return False
    min_cov = float(
        params.get(
            "minimum_active_coverage_pct",
            (spec.minimum_active_coverage_pct if spec else 80.0),
        )
    )
    # Skip only when essentially off (very low coverage), not when partially on.
    # Use a floor: if active_sample_count == 0 → always skip; if coverage < 5% also skip.
    if int(meta.get("active_sample_count", 0)) == 0:
        return True
    # If user sets a high minimum_active_coverage_pct, honor it for skip.
    if float(meta.get("active_coverage_pct", 100)) < min(min_cov, 5.0):
        return True
    return int(meta.get("active_sample_count", 0)) == 0
