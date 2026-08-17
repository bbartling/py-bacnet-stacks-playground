"""Write selection_verdict.json from on-disk artifacts. Tests must call compute_selection_verdict."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04v2_selection import compute_selection_verdict
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
    track_b_failed = load_json(root / "trackB" / "failed.json")
    track_b_plan = (root / "trackB" / "plan.json").is_file()
    body = compute_selection_verdict(
        stage_a_summary=stage_a,
        peak_contract=peak,
        champion=champion,
        long_campaign_ramp_passed=False,
        track_b_attempted=bool(track_b_plan or track_b_failed),
        track_b_failed_honestly=bool(track_b_failed and track_b_failed.get("failed") is True),
        stage_b_trials=trials,
    )
    dest = root / "selection_verdict.json"
    dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": body["verdict"], "long_campaign_allowed": body["long_campaign_allowed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
