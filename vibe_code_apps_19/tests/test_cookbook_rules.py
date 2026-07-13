"""Tests for all canonical cookbook rules."""

from __future__ import annotations

import pandas as pd
import pytest
import yaml

from app.rules import CANONICAL_RULE_COUNT, CANONICAL_RULES, RULES, RULES_BY_ID, run_rule
from app.rules.base import RuleResult
from app.rules.runner import run_all_cookbook_rules
from tests.point_names import canon_point_cols


def test_canonical_count():
    assert CANONICAL_RULE_COUNT == 55
    assert len(CANONICAL_RULES) == 55
    assert len(RULES) >= 51
    # Custom extras never replace canonical ids
    canonical_ids = {r.id for r in CANONICAL_RULES}
    assert canonical_ids <= {r.id for r in RULES}
    assert "VAV-AHU-LEAVE" in RULES_BY_ID


def test_inventory_metadata():
    from pathlib import Path

    inv = yaml.safe_load((Path(__file__).parent.parent / "configs" / "rule_inventory.yaml").read_text(encoding="utf-8"))
    assert inv["canonical_rule_count"] == 55
    assert len(inv["rules"]) == 55


@pytest.mark.parametrize("rule_id", [r.id for r in CANONICAL_RULES])
def test_every_rule_imports(rule_id: str):
    assert rule_id in RULES_BY_ID


@pytest.mark.parametrize("rule_id", [r.id for r in CANONICAL_RULES])
def test_skip_when_roles_missing(rule_id: str):
    idx = pd.date_range("2024-06-01", periods=5, freq="5min", tz="UTC")
    df = pd.DataFrame(index=idx)
    df.attrs["equipment_id"] = "TEST_EQ"
    r = run_rule(rule_id, df, {}, 300.0)
    assert isinstance(r, RuleResult)
    assert r.status in ("SKIPPED_MISSING_ROLES", "NOT_APPLICABLE_EQUIPMENT_TYPE", "PASS", "FAULT", "ERROR")
    if r.status == "SKIPPED_MISSING_ROLES":
        assert not r.applicable
        assert r.missing_roles
    if r.status == "NOT_APPLICABLE_EQUIPMENT_TYPE":
        assert not r.applicable


def _ahu_df(**cols) -> pd.DataFrame:
    cols = canon_point_cols(cols)
    n = len(next(iter(cols.values())))
    idx = pd.date_range("2024-06-01", periods=n, freq="5min", tz="UTC")
    df = pd.DataFrame(cols, index=idx)
    df.attrs["equipment_id"] = "AHU_1"
    return df


def test_fc2_runs_with_roles():
    """Smoke path kept; mix_tol sensitivity lives in test_rule_param_sensitivity.py."""
    df = _ahu_df(
        mat=[70, 70, 65, 65, 65],
        rat=[70, 70, 70, 70, 70],
        oa_t=[30, 30, 30, 30, 30],
        fan_cmd=[50, 50, 50, 50, 50],
    )
    r = run_rule("FC2", df, {"confirm_min": 0, "mix_tol": 1.15}, 300.0, require_operational_gates=False)
    assert r.applicable
    assert r.status in ("PASS", "FAULT")


def test_vav1_runs_with_roles():
    df = _ahu_df(zone_t=[72, 72, 65, 78, 72])
    df.attrs["equipment_id"] = "VAV_7"
    r = run_rule("VAV-1", df, {"zone_lo": 70, "zone_hi": 75, "confirm_min": 0}, 300.0)
    assert r.applicable
    assert r.status == "FAULT"


