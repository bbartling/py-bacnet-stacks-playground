#!/usr/bin/env python3
"""Sidecar midnight tick. Advisory JSON only — never BACnet writes."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from eplus_gym.rl.field_sidecar import midnight_tick  # noqa: E402
from eplus_gym.rl.policy_pack import DailyPolicyPack  # noqa: E402


def main() -> int:
    pack = Path(os.environ.get("POLICY_PACK", "/shared/daily_policy.pkl"))
    out = Path(os.environ.get("PROPOSAL_OUT", "/shared/proposed_setpoints.json"))
    day = os.environ.get("TICK_DAY", "2026-01-26")
    if not pack.is_file():
        DailyPolicyPack().save(pack)
    hourly = [-5.0] * 24  # pretend OWM payload injected at midnight
    midnight_tick(
        pack_path=pack,
        day=day,
        forecast_source="pretend_owm",
        out_path=out,
        hourly_override=hourly,
    )
    print("wrote", out, "bacnet_writes=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
