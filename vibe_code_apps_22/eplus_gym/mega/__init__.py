"""Vibe22 mega-program v3 phases 3–20 (Phase 2 lives in phase2_w2a_diagnosis)."""

from eplus_gym.mega.child_model_ledger import ChildModelLedger, register_child_model
from eplus_gym.mega.physics_repair_matrix import PhysicsRepairMatrix
from eplus_gym.mega.load_shape_gates import LoadShapePromotionGate
from eplus_gym.mega.billing_floors import candidate_and_baseline_floors
from eplus_gym.mega.common_action_contract import MEGA_ACTION_CONTRACT_V1
from eplus_gym.mega.fixed_rules import FIXED_TOU_RULE, FIXED_WEATHER_RULE
from eplus_gym.mega.grid_search import GridSearchArm
from eplus_gym.mega.day_ahead_optimizer import DayAheadOptimizerArm
from eplus_gym.mega.multi_seed_config import MEGA_MIN_SEEDS
from eplus_gym.mega.shadow_adaptation import ShadowAdaptationSpec
from eplus_gym.mega.validation_locked_test import ValidationSelectionResult
from eplus_gym.mega.terminal_handoff import build_terminal_handoff

__all__ = [
    "ChildModelLedger",
    "register_child_model",
    "PhysicsRepairMatrix",
    "LoadShapePromotionGate",
    "candidate_and_baseline_floors",
    "MEGA_ACTION_CONTRACT_V1",
    "FIXED_WEATHER_RULE",
    "FIXED_TOU_RULE",
    "GridSearchArm",
    "DayAheadOptimizerArm",
    "MEGA_MIN_SEEDS",
    "ShadowAdaptationSpec",
    "ValidationSelectionResult",
    "build_terminal_handoff",
]