def test_run_all_returns_active_catalog():
    idx = pd.date_range("2024-06-01", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame({"outside-air-temp": [70, 71, 72]}, index=idx)
    df.attrs["equipment_id"] = "AHU_1"
    results = run_all_cookbook_rules(df, equipment_id="AHU_1", poll_seconds=300.0)
    assert len(results) == len(RULES)
    assert sum(1 for r in results if not str(r.rule_id).startswith("CUSTOM-")) == 55


def test_result_shape():
    idx = pd.date_range("2024-06-01", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame(index=idx)
    df.attrs["equipment_id"] = "X"
    r = run_rule("FC1", df, {}, 300.0)
    d = r.to_dict()
    for key in ("rule_id", "equipment_id", "site_id", "building_id", "equipment_type", "status", "applicable", "missing_roles", "notes"):
        assert key in d


def test_vlv1_closed_valve_sat_below_sp_fault():
    df = _ahu_df(
        sat=[50.0] * 6,
        sat_sp=[55.0] * 6,
        clg_valve_pct=[0.0] * 6,
        fan_status=[1.0] * 6,
        mat=[60.0] * 6,
    )
    r = run_rule("VLV-1", df, {"confirm_min": 0, "sat_err": 2.0, "mat_leak_delta": 2.0}, 300.0)
    assert r.status == "FAULT"


def test_vlv1_sat_above_low_sp_but_below_mat_fault():
    """Graphic-like: DAT~74, SP~50 (reset), MAT~80, valve closed → leak via MAT path."""
    df = _ahu_df(
        sat=[74.0] * 6,
        sat_sp=[50.0] * 6,
        clg_valve_pct=[2.0] * 6,
        fan_status=[1.0] * 6,
        mat=[80.0] * 6,
    )
    r = run_rule("VLV-1", df, {"confirm_min": 0, "sat_err": 2.0, "mat_leak_delta": 2.0}, 300.0)
    assert r.status == "FAULT"


def test_vlv1_fan_off_skipped_equipment_off():
    df = _ahu_df(
        sat=[50.0] * 6,
        sat_sp=[55.0] * 6,
        clg_valve_pct=[0.0] * 6,
        fan_status=[0.0] * 6,
        mat=[60.0] * 6,
    )
    r = run_rule("VLV-1", df, {"confirm_min": 0}, 300.0)
    assert r.status == "SKIPPED_EQUIPMENT_OFF"


def test_sched1_unocc_fan_zone_in_band_fault():
    df = _ahu_df(
        occ_mode=["unoccupied"] * 6,
        fan_status=[1.0] * 6,
        zone_t=[72.0] * 6,
    )
    r = run_rule(
        "SCHED-1",
        df,
        {"confirm_min": 0, "comfort_low_f": 70.0, "comfort_high_f": 75.0},
        300.0,
    )
    assert r.status == "FAULT"


def test_sched1_unocc_fan_zone_outside_band_pass():
    df = _ahu_df(
        occ_mode=["unoccupied"] * 6,
        fan_status=[1.0] * 6,
        zone_t=[80.0] * 6,
    )
    r = run_rule(
        "SCHED-1",
        df,
        {"confirm_min": 0, "comfort_low_f": 70.0, "comfort_high_f": 75.0},
        300.0,
    )
    assert r.status == "PASS"


def test_sched1_no_zone_t_backward_compatible_fault():
    df = _ahu_df(
        occ_mode=["unoccupied"] * 6,
        fan_status=[1.0] * 6,
    )
    r = run_rule("SCHED-1", df, {"confirm_min": 0}, 300.0)
    assert r.status == "FAULT"


def test_vlv1_and_sched1_inventory_and_catalog_params():
    """Keep inventory + CookbookRule metadata aligned so agents don't drop tunables."""
    from pathlib import Path

    inv = yaml.safe_load(
        (Path(__file__).parent.parent / "configs" / "rule_inventory.yaml").read_text(encoding="utf-8")
    )
    by_id = {r["rule_id"]: r for r in inv["rules"]}

    vlv = RULES_BY_ID["VLV-1"]
    assert "mixed-air-temp" in vlv.optional_roles
    assert "fan-status" in vlv.optional_roles
    assert {p.key for p in vlv.params} >= {"sat_err", "mat_leak_delta", "confirm_min"}
    inv_vlv = by_id["VLV-1"]
    assert "mixed-air-temp" in inv_vlv["optional_roles"]
    assert set(inv_vlv["tunable_params"]) >= {"sat_err", "mat_leak_delta", "confirm_min"}

    sched = RULES_BY_ID["SCHED-1"]
    assert "zone-air-temp" in sched.optional_roles
    assert {p.key for p in sched.params} >= {"comfort_low_f", "comfort_high_f", "confirm_min"}
    inv_sched = by_id["SCHED-1"]
    assert "zone-air-temp" in inv_sched["optional_roles"]
    assert set(inv_sched["tunable_params"]) >= {"comfort_low_f", "comfort_high_f", "confirm_min"}
    assert "occupied" in inv_sched["description"] or "calendar" in inv_sched["description"].lower()


def test_vlv1_pass_when_valve_open():
    df = _ahu_df(
        sat=[50.0] * 6,
        sat_sp=[55.0] * 6,
        clg_valve_pct=[40.0] * 6,
        fan_status=[1.0] * 6,
        mat=[60.0] * 6,
    )
    r = run_rule("VLV-1", df, {"confirm_min": 0}, 300.0)
    assert r.status == "PASS"
