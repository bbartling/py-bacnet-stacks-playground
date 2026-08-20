"""Write compact Stage A trial table from ramp_gate + reward.json."""
from __future__ import annotations

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "docs" / "audits" / "figures" / "a04v2" / "stageA"
rows = []
for p in sorted(root.glob("*/ramp_gate.json")):
    run_id = p.parent.name
    d = json.loads(p.read_text(encoding="utf-8"))
    peak = None
    r = p.parent / "incumbent" / "reward.json"
    if r.is_file():
        peak = float(json.loads(r.read_text(encoding="utf-8"))["peak_kw"])
    rows.append(
        {
            "run_id": run_id,
            "ramp_passed": d.get("passed"),
            "inc_max": d.get("incumbent_simulated_max_f_per_15min"),
            "low_max": d.get("perturbed_simulated_max_f_per_15min"),
            "high_max": d.get("high_occ_simulated_max_f_per_15min"),
            "inc_peak_kw": peak,
            "peak_10pct_pass": peak is not None and 256.338 <= peak <= 313.302,
        }
    )
out = {
    "schema": "vibe22.a04v2.stageA_summary.v1",
    "threshold_f_per_15min": 2.650769999999918,
    "peak_band_kw": [256.338, 313.302],
    "trials": rows,
}
dest = root.parent / "stageA_summary.json"
dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
