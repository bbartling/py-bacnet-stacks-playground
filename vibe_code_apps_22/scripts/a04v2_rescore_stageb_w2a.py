"""Rescore published Stage B W2A warning counts with the real-format parser.

Does not weaken thresholds or promote a model. If .err files are absent, the
historical phase attribution is marked unparseable / not evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

from eplus_gym.eplus_err import parse_eplus_err, scored_runtime_w2a_count
from eplus_gym.trackb_banks import scored_runtime_w2a_pass

APP = Path(__file__).resolve().parents[1]
STAGE_B = APP / "docs" / "audits" / "figures" / "a04v2" / "stageB"
OUT = APP / "docs" / "audits" / "figures" / "vibe22_repair" / "stageb_w2a_rescore.json"


def main() -> int:
    err_files = list(STAGE_B.rglob("eplusout.err")) if STAGE_B.is_dir() else []
    rows = []
    for err in err_files:
        gate = parse_eplus_err(err)
        rows.append(
            {
                "err": err.relative_to(APP).as_posix(),
                "warmup": (gate.get("w2a_low_airflow_by_phase") or {}).get("warmup"),
                "sizing": (gate.get("w2a_low_airflow_by_phase") or {}).get("sizing"),
                "scored_runtime": scored_runtime_w2a_count(gate),
                "unparseable": bool(gate.get("w2a_phase_unparseable")),
                "runtime_pass": scored_runtime_w2a_pass(gate),
                "printed_total": (gate.get("recurring") or {}).get("w2a_low_airflow"),
            }
        )
    body = {
        "schema": "vibe22.stageb.w2a_rescore.v1",
        "n_err_files": len(err_files),
        "threshold_unchanged_scored_runtime_max": 0,
        "promoted_model": None,
        "note": (
            "Old parser treated the first 'total times' integer as warmup. "
            "Rescore uses runtime = total - warmup - sizing. Missing .err files "
            "cannot be reconstructed; published Stage B recurring=1 values are "
            "warning-object counts, not phase totals."
        ),
        "rows": rows,
        "long_campaign_allowed": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n_err_files": len(err_files), "out": str(OUT.name)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
