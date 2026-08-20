"""Write selection_verdict.json from on-disk artifacts. Tests must call compute_selection_verdict."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04v2_selection import compute_selection_verdict, track_b_state_from_plan
from eplus_gym.demand_windows import freeze_peak_contract


def load_json(path: Path) -> dict | None:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def main() -> int:
    root = _APP / "docs" / "audits" / "figures" / "a04v2"
    peak = load_json(root / "peak_contract.json") or freeze_peak_contract()
    stage_a = load_json(root / "stageA_summary.json")
    ledger = load_json(root / "stageB" / "campaign_ledger.json") or {"trials": []}
    trials = ledger.get("trials") or []
    champ_path = root / "champion.json"
    champion = load_json(champ_path)
    failed = load_json(root / "trackB" / "failed.json")
    plan = load_json(root / "trackB" / "plan.json") or {}
    state = track_b_state_from_plan(plan)
    if failed and failed.get("failed") is True:
        state["track_b_failed_honestly"] = True
        state["track_b_live_energyplus_executed"] = True
        state["track_b_executed"] = True
    body = compute_selection_verdict(
        stage_a_summary=stage_a,
        peak_contract=peak,
        champion=champion,
        long_campaign_ramp_passed=False,
        track_b_planned=state["track_b_planned"],
        track_b_plan_created=state["track_b_plan_created"],
        track_b_builder_prototype_created=state["track_b_builder_prototype_created"],
        track_b_structural_validation_passed=state["track_b_structural_validation_passed"],
        track_b_live_energyplus_executed=state["track_b_live_energyplus_executed"],
        track_b_executed=state["track_b_executed"],
        track_b_completed=state["track_b_completed"],
        track_b_failed_honestly=state["track_b_failed_honestly"],
        stage_b_trials=trials,
    )
    dest = root / "selection_verdict.json"
    dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": body["verdict"], "long_campaign_allowed": body["long_campaign_allowed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
