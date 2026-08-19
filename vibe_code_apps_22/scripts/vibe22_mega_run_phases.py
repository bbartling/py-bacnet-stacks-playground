"""Orchestrate mega phases 2–20 — fail-closed contract/scaffold status only.

Never writes synthetic experiment metrics to docs/audits/figures/vibe22_mega/.
Contract examples go to tests/fixtures/mega/EXAMPLE_NOT_EXPERIMENT_RESULT/.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.mega.billing_floors import candidate_and_baseline_floors
from eplus_gym.mega.common_action_contract import contract_manifest
from eplus_gym.mega.fixed_rules import arm_manifest
from eplus_gym.mega.grid_search import GridSearchArm, default_coarse_grid
from eplus_gym.mega.multi_seed_config import mega_training_bundle
from eplus_gym.mega.obs_tariff_v4 import build_observation_v4
from eplus_gym.mega.shadow_adaptation import default_adaptation_spec
from eplus_gym.mega.tariff_modes import REQUIRED_MODES, default_tariff_catalog
from eplus_gym.mega.validation_locked_test import NO_PRISTINE_LOCKED_TEST

FIXTURES = _APP / "tests" / "fixtures" / "mega" / "EXAMPLE_NOT_EXPERIMENT_RESULT"
STATUS_PATH = _APP / "docs" / "audits" / "figures" / "vibe22_mega" / "mega_run_status.json"

EXAMPLE_LABEL = "EXAMPLE_NOT_EXPERIMENT_RESULT"


def _write_example(phase: int, filename: str, body: dict[str, Any]) -> dict[str, Any]:
    payload = {
        **body,
        "label": EXAMPLE_LABEL,
        "phase_status": body.get("phase_status", "CONTRACT_ONLY"),
    }
    out = FIXTURES / f"phase{phase}" / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def run_all(*, start_phase: int = 2) -> dict[str, object]:
    phase_status: dict[str, str] = {}
    artifacts: dict[str, object] = {}

    phase_status["2"] = "NOT_RUN"
    artifacts["phase2"] = {
        "note": "Use feat/vibe22-mega-phase2-w2a-diagnosis branch and PR #111 CLI with MCP evidence.",
        "audit_path": "docs/audits/figures/vibe22_mega_phase2/phase2_w2a_diagnosis.json",
    }

    if start_phase <= 3:
        phase_status["3"] = "SCAFFOLD_ONLY"
        artifacts["phase3"] = _write_example(
            3,
            "child_model_ledger_schema.json",
            {
                "schema": "vibe22.mega.child_model_ledger.v1",
                "phase_status": "SCAFFOLD_ONLY",
                "note": "Real child hashes require patched IDF on disk — see a04_child_hp67_scaled_v1.",
            },
        )

    if start_phase <= 4:
        phase_status["4"] = "BLOCKED_BY_PHYSICS"
        artifacts["phase4"] = _write_example(
            4,
            "physics_repair_matrix_schema.json",
            {
                "schema": "vibe22.mega.physics_repair_matrix.v1",
                "phase_status": "BLOCKED_BY_PHYSICS",
                "note": "LIVE_EPLUS_COMPLETE requires child-model scored runs with ERR/EIO evidence.",
            },
        )

    if start_phase <= 5:
        phase_status["5"] = "NOT_RUN"
        artifacts["phase5"] = _write_example(
            5,
            "load_shape_gate_schema.json",
            {
                "schema": "vibe22.mega.load_shape_promotion_gate.v1",
                "phase_status": "NOT_RUN",
                "hourly_thresholds": {"nmbe_abs_pct": 10.0, "cvrmse_pct": 30.0},
                "monthly_thresholds": {"nmbe_abs_pct": 5.0, "cvrmse_pct": 15.0},
                "note": "No hardcoded correlation/timing demonstration values.",
            },
        )

    if start_phase <= 6:
        catalog = default_tariff_catalog()
        modes_out = {
            "schema": "vibe22.mega.tariff_catalog.v1",
            "phase_status": "CONTRACT_ONLY",
            "modes": list(REQUIRED_MODES),
            "specs": {k: v.to_dict() if hasattr(v, "to_dict") else str(v) for k, v in catalog.items()},
        }
        artifacts["phase6"] = _write_example(6, "tariff_catalog.json", modes_out)
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
        obs_sample = {
            "schema": "vibe22.mega.obs_v4_sample.v1",
            "phase_status": "CONTRACT_ONLY",
            "n_obs": int(vec.size),
            "future_tariff_in_observation": ctx["future_tariff_in_observation"],
        }
        _write_example(6, "obs_v4_sample.json", obs_sample)
        phase_status["6"] = "CONTRACT_ONLY"

    if start_phase <= 7:
        floors = candidate_and_baseline_floors(
            candidate_mtd_peak_kw=155.0,
            baseline_mtd_peak_kw=180.0,
            ratchet_floor_kw=170.0,
            contract_floor_kw=165.0,
        )
        floors["phase_status"] = "CONTRACT_ONLY"
        artifacts["phase7"] = _write_example(7, "billing_floors.json", floors)
        phase_status["7"] = "CONTRACT_ONLY"

    if start_phase <= 8:
        contract = contract_manifest()
        contract["phase_status"] = "CONTRACT_ONLY"
        artifacts["phase8"] = _write_example(8, "common_action_contract.json", contract)
        phase_status["8"] = "CONTRACT_ONLY"

    if start_phase <= 9:
        fixed = arm_manifest()
        artifacts["phase9"] = _write_example(9, "fixed_rules.json", fixed)
        phase_status["9"] = "CONTRACT_ONLY"

    if start_phase <= 10:
        gs = GridSearchArm(day="2025-12-15")
        for params in default_coarse_grid():
            gs.add_coarse(params)
        body = gs.to_dict()
        body["phase_status"] = "SCAFFOLD_ONLY"
        body["label"] = EXAMPLE_LABEL
        artifacts["phase10"] = _write_example(10, "grid_search_schema.json", body)
        phase_status["10"] = "SCAFFOLD_ONLY"

    if start_phase <= 11:
        phase_status["11"] = "SCAFFOLD_ONLY"
        artifacts["phase11"] = _write_example(
            11,
            "day_ahead_optimizer_schema.json",
            {
                "schema": "vibe22.mega.day_ahead_optimizer.v1",
                "phase_status": "SCAFFOLD_ONLY",
                "note": "stub_objective blocked in production runner; EnergyPlus confirmation required.",
                "occupied_heating_bounds_f": [68.0, 72.0],
            },
        )

    if start_phase <= 12:
        bundle = mega_training_bundle()
        bundle["dqn"]["phase_status"] = "NOT_RUN"
        bundle["dqn"]["label"] = EXAMPLE_LABEL
        artifacts["phase12"] = _write_example(12, "multi_seed_dqn_config.json", bundle["dqn"])
        phase_status["12"] = "NOT_RUN"

    if start_phase <= 13:
        bundle = mega_training_bundle()
        bundle["ppo"]["phase_status"] = "NOT_RUN"
        bundle["ppo"]["label"] = EXAMPLE_LABEL
        artifacts["phase13"] = _write_example(13, "multi_seed_ppo_config.json", bundle["ppo"])
        phase_status["13"] = "NOT_RUN"

    if start_phase <= 14:
        phase1_path = _APP / "docs" / "audits" / "figures" / "vibe22_mega_phase1" / "phase1_evidence_freeze.json"
        phase1 = json.loads(phase1_path.read_text(encoding="utf-8")) if phase1_path.is_file() else {}
        forbidden = phase1.get("date_use_ledger", {}).get("locked_test", {}).get("inspected_january_dates", [])
        adapt = default_adaptation_spec(forbidden_january=forbidden)
        body = adapt.to_dict()
        body["phase_status"] = "CONTRACT_ONLY"
        artifacts["phase14"] = _write_example(14, "shadow_adaptation.json", body)
        phase_status["14"] = "CONTRACT_ONLY"

    if start_phase <= 15:
        phase_status["15"] = "BLOCKED_BY_PHYSICS"
        artifacts["phase15"] = _write_example(
            15,
            "validation_selection_schema.json",
            {
                "schema": "vibe22.mega.validation_selection.v1",
                "phase_status": "BLOCKED_BY_PHYSICS",
                "locked_test_status": NO_PRISTINE_LOCKED_TEST,
                "note": "No synthetic PPO/DQN validation rows.",
            },
        )

    if start_phase <= 16:
        phase_status["16"] = "NOT_RUN"
        artifacts["phase16"] = _write_example(
            16,
            "final_plot_manifest_schema.json",
            {
                "schema": "vibe22.mega.final_plot_manifest.v1",
                "phase_status": "NOT_RUN",
                "note": "Plots from real Phase 0 manifests only.",
            },
        )

    if start_phase <= 17:
        phase_status["17"] = "NOT_RUN"
        artifacts["phase17"] = {
            "note": "Scientific report withheld until live E+ / training evidence exists.",
        }

    if start_phase <= 18:
        phase_status["18"] = "partial"
        artifacts["phase18"] = {
            "note": "Spec index partial — mega v3 phases 4–17 pending live evidence.",
        }

    if start_phase <= 19:
        phase_status["19"] = "tests_required"
        artifacts["phase19"] = {"note": "pytest mega scaffold + phase2 branch tests"}

    if start_phase <= 20:
        phase_status["20"] = "SCAFFOLD_ONLY"
        artifacts["phase20"] = _write_example(
            20,
            "terminal_handoff_schema.json",
            {
                "schema": "vibe22.mega.terminal_handoff.v1",
                "phase_status": "SCAFFOLD_ONLY",
                "vibe19_untouched": True,
                "bacnet_command_authority": 0,
            },
        )

    summary = {
        "label": EXAMPLE_LABEL,
        "phase_status": phase_status,
        "artifacts": list(artifacts.keys()),
        "fixture_root": str(FIXTURES.relative_to(_APP)).replace("\\", "/"),
        "forbidden_paths": ["docs/audits/figures/vibe22_mega/phase[3-9]"],
    }
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description="Vibe22 mega phase status (fail-closed scaffold runner)")
    p.add_argument("--start-phase", type=int, default=2)
    args = p.parse_args()
    summary = run_all(start_phase=args.start_phase)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
