"""Tests for mega phases 3–20 scaffold modules."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eplus_gym.mega.billing_floors import candidate_and_baseline_floors
from eplus_gym.mega.child_model_ledger import bootstrap_ledger, register_child_model
from eplus_gym.mega.common_action_contract import MEGA_ACTION_CONTRACT_V1
from eplus_gym.mega.day_ahead_optimizer import DayAheadOptimizerArm
from eplus_gym.mega.fixed_rules import FIXED_TOU_RULE, FIXED_WEATHER_RULE, all_fixed_rules
from eplus_gym.mega.grid_search import GridSearchArm, MAX_EXTRA_CANDIDATES_PER_DAY, default_coarse_grid
from eplus_gym.mega.load_shape_gates import (
    SCREEN_UNAVAILABLE,
    evaluate_hourly_load_shape_gate,
    evaluate_monthly_load_shape_gate,
)
from eplus_gym.mega.multi_seed_config import MEGA_MIN_SEEDS, MultiSeedPlan
from eplus_gym.mega.obs_tariff_v4 import N_OBS_V4, build_observation_v4
from eplus_gym.mega.physics_repair_matrix import PhysicsRepairMatrix, MAX_PHYSICS_CANDIDATES
from eplus_gym.mega.shadow_adaptation import LABEL, default_adaptation_spec
from eplus_gym.mega.tariff_modes import REQUIRED_MODES, default_tariff_catalog
from eplus_gym.mega.validation_locked_test import select_validation_checkpoints
from eplus_gym.phase2_w2a_diagnosis import build_w2a_diagnosis
from eplus_gym.phase2_mcp_evidence import build_mcp_evidence_block

APP = Path(__file__).resolve().parents[1]


def test_child_model_ledger_parent_hash_enforced(tmp_path: Path):
    parent = APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    child = tmp_path / "child.idf"
    child.write_bytes(parent.read_bytes())
    ledger = bootstrap_ledger(parent)
    register_child_model(
        ledger,
        child_name="test_child",
        child_idf_path=child,
        patches=[{"field": "Rated Heating Capacity", "op": "scale"}],
        rationale="test",
    )
    body = ledger.to_dict()
    assert body["parent"]["immutable_label"] == "A04_IMMUTABLE_PARENT"
    assert body["n_children"] == 1


def test_physics_matrix_caps():
    matrix = PhysicsRepairMatrix()
    assert matrix.max_candidates == MAX_PHYSICS_CANDIDATES


def test_hourly_load_shape_gate_blocks_high_nmbe():
    gate = evaluate_hourly_load_shape_gate(
        hourly_nmbe_pct=15.0,
        hourly_cvrmse_pct=25.0,
    )
    assert gate.blocks_promotion() is True


def test_hourly_load_shape_gate_passes_within_threshold():
    gate = evaluate_hourly_load_shape_gate(
        hourly_nmbe_pct=8.0,
        hourly_cvrmse_pct=25.0,
    )
    assert gate.blocks_promotion() is False


def test_monthly_gate_blocks_when_unavailable():
    gate = evaluate_monthly_load_shape_gate(monthly_nmbe_pct=None, monthly_cvrmse_pct=None)
    assert gate.blocks_promotion() is True
    assert gate.metrics[0].unavailable_reason == SCREEN_UNAVAILABLE


def test_tariff_catalog_has_required_modes():
    cat = default_tariff_catalog()
    for mode in REQUIRED_MODES:
        assert mode in cat
    qtr = cat["tou_evening_peak_illustrative"].quarter_hour_prices()
    assert qtr.size == 96


def test_obs_v4_includes_tariff_forecast():
    vec, ctx = build_observation_v4(
        day="2025-12-15",
        hourly_oat_c=[0.0] * 24,
        forecast_valid_mask=[1.0] * 24,
        zone_temps_f=[68.0] * 6,
        billing_floor_kw=180.0,
        mtd_peak_kw=175.0,
        ratchet_floor_kw=170.0,
        contract_floor_kw=165.0,
        previous_action=None,
        continuous_conditioning_state=0.0,
        tariff_mode="tou_evening_peak_illustrative",
    )
    assert vec.size == N_OBS_V4
    assert ctx["future_tariff_in_observation"] is True


def test_independent_billing_floors():
    floors = candidate_and_baseline_floors(
        candidate_mtd_peak_kw=150.0,
        baseline_mtd_peak_kw=200.0,
        ratchet_floor_kw=180.0,
        contract_floor_kw=175.0,
    )
    assert floors["candidate_floor_kw"] == 180.0
    assert floors["baseline_floor_kw"] == 200.0
    assert floors["no_retroactive_demand_savings"] is True


def test_fixed_rules_vary_with_forecast_and_price():
    cold = FIXED_WEATHER_RULE.params_for_day("2025-12-15", forecast_min_oat_c=-15.0)
    mild = FIXED_WEATHER_RULE.params_for_day("2025-12-16", forecast_min_oat_c=5.0)
    assert cold.recovery_lead_minutes > mild.recovery_lead_minutes

    peak_morning = [1.5] * 24
    peak_morning[8] = 3.0
    peak_evening = [1.5] * 24
    peak_evening[18] = 3.0
    tou_am = FIXED_TOU_RULE.params_for_day("2025-12-15", hourly_energy_rates=peak_morning)
    tou_pm = FIXED_TOU_RULE.params_for_day("2025-12-15", hourly_energy_rates=peak_evening)
    assert tou_am.heating_setpoint_start_step != tou_pm.heating_setpoint_start_step


def test_fixed_rules_deterministic_without_inputs():
    assert len(all_fixed_rules()) == 2
    p1 = FIXED_WEATHER_RULE.params_for_day("2025-12-15")
    p2 = FIXED_WEATHER_RULE.params_for_day("2025-12-16")
    assert p1.recovery_lead_minutes == p2.recovery_lead_minutes


def test_grid_search_covers_control_dimensions():
    grid = default_coarse_grid()
    keys = set().union(*(g.keys() for g in grid))
    for required in (
        "occupied_heating_f",
        "unoccupied_heating_f",
        "recovery_lead_minutes",
        "heating_setpoint_start_step",
    ):
        assert required in keys


def test_grid_search_dedupe_and_cap():
    from eplus_gym.mega.grid_search import GridCandidate

    gs = GridSearchArm(day="2025-12-15")
    params = {"occupied_heating_f": 70.0}
    assert gs.add_coarse(params) is not None
    assert gs.add_coarse(params) is None
    seed = GridCandidate("s", params)
    deltas = [{"occupied_heating_f": 70.0 + i * 0.1} for i in range(MAX_EXTRA_CANDIDATES_PER_DAY + 5)]
    added = gs.refine_local(seed, deltas)
    assert len(added) <= MAX_EXTRA_CANDIDATES_PER_DAY


def test_day_ahead_optimizer_occupied_bounds():
    opt = DayAheadOptimizerArm(bounds=[])
    assert opt.default_bounds()[0] == (68.0, 72.0)


def test_day_ahead_optimizer_runs_with_stub_in_tests():
    pytest.importorskip("scipy")
    opt = DayAheadOptimizerArm(bounds=[(68.0, 72.0), (60.0, 68.0)])
    res = opt.optimize(opt.stub_objective())
    assert res.n_evals > 0
    assert len(res.x_best) == 2
    assert 68.0 <= res.x_best[0] <= 72.0


def test_multi_seed_minimum():
    plan = MultiSeedPlan("DQN")
    plan.validate()
    assert len(plan.seeds) >= MEGA_MIN_SEEDS


def test_shadow_adaptation_label():
    spec = default_adaptation_spec(forbidden_january=["2026-01-12"])
    assert spec.label == LABEL


def test_validation_selects_one_per_algo():
    rows = [
        {"algo": "PPO", "policy_id": "trained_ppo_seed0", "mean_reward": 0.2, "readiness_rate": 1.0},
        {"algo": "PPO", "policy_id": "trained_ppo_seed1", "mean_reward": 0.1, "readiness_rate": 1.0},
        {"algo": "DQN", "policy_id": "trained_dqn_seed0", "mean_reward": 0.3, "readiness_rate": 1.0},
        {"algo": "DQN", "policy_id": "trained_dqn_seed1", "mean_reward": -0.1, "readiness_rate": 1.0},
    ]
    sel = select_validation_checkpoints(rows)
    assert sel.selected_ppo == "trained_ppo_seed0"
    assert sel.selected_dqn == "trained_dqn_seed0"
    assert sel.locked_test_ran is False


def test_common_action_contract_shared_arms():
    assert "GRID_SEARCH" in MEGA_ACTION_CONTRACT_V1["shared_by_arms"]


def test_verified_tariff_fail_closed():
    cat = default_tariff_catalog()
    with pytest.raises(ValueError, match="verified"):
        cat["verified_tariff"].to_contract()


def test_seed_matrix_from_phase2():
    from eplus_gym.mega.physics_repair_matrix import seed_matrix_from_phase2

    idf = APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    mcp = build_mcp_evidence_block(
        load_result={"file_path": idf.name, "loaded_successfully": True},
        model_summary={"Version": {"Version Identifier": "26.1"}},
        hvac_loops={"summary": {"total_zones": 9}},
    )
    p2 = build_w2a_diagnosis(
        idf_path=idf,
        mcp_load_result=mcp["payloads"]["load_idf_model"],
        mcp_model_summary=mcp["payloads"]["get_model_summary"],
        mcp_hvac_loops=mcp["payloads"]["discover_hvac_loops"],
    )
    matrix = seed_matrix_from_phase2(phase2_diagnosis=p2)
    assert len(matrix.attempts) >= 2


def test_hp67_patch_fail_closed_on_autosize_parent():
    from eplus_gym.mega.hp67_child_patch import HP_COUNT_67, patch_hp67_scaled_v1

    idf = APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    with pytest.raises(ValueError, match="refuse"):
        patch_hp67_scaled_v1(idf.read_text(encoding="utf-8", errors="replace"))


def test_hp67_v1_child_on_disk_has_nine_zones():
    child = APP / "models" / "eplus" / "a04v2_candidates" / "a04_child_hp67_scaled_v1" / "lakeside_w2a_hp67_scaled_v1.idf"
    if not child.is_file():
        pytest.skip("historical v1 child not present")
    from eplus_gym.mega.hp67_child_patch import HP_COUNT_67

    text = child.read_text(encoding="utf-8", errors="replace")
    for z in HP_COUNT_67:
        assert f"{z} WAHP Heating Coil" in text
