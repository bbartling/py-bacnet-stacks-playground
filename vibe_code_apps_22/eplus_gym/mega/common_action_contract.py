"""Phase 8: common control/action contract shared by all comparison arms."""
from __future__ import annotations

from typing import Any

from eplus_gym.control_v2 import SixZoneDailyParamsV2
from eplus_gym.rl.research_spaces import RESEARCH_ACTION_CONTRACT_V2

MEGA_ACTION_CONTRACT_V1 = {
    "schema": "vibe22.mega.common_action_contract.v1",
    "research_action_contract": RESEARCH_ACTION_CONTRACT_V2,
    "school_occupancy": "calendar_truth",
    "shared_by_arms": [
        "FIXED_WEATHER_RULE",
        "FIXED_TOU_RULE",
        "GRID_SEARCH",
        "DAY_AHEAD_OPTIMIZER",
        "DQN",
        "PPO",
        "BAS_INCUMBENT",
    ],
    "decoder": "research_action_contract_v2_affine_box",
    "bacnet_command_authority": 0,
}


def decode_action_for_arm(raw_action: Any, *, arm: str, day: str = "2025-12-15") -> SixZoneDailyParamsV2:
    from eplus_gym.rl.research_spaces import decode_continuous_research_v2

    _ = arm  # all arms share the same decoder envelope
    return decode_continuous_research_v2(raw_action, day=day)


def contract_manifest() -> dict[str, Any]:
    return dict(MEGA_ACTION_CONTRACT_V1)
