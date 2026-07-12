"""Tests for shared rule-card builder (params + mapping coverage)."""

from __future__ import annotations

import pandas as pd

from app.rule_card import (
    build_rule_card,
    equipment_mapping_coverage,
    filter_status_bucket,
    param_rows_for_rule,
)
from app.rules import RULES_BY_ID
from app.rules.base import RuleResult


def test_build_rule_card_mapping_present_and_missing():
    rule = RULES_BY_ID["VLV-1"]
    idx = pd.date_range("2024-06-01", periods=4, freq="5min", tz="UTC")
    mapped = pd.DataFrame(
        {
            "sat": [55.0] * 4,
            "sat_sp": [55.0] * 4,
            "clg_valve_pct": [0.0] * 4,
            "fan_status": [1.0] * 4,
        },
        index=idx,
    )
    role_map = {
        "AHU_1": {
            "equipment_type": "AHU",
            "discharge_air_temp_f": "sat",
            "sat_sp_f": "sat_sp",
            "clg_v": "clg_valve_pct",
            # mat intentionally unmapped
        }
    }
    card = build_rule_card(
        equipment_id="AHU_1",
        rule=rule,
        result=None,
        role_map=role_map,
        mapped_df=mapped,
        params={"VLV-1": {"confirm_min": 2.0}},
    )
    assert card.rule_id == "VLV-1"
    assert card.status == "NOT_RUN"
    roles = {m.role: m for m in card.mapping_rows}
    assert "clg_valve_pct" in roles
    assert roles["clg_valve_pct"].in_history is True
    assert roles["clg_valve_pct"].csv_column == "clg_v"
    assert roles["clg_valve_pct"].requirement == "required"
    # Param merge: session override wins
    keys = {p.key: p for p in card.param_rows}
    assert "confirm_min" in keys
    assert keys["confirm_min"].value == 2.0
    assert keys["confirm_min"].source == "override"


def test_param_rows_defaults_when_no_override():
    rule = RULES_BY_ID["VLV-1"]
    rows = param_rows_for_rule(rule, {})
    assert rows
    assert all(p.source == "default" for p in rows)


def test_equipment_mapping_coverage_union():
    rules = [RULES_BY_ID["VLV-1"]]
    mapped = pd.DataFrame({"sat": [1.0], "clg_valve_pct": [0.0]})
    role_map = {"AHU_1": {"c": "clg_valve_pct", "s": "sat"}}
    present, total, pct = equipment_mapping_coverage(rules, "AHU_1", role_map, mapped)
    assert total >= 1
    assert present >= 1
    assert 0 <= pct <= 100


def test_filter_status_bucket():
    assert filter_status_bucket("FAULT") == "FAULT"
    assert filter_status_bucket("PASS") == "PASS"
    assert filter_status_bucket("SKIPPED_MISSING_ROLES") == "SKIPPED"
    assert filter_status_bucket("NOT_RUN") == "Not run"
    assert filter_status_bucket("NOT_APPLICABLE_EQUIPMENT_TYPE") == "SKIPPED"


def test_build_rule_card_with_result_status():
    rule = RULES_BY_ID["VLV-1"]
    res = RuleResult(
        rule_id="VLV-1",
        equipment_id="AHU_1",
        status="FAULT",
        applicable=True,
        fault_hours=1.5,
        missing_roles=[],
        notes="leak",
    )
    card = build_rule_card(
        equipment_id="AHU_1",
        rule=rule,
        result=res,
        role_map={"AHU_1": {}},
        mapped_df=pd.DataFrame(),
        params=None,
    )
    assert card.status == "FAULT"
    assert card.fault_hours == 1.5
    assert card.has_result is True


def test_build_rule_card_catalog_parity_fields():
    rule = RULES_BY_ID["SV-SPIKE"]
    card = build_rule_card(
        equipment_id="AHU_1",
        rule=rule,
        result=None,
        role_map={"AHU_1": {}},
        mapped_df=pd.DataFrame(),
        params=None,
    )
    assert card.gate_mode.startswith("always")
    assert card.confirm_seconds == 300.0
    assert card.sensor_sweep is True
    assert card.sweep_label == "sensor_sweep"
    assert any("confirmed_fault" in b for b in card.plot_series)
    assert "sensor-fault" in card.analytics_hint.lower() or "FAULT" in card.analytics_hint
    assert card.catalog_facts
    keys = {p.key: p for p in card.param_rows}
    assert "spike_scale" in keys
    assert keys["spike_scale"].min <= keys["spike_scale"].default <= keys["spike_scale"].max
