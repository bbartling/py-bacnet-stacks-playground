"""Rescore Stage B warning gates using EnergyPlus 'occurred N total times' counts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.eplus_err import parse_eplus_err
from eplus_gym.path_sanitize import redact_obj

MAX_W2A = 0


def main() -> int:
    root = _APP / "docs" / "audits" / "figures" / "a04v2" / "stageB"
    ledger_path = root / "campaign_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    for rec in ledger["trials"]:
        dest = root / rec["run_id"]
        errs = list(dest.rglob("eplusout.err")) if dest.is_dir() else []
        hist = []
        max_air = 0
        for err in errs:
            q = parse_eplus_err(err)
            n = int((q.get("recurring") or {}).get("w2a_low_airflow") or 0)
            hist.append(
                {
                    "err": err.parent.name,
                    "w2a_low_airflow": n,
                    "warning_count": q.get("warning_count"),
                    "severe_count": q.get("severe_count"),
                    "fatal_count": q.get("fatal_count"),
                }
            )
            max_air = max(max_air, n)
        rec["eplus_warning_histogram"] = hist
        rec["warning_gate"] = {
            "max_w2a_low_airflow": MAX_W2A,
            "w2a_low_airflow": max_air,
            "n_err_files": len(errs),
            "passed": max_air <= MAX_W2A,
        }
    ledger = redact_obj(ledger)
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    n_ramp = sum(1 for t in ledger["trials"] if (t.get("ramp") or {}).get("passed"))
    n_warn = sum(1 for t in ledger["trials"] if (t.get("warning_gate") or {}).get("passed"))
    print(json.dumps({"n": len(ledger["trials"]), "ramp_passed": n_ramp, "warning_passed": n_warn}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
