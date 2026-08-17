"""Summarize Stage A CapMult ramp/peak results."""
from __future__ import annotations

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "docs" / "audits" / "figures" / "a04v2" / "stageA"
for m in (10, 20, 40):
    d = json.loads((root / f"capmult_t{m}" / "ramp_gate.json").read_text(encoding="utf-8"))
    print(
        f"t={m} passed={d['passed']} "
        f"inc={d['incumbent_simulated_max_f_per_15min']:.3f} "
        f"low={d['perturbed_simulated_max_f_per_15min']:.3f} "
        f"high={d['high_occ_simulated_max_f_per_15min']:.3f}"
    )
    for arm in ("incumbent", "low_unocc", "high_occ"):
        r = root / f"capmult_t{m}" / arm / "reward.json"
        if r.is_file():
            j = json.loads(r.read_text(encoding="utf-8"))
            print(f"  {arm}: peak={float(j['peak_kw']):.2f} kWh={float(j['daily_kwh']):.1f}")
