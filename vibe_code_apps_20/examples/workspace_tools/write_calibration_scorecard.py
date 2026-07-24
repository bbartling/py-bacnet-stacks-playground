#!/usr/bin/env python3
"""Write Twin-expected calibration_scorecard.json from g14_score.json / score_g14_monthly.

Studio tip (PR33+) G14 iteration charts only read:
  calibration_scorecard.json | campaign_stamp.json | wattlab_report.json
and expect nested::

  {
    "utility_bills": {
      "pass_fail": "PASS"|"FAIL",
      "stats_electricity": {"nmbe_pct": …, "cvrmse_pct": …},
      "stats_natural_gas": {"nmbe_pct": …, "cvrmse_pct": …}
    }
  }

Our publish path historically wrote g14_score.json + a wattlab_report.g14 blob that
does NOT match that shape — so charts show "No per-run G14 scorecards yet".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def g14_to_calibration_scorecard(g14: dict[str, Any]) -> dict[str, Any]:
    elec = g14.get("elec") if isinstance(g14.get("elec"), dict) else {}
    gas = g14.get("gas") if isinstance(g14.get("gas"), dict) else {}
    if not elec and "nmbe_pct" in g14:
        # flat single-fuel shape
        elec = g14
    pass_fail = g14.get("pass_fail") or g14.get("overall")
    if pass_fail is None:
        ep = bool(g14.get("elec_pass"))
        gp = g14.get("gas_pass")
        if gp is None:
            pass_fail = "PASS" if ep else "FAIL"
        else:
            pass_fail = "PASS" if (ep and bool(gp)) else "FAIL"
    if isinstance(pass_fail, bool):
        pass_fail = "PASS" if pass_fail else "FAIL"
    out: dict[str, Any] = {
        "utility_bills": {
            "pass_fail": str(pass_fail).upper() if pass_fail else "FAIL",
            "stats_electricity": {
                "nmbe_pct": elec.get("nmbe_pct"),
                "cvrmse_pct": elec.get("cvrmse_pct"),
            },
            "stats_natural_gas": {
                "nmbe_pct": gas.get("nmbe_pct"),
                "cvrmse_pct": gas.get("cvrmse_pct"),
            },
        }
    }
    # Preserve monthly rows if present (deliverables / debugging).
    monthly = g14.get("monthly")
    if isinstance(monthly, list) and monthly:
        out["utility_bills"]["per_month"] = monthly
    for k in ("annual_elec_delta_pct", "annual_gas_delta_pct", "elec_pass", "gas_pass", "g14_pass"):
        if k in g14:
            out[k] = g14[k]
    return out


def scorecard_from_run_dir(run_dir: Path) -> dict[str, Any] | None:
    for name in ("g14_score.json", "calibration_scorecard.json"):
        p = run_dir / name
        if not p.is_file():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        if name == "calibration_scorecard.json" and isinstance(data.get("utility_bills"), dict):
            return data
        # g14_score.json or nested under wattlab_report
        if "elec" in data or "gas" in data or "utility_bills" in data:
            if "utility_bills" in data:
                return data
            return g14_to_calibration_scorecard(data)
    wr = run_dir / "wattlab_report.json"
    if wr.is_file():
        data = json.loads(wr.read_text(encoding="utf-8"))
        g14 = data.get("g14") if isinstance(data, dict) else None
        if isinstance(g14, dict):
            return g14_to_calibration_scorecard(g14)
    return None


def write_for_run(run_dir: Path, *, force: bool = False) -> Path | None:
    dest = run_dir / "calibration_scorecard.json"
    if dest.is_file() and not force:
        existing = json.loads(dest.read_text(encoding="utf-8"))
        bills = existing.get("utility_bills") if isinstance(existing, dict) else None
        se = (bills or {}).get("stats_electricity") if isinstance(bills, dict) else None
        if isinstance(se, dict) and se.get("nmbe_pct") is not None:
            return dest
    sc = scorecard_from_run_dir(run_dir)
    if not sc:
        return None
    dest.write_text(json.dumps(sc, indent=2) + "\n", encoding="utf-8")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("runs", nargs="+", type=Path, help="Run dir(s) or runs/ root")
    ap.add_argument("--all-under", action="store_true", help="Treat each path as runs root")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    ok = 0
    skip = 0
    for root in args.runs:
        dirs = sorted(p for p in root.iterdir() if p.is_dir()) if args.all_under else [root]
        for d in dirs:
            if not d.is_dir():
                continue
            out = write_for_run(d, force=args.force)
            if out:
                print(f"ok  {d.name} -> {out.name}")
                ok += 1
            else:
                print(f"skip {d.name} (no g14_score / wattlab_report.g14)")
                skip += 1
    print(f"wrote={ok} skip={skip}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
