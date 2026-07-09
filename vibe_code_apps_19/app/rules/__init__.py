"""Rule registry for Streamlit demo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from app.rules import ahu_rules, economizer_rules, fan_rules, vav_rules
from app.rules.base import RuleResult

RuleFn = Callable[..., RuleResult]


@dataclass
class RuleSpec:
    rule_id: str
    label: str
    required_roles: list[str]
    default_confirm_minutes: float
    config_key: str
    fn: RuleFn
    needs_weather: bool = False


RULES: list[RuleSpec] = [
    RuleSpec("FAN-RUNTIME", "Fan runtime hours", ["fan_cmd"], 0, "fan_runtime", fan_rules.fan_runtime_hours),
    RuleSpec("VAV-1", "VAV comfort band", ["zone_t"], 15, "vav_1", vav_rules.vav_comfort_fault),
    RuleSpec("AVG-ZONE-TEMP", "Average zone temp", ["zone_t"], 0, "vav_1", vav_rules.avg_zone_temp),
    RuleSpec("ZONE-COMFORT-PCT", "Zone comfort %", ["zone_t"], 0, "vav_1", vav_rules.zone_comfort_pct),
    RuleSpec("SAT-HIGH", "SAT above SP (FC13-style)", ["sat", "sat_sp", "clg_valve_pct", "oa_damper_pct"], 10, "sat_high", ahu_rules.sat_high_fault),
    RuleSpec("ECON-2", "Economizing when unfavorable", ["oa_t", "oa_damper_pct"], 5, "econ_2", economizer_rules.economizer_unfavorable),
    RuleSpec("ECON-1", "Economizer stuck closed", ["oa_t", "oa_damper_pct", "fan_cmd"], 10, "econ_1", economizer_rules.econ_stuck_closed),
    RuleSpec("OAT-METEO", "OAT vs weather", ["oa_t"], 15, "oat_meteo", economizer_rules.oat_meteo_fault, needs_weather=True),
    RuleSpec("FC2-MAT-LOW", "Mixed air low (FC2)", ["mat", "rat", "oa_t", "fan_cmd"], 10, "fc2", ahu_rules.fc2_mat_low),
]

RULES_BY_ID = {r.rule_id: r for r in RULES}


def run_rule(spec: RuleSpec, df: pd.DataFrame, params: dict, poll_seconds: float, weather: pd.DataFrame | None = None) -> RuleResult:
    confirm_min = float(params.pop("_confirm_minutes", spec.default_confirm_minutes))
    confirm_seconds = confirm_min * 60.0
    if spec.needs_weather:
        return spec.fn(df, weather, params, poll_seconds, confirm_seconds)
    return spec.fn(df, params, poll_seconds, confirm_seconds)


def run_all(df: pd.DataFrame, params_by_rule: dict[str, dict], poll_seconds: float, weather: pd.DataFrame | None = None) -> list[RuleResult]:
    results = []
    for spec in RULES:
        p = dict(params_by_rule.get(spec.rule_id, {}))
        try:
            results.append(run_rule(spec, df, p, poll_seconds, weather))
        except Exception as exc:
            from app.rules.base import RuleResult
            import pandas as pd

            results.append(
                RuleResult(
                    rule_id=spec.rule_id,
                    equipment_id=df.attrs.get("equipment_id", ""),
                    raw_fault=pd.Series(False, index=df.index),
                    confirmed_fault=pd.Series(False, index=df.index),
                    fault_hours=0.0,
                    fault_pct=0.0,
                    total_hours=0.0,
                    message=f"skip: {exc}",
                )
            )
    return results
