#!/usr/bin/env python3
"""Sidecar midnight tick. Advisory JSON only — never BACnet writes."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from eplus_gym.rl.field_sidecar import midnight_tick  # noqa: E402


def main() -> int:
    pack = Path(os.environ.get("POLICY_PACK", "/shared/daily_policy.pkl"))
    out = Path(os.environ.get("PROPOSAL_OUT", "/shared/proposed_setpoints.json"))
    day = os.environ.get("TICK_DAY", "2026-01-26")
    if not pack.is_file():
        raise FileNotFoundError(f"missing policy pack {pack}; refusing silent heuristic")
    fixture = os.environ.get("VIBE22_TEST_FORECAST_C", "").strip()
    if fixture:
        hourly = [float(fixture)] * 24
        source = "test_fixture_constant_c"
    else:
        hourly = [-5.0] * 24
        source = "test_fixture_minus5c_not_openweathermap"
    midnight_tick(
        pack_path=pack,
        day=day,
        forecast_source=source,
        out_path=out,
        hourly_override=hourly,
    )
    print("wrote", out, "bacnet_writes=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
