"""50-rule Open-FDD pandas cookbook registry."""

from app.rules.base import RuleResult
from app.rules.cookbook_catalog import RULES, RULES_BY_ID, catalog
from app.rules.runner import infer_equipment_kind, run_all_cookbook_rules, run_batch, run_cookbook_rule

CANONICAL_RULE_COUNT = len(RULES)


def run_all(
    df,
    params_by_rule: dict | None = None,
    poll_seconds: float = 300.0,
    weather=None,
) -> list[RuleResult]:
    eq = df.attrs.get("equipment_id", "")
    return run_all_cookbook_rules(
        df,
        equipment_id=eq,
        poll_seconds=poll_seconds,
        params_by_rule=params_by_rule,
        weather=weather,
    )


def run_rule(rule_id: str, df, params: dict | None = None, poll_seconds: float = 300.0, weather=None) -> RuleResult:
    rule = RULES_BY_ID[rule_id]
    return run_cookbook_rule(
        rule,
        df,
        equipment_id=df.attrs.get("equipment_id", ""),
        equipment_kind=infer_equipment_kind(df.attrs.get("equipment_id", "")),
        poll_seconds=poll_seconds,
        params_by_rule={rule_id: params or {}},
        weather=weather,
    )


__all__ = [
    "RULES",
    "RULES_BY_ID",
    "CANONICAL_RULE_COUNT",
    "RuleResult",
    "catalog",
    "infer_equipment_kind",
    "run_all",
    "run_rule",
    "run_all_cookbook_rules",
    "run_batch",
    "run_cookbook_rule",
]
