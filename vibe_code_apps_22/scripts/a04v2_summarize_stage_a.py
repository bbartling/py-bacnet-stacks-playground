"""Summarize Stage A CapMult / InternalMass ramp/peak results from on-disk artifacts."""
from __future__ import annotations

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "docs" / "audits" / "figures" / "a04v2" / "stageA"


def trial_dirs() -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        d
        for d in root.iterdir()
        if d.is_dir() and (d.name.startswith("capmult_t") or d.name.startswith("imass_"))
    )


def summarize() -> list[dict]:
    rows = []
    for d in trial_dirs():
        gate_p = d / "ramp_gate.json"
        if not gate_p.is_file():
            continue
        gate = json.loads(gate_p.read_text(encoding="utf-8"))
        rec = {
            "run_id": d.name,
            "passed": gate.get("passed"),
            "inc": gate.get("incumbent_simulated_max_f_per_15min"),
            "low": gate.get("perturbed_simulated_max_f_per_15min"),
            "high": gate.get("high_occ_simulated_max_f_per_15min"),
        }
        for arm in ("incumbent", "low_unocc", "high_occ"):
            r = d / arm / "reward.json"
            if r.is_file():
                j = json.loads(r.read_text(encoding="utf-8"))
                rec[f"{arm}_peak_kw"] = float(j.get("peak_kw") or 0.0)
        rows.append(rec)
    return rows


def main() -> int:
    for rec in summarize():
        print(
            f"{rec['run_id']} passed={rec['passed']} "
            f"inc={rec['inc']:.3f} low={rec['low']:.3f} high={rec['high']:.3f}"
        )
        if "incumbent_peak_kw" in rec:
            print(f"  incumbent peak={rec['incumbent_peak_kw']:.2f} kW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
